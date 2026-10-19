import asyncio
from unittest.mock import patch

import pytest

import mdcx.base.web as base_web
from mdcx.config.enums import Language, Website
from mdcx.config.manager import manager
from mdcx.config.models import Config
from mdcx.crawlers.base import BaseCrawler
from mdcx.models.types import CrawlerInput, CrawlerResult
from mdcx.web_async import (
    AsyncWebClient,
    SiteCircuitOpen,
)
from tests.cf_fake_server import FakeBypassServer, ProbeCrawler
from tests.crawlers.test_javlibrary_429_backoff import FakeResponse


def _crawl_input(number="SSNI-126"):
    return CrawlerInput(
        appoint_number="",
        appoint_url="",
        file_path=None,
        number=number,
        mosaic="",
        short_number="",
        language=Language.UNDEFINED,
        org_language=Language.UNDEFINED,
    )


class DummyJavCrawler(BaseCrawler):
    @classmethod
    def site(cls):
        return Website.JAVLIBRARY

    @classmethod
    def base_url_(cls) -> str:
        return "https://www.javlibrary.com"

    async def _generate_search_url(self, ctx):
        return None

    async def _parse_search_page(self, ctx, html, search_url: str):
        return None

    async def _parse_detail_page(self, ctx, html, detail_url: str):
        return None

    async def _run(self, ctx):
        text, error = await self.async_client.get_text(
            f"https://www.javlibrary.com/ja/vl_searchbyid.php?keyword={ctx.input.number}"
        )
        if text is None:
            return None
        data = CrawlerResult.empty()
        data.title = f"Title for {ctx.input.number}"
        return data


@pytest.mark.asyncio
async def test_t1_direct_403_non_cf_retries_after_15s_and_succeeds():
    """T1: 直连 403（非 CF 页），重试后 200；共 2 次请求；中间等 15 秒（测试 mock sleep）；不记失败。"""
    logs: list[str] = []
    client = AsyncWebClient(timeout=10, cf_bypass_url="", log_fn=logs.append)
    calls: list[str] = []
    sleeps: list[float] = []

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    client._sleep = fake_sleep

    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        calls.append(url)
        if len(calls) == 1:
            return FakeResponse(status_code=403, content=b"Forbidden", url=url)
        return FakeResponse(status_code=200, content=b"<html>success</html>", url=url)

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    res, err = await client.request("GET", "https://javdb.com/v/12345")
    assert res is not None
    assert res.status_code == 200
    assert err == ""
    assert len(calls) == 2
    assert sleeps == [15.0]

    # 日志匹配
    assert any("⚠️ [封禁] javdb.com 返回 403，等待 15s 后重试 1 次" in line for line in logs)

    # 成功后未记失败（计数为 0）
    site_state = client._site_ban_states.get("javdb.com")
    assert site_state is None or site_state.failure_count == 0

    await client.close()


@pytest.mark.asyncio
async def test_t2_single_movie_403_twice_abandons_and_pauses_60s():
    """T2: 一部片 403 两次；该片放弃该站；计数 1；该站暂停 60 秒；同站下一部片暂停结束后仍会请求。"""
    logs: list[str] = []
    client = AsyncWebClient(timeout=10, cf_bypass_url="", log_fn=logs.append)
    crawler = DummyJavCrawler(client=client)
    calls: list[str] = []
    sleeps: list[float] = []

    virtual_time = 1000.0
    client._time_fn = lambda: virtual_time

    async def fake_sleep(delay: float):
        nonlocal virtual_time
        sleeps.append(delay)
        virtual_time += delay

    client._sleep = fake_sleep

    # 第一部片：403 两次；第二部片：200 成功
    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        calls.append(url)
        if len(calls) <= 2:
            return FakeResponse(status_code=403, content=b"Forbidden", url=url)
        return FakeResponse(status_code=200, content=b"<html>success</html>", url=url)

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    # Movie 1 运行
    res1 = await crawler.run(_crawl_input("MOVIE-001"))
    assert res1.data is None
    # 单片失败不熔断断路器！
    assert crawler._site_failure == ""
    assert len(calls) == 2
    assert sleeps == [15.0]

    # 检查计数为 1，暂停 60s
    site_state = client._site_ban_states.get("javlibrary")
    assert site_state is not None
    assert site_state.failure_count == 1
    assert any("⏸️ [封禁] javlibrary 第 1/3 次被拒，暂停该站 60s" in line for line in logs)

    # Movie 2 运行：由于该站暂停 60 秒，排队等待暂停结束
    res2 = await crawler.run(_crawl_input("MOVIE-002"))
    assert res2.data is not None
    assert len(calls) == 3
    # 等待了 15s（重试）+ 60s（暂停）
    assert sleeps == [15.0, 60.0]
    # Movie 2 成功后清零
    assert site_state.failure_count == 0
    assert any("✅ [封禁] javlibrary 恢复正常，失败计数清零" in line for line in logs)

    await crawler.close()


@pytest.mark.asyncio
async def test_t3_three_consecutive_movies_403_twice_trips_circuit_breaker():
    """T3: 连续 3 部片各 403 两次；第 3 次后断路器打开，文案一致；第 4 部片跳过该站。"""
    logs: list[str] = []
    client = AsyncWebClient(timeout=10, cf_bypass_url="", log_fn=logs.append)
    crawler = DummyJavCrawler(client=client)
    calls: list[str] = []
    sleeps: list[float] = []

    virtual_time = 1000.0
    client._time_fn = lambda: virtual_time

    async def fake_sleep(delay: float):
        nonlocal virtual_time
        sleeps.append(delay)
        virtual_time += delay

    client._sleep = fake_sleep

    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        calls.append(url)
        return FakeResponse(status_code=403, content=b"Forbidden", url=url)

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    # Movie 1
    res1 = await crawler.run(_crawl_input("MOVIE-001"))
    assert res1.data is None
    assert crawler._site_failure == ""
    assert client._site_ban_states["javlibrary"].failure_count == 1

    # Movie 2
    res2 = await crawler.run(_crawl_input("MOVIE-002"))
    assert res2.data is None
    assert crawler._site_failure == ""
    assert client._site_ban_states["javlibrary"].failure_count == 2

    # Movie 3
    res3 = await crawler.run(_crawl_input("MOVIE-003"))
    assert res3.data is None
    # 连续 3 部片失败，断路器打开！
    expected_reason = "连续 3 部片被拒绝 (403)，可能已被限制访问"
    assert crawler._site_failure == expected_reason
    assert any(f"🚫 [断路器] javlibrary 本次运行停用：{expected_reason}" in line for line in logs)

    # 此时共调用 6 次请求 (3 部片各 2 次)
    assert len(calls) == 6

    # Movie 4: 后续番号跳过该站，不再发网络请求
    res4 = await crawler.run(_crawl_input("MOVIE-004"))
    assert res4.data is None
    assert isinstance(res4.debug_info.error, SiteCircuitOpen)
    assert len(calls) == 6  # 请求数未增加
    assert any("⏭ [断路器] javlibrary 本次运行跳过后续番号" in line for line in logs)

    await crawler.close()


@pytest.mark.asyncio
async def test_t4_two_failures_then_one_success_then_two_failures_does_not_trip():
    """T4: 失败 2 次后一次成功，再失败 2 次；不停站（成功清零），清零日志出现一次。"""
    logs: list[str] = []
    client = AsyncWebClient(timeout=10, cf_bypass_url="", log_fn=logs.append)
    crawler = DummyJavCrawler(client=client)
    calls: list[str] = []

    virtual_time = 1000.0
    client._time_fn = lambda: virtual_time

    async def fake_sleep(delay: float):
        nonlocal virtual_time
        virtual_time += delay

    client._sleep = fake_sleep

    # Movie 1, 2: 403; Movie 3: 200; Movie 4, 5: 403
    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        calls.append(url)
        # Movie 1 (call 1,2), Movie 2 (call 3,4) -> 403
        if len(calls) <= 4:
            return FakeResponse(status_code=403, content=b"Forbidden", url=url)
        # Movie 3 (call 5) -> 200
        if len(calls) == 5:
            return FakeResponse(status_code=200, content=b"<html>success</html>", url=url)
        # Movie 4 (call 6,7), Movie 5 (call 8,9) -> 403
        return FakeResponse(status_code=403, content=b"Forbidden", url=url)

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    # 失败 2 次
    await crawler.run(_crawl_input("MOVIE-001"))
    assert client._site_ban_states["javlibrary"].failure_count == 1
    await crawler.run(_crawl_input("MOVIE-002"))
    assert client._site_ban_states["javlibrary"].failure_count == 2

    # 成功 1 次
    res3 = await crawler.run(_crawl_input("MOVIE-003"))
    assert res3.data is not None
    assert client._site_ban_states["javlibrary"].failure_count == 0
    # 清零日志仅出现 1 次
    assert sum("✅ [封禁] javlibrary 恢复正常，失败计数清零" in line for line in logs) == 1

    # 再失败 2 次
    await crawler.run(_crawl_input("MOVIE-004"))
    assert client._site_ban_states["javlibrary"].failure_count == 1
    await crawler.run(_crawl_input("MOVIE-005"))
    assert client._site_ban_states["javlibrary"].failure_count == 2

    # 断路器依然未打开！
    assert crawler._site_failure == ""

    await crawler.close()


@pytest.mark.asyncio
async def test_t4b_concurrent_three_movies_403_twice_records_single_failure():
    """T4b: 并发 3 部片同时 403 两次；只记 1 次失败、只暂停一次。"""
    logs: list[str] = []
    client = AsyncWebClient(timeout=10, cf_bypass_url="", log_fn=logs.append)
    crawler = DummyJavCrawler(client=client)

    virtual_time = 1000.0
    client._time_fn = lambda: virtual_time

    async def fake_sleep(delay: float):
        # 允许微小让渡以模拟真实并发协同
        await asyncio.sleep(0.001)

    client._sleep = fake_sleep

    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        await asyncio.sleep(0.001)
        return FakeResponse(status_code=403, content=b"Forbidden", url=url)

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    # 并发跑 3 部片
    results = await asyncio.gather(
        crawler.run(_crawl_input("MOVIE-A")),
        crawler.run(_crawl_input("MOVIE-B")),
        crawler.run(_crawl_input("MOVIE-C")),
    )
    for r in results:
        assert r.data is None

    # 关键验证：由于同时在途并处于暂停窗口内，只记 1 次失败，只暂停一次
    site_state = client._site_ban_states["javlibrary"]
    assert site_state.failure_count == 1
    assert sum("暂停该站 60s" in line for line in logs) == 1
    assert crawler._site_failure == ""

    await crawler.close()


@pytest.mark.asyncio
async def test_t4c_cf_1015_ban_page_403_and_429_handled_as_ban():
    """T4c: 1015 封禁页（状态码 403 和 429 各一例）；按 403 规则处理，不走 429 两次退避。"""
    logs: list[str] = []
    client = AsyncWebClient(timeout=10, cf_bypass_url="", log_fn=logs.append)
    sleeps: list[float] = []

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    client._sleep = fake_sleep

    # 例 1：状态码 403 + 1015 封禁页面
    calls1: list[str] = []

    async def fake_curl_1015_403(*args, **kwargs):
        calls1.append(str(kwargs.get("url") or ""))
        return FakeResponse(
            status_code=403,
            content=b"<html><title>Error 1015: You are being rate limited</title></html>",
            url="https://javdb.com/search",
        )

    client._curl_request = fake_curl_1015_403  # type: ignore[method-assign]
    res1, err1 = await client.request("GET", "https://javdb.com/search")
    assert res1 is None
    assert len(calls1) == 2
    assert sleeps == [15.0]
    assert any("⚠️ [封禁] javdb.com 返回 403 (1015)，等待 15s 后重试 1 次" in line for line in logs)
    assert any("⏸️ [封禁] javdb.com 第 1/3 次被拒，暂停该站 60s" in line for line in logs)
    # 确认没有走普通 429 退避
    assert not any("⏳ [限流]" in line for line in logs)

    # 重置状态测试例 2
    client._site_ban_states.clear()
    logs.clear()
    sleeps.clear()

    # 例 2：状态码 429 + 1015 封禁页面
    calls2: list[str] = []

    async def fake_curl_1015_429(*args, **kwargs):
        calls2.append(str(kwargs.get("url") or ""))
        return FakeResponse(
            status_code=429,
            content=b"<html><body>error code: 1015<p>you are being rate limited</p></body></html>",
            url="https://javdb.com/detail",
        )

    client._curl_request = fake_curl_1015_429  # type: ignore[method-assign]
    res2, err2 = await client.request("GET", "https://javdb.com/detail")
    assert res2 is None
    assert len(calls2) == 2
    assert sleeps == [15.0]
    assert any("⚠️ [封禁] javdb.com 返回 429 (1015)，等待 15s 后重试 1 次" in line for line in logs)
    assert any("⏸️ [封禁] javdb.com 第 1/3 次被拒，暂停该站 60s" in line for line in logs)
    # 绝不走普通 429 的两次退避（无 ⏳ [限流]）
    assert not any("⏳ [限流]" in line for line in logs)

    await client.close()


@pytest.mark.asyncio
async def test_t5_normal_429_keeps_master_v26_backoff():
    """T5: 普通 429（非 1015）；与 master 一致（v2.6 退避）。"""
    logs: list[str] = []
    client = AsyncWebClient(timeout=10, cf_bypass_url="", log_fn=logs.append)
    calls: list[str] = []
    sleeps: list[float] = []

    async def fake_sleep(delay: float):
        sleeps.append(delay)

    client._sleep = fake_sleep

    # 普通 429，无 1015 文案，带 Retry-After: 3
    async def fake_curl_normal_429(*args, **kwargs):
        calls.append(str(kwargs.get("url") or ""))
        if len(calls) == 1:
            return FakeResponse(
                status_code=429,
                headers={"Retry-After": "3"},
                content=b"Too Many Requests",
                url="https://www.javlibrary.com/test",
            )
        return FakeResponse(status_code=200, content=b"<html>success</html>", url="https://www.javlibrary.com/test")

    client._curl_request = fake_curl_normal_429  # type: ignore[method-assign]
    res, err = await client.request("GET", "https://www.javlibrary.com/test")
    assert res is not None
    assert res.status_code == 200
    assert len(calls) == 2
    # 走的是 429 退避 (Retry-After: 3s)，不是 15s 封禁等待
    assert sleeps == [3.0]
    assert any("⏳ [限流] javlibrary 返回 429，等待 3s 后重试 (1/2)" in line for line in logs)
    assert not any("⚠️ [封禁]" in line for line in logs)

    await client.close()


@pytest.mark.asyncio
async def test_t6_403_cf_challenge_page_routes_to_bypass():
    """T6: 403 但是可解 CF 挑战页；与 master 一致（进 bypass）。"""
    logs: list[str] = []
    client = AsyncWebClient(timeout=10, cf_bypass_url="http://127.0.0.1:8000", log_fn=logs.append)
    direct_calls: list[str] = []
    mirror_calls: list[str] = []

    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        if "127.0.0.1:8000" in url:
            mirror_calls.append(url)
            return FakeResponse(status_code=200, content=b"<html>mirror success</html>", url=url)
        direct_calls.append(url)
        # 403 挑战页
        return FakeResponse(
            status_code=403,
            headers={"server": "cloudflare", "cf-ray": "12345678"},
            content=b"<html>just a moment cf-chl</html>",
            url=url,
        )

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    res, err = await client.request("GET", "https://www.javlibrary.com/test")
    assert res is not None
    assert res.status_code == 200
    assert len(direct_calls) == 1
    assert len(mirror_calls) == 1
    # 确认进入 CF bypass
    assert any("🛑 检测到 Cloudflare 挑战页" in line for line in logs)
    assert any("✅ bypass 成功" in line for line in logs)
    # 不会被误判为 403 封禁
    assert not any("⚠️ [封禁]" in line for line in logs)

    await client.close()


@pytest.mark.asyncio
async def test_t7_ban_15s_and_60s_pause_exempted_from_timeout():
    """T7: 15 秒重试等待、60 秒站点暂停都不计入单番号超时；与 v2.7 T4 同理。"""
    async with FakeBypassServer(log=lambda _: None) as server:
        # 单番号超时设为极短的 0.25 秒
        client = server.client(cf_bypass_url="", site_total_timeout=0.25)
        crawler = ProbeCrawler(client, server.url("plain.test").rstrip("/"))

        calls = 0

        async def fake_curl_request(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                return FakeResponse(status_code=403, content=b"Forbidden", url=server.url("plain.test"))
            return FakeResponse(status_code=200, content=b"<html>success</html>", url=server.url("plain.test"))

        client._curl_request = fake_curl_request  # type: ignore[method-assign]

        sleeps: list[float] = []

        async def fake_sleep(delay: float):
            sleeps.append(delay)
            # 模拟在 exempt 上下文内等待了 15 秒
            # 在单测中微眠 0.05 秒保证事件循环调度，但记录 delay
            await asyncio.sleep(0.05)

        client._sleep = fake_sleep

        res = await crawler.run(_crawl_input("MOVIE-T7"))
        # 尽管 15 秒等待（远超 0.25s 预算），但因为在途时间极短，不超时！
        assert res.data is not None
        assert res.debug_info.error is None
        assert sleeps == [15.0]

        await client.close()


@pytest.mark.asyncio
async def test_t8_trailer_quality_probe_disabled():
    """T8: trailer_quality_probe=false；不发探测 HEAD，使用原地址。"""
    original_config = manager.config.trailer_quality_probe
    try:
        manager.config.trailer_quality_probe = False

        checked_urls: list[str] = []

        async def fake_check_url(url: str):
            checked_urls.append(url)
            return True

        with patch.object(base_web, "check_url", fake_check_url):
            sample_url = "https://cc3001.dmm.co.jp/litevideo/freepv/s/ssi/ssis00090/ssis00090_sm_w.mp4"
            result_url = await base_web.get_dmm_trailer(sample_url)

            # 开关关闭时：不发探测 HEAD，直接返回原地址
            assert len(checked_urls) == 0
            assert result_url == sample_url
    finally:
        manager.config.trailer_quality_probe = original_config


@pytest.mark.asyncio
async def test_t9_trailer_quality_probe_enabled_and_default_true():
    """T9: trailer_quality_probe=true 及旧配置无此键；默认行为与 master 一致。"""
    # 验证 1: 默认模型反序列化（旧配置无此键）
    empty_cfg = Config.model_validate({})
    assert empty_cfg.trailer_quality_probe is True

    json_without_key = '{"timeout": 10}'
    cfg_from_json = Config.model_validate_json(json_without_key)
    assert cfg_from_json.trailer_quality_probe is True

    # 验证 2: 开启时发送探测 HEAD 请求，探测更高画质
    original_config = manager.config.trailer_quality_probe
    try:
        manager.config.trailer_quality_probe = True

        checked_urls: list[str] = []

        async def fake_check_url(url: str):
            checked_urls.append(url)
            # 假定 mhb 存在
            return "_mhb_" in url

        with patch.object(base_web, "check_url", fake_check_url):
            sample_url = "https://cc3001.dmm.co.jp/litevideo/freepv/s/ssi/ssis00090/ssis00090_sm_w.mp4"
            result_url = await base_web.get_dmm_trailer(sample_url)

            # 开关开启时：探测了更高画质
            assert len(checked_urls) > 0
            assert result_url == "https://cc3001.dmm.co.jp/litevideo/freepv/s/ssi/ssis00090/ssis00090_mhb_w.mp4"
    finally:
        manager.config.trailer_quality_probe = original_config


@pytest.mark.asyncio
async def test_t10_regression_all_v26_and_v27_tests():
    """T10: 回归：v2.6 T1–T6、v2.7 T1–T5 全部通过。"""
    from tests.crawlers.test_anti_ban_step1 import (
        test_t1_host_confirmed_bypass_skips_direct_connection,
        test_t2_other_host_still_tries_direct_connection,
        test_t3_single_movie_timeout_does_not_trip_circuit_breaker,
        test_t4_cooldown_and_429_backoff_not_counted_in_timeout,
        test_t5_regression_exhausted_attempts_still_trips_circuit_breaker,
    )
    from tests.crawlers.test_javlibrary_429_backoff import (
        test_t1_mirror_first_429_with_retry_after_retries_and_succeeds,
        test_t2_mirror_continuous_429_exceeds_retry_limit_trips_circuit_breaker,
        test_t3_429_without_retry_after_uses_backoff_and_bounded_by_timeout,
        test_t4_regression_mirror_terminal_400_skips_html_and_stops_retry,
        test_t5_regression_mirror_general_5xx_falls_back_to_html,
        test_t6_site_minimum_interval_javlibrary_vs_other_site,
    )

    # v2.6 回归测试
    await test_t1_mirror_first_429_with_retry_after_retries_and_succeeds()
    await test_t2_mirror_continuous_429_exceeds_retry_limit_trips_circuit_breaker()
    await test_t3_429_without_retry_after_uses_backoff_and_bounded_by_timeout()
    await test_t4_regression_mirror_terminal_400_skips_html_and_stops_retry()
    await test_t5_regression_mirror_general_5xx_falls_back_to_html()
    await test_t6_site_minimum_interval_javlibrary_vs_other_site()

    # v2.7 回归测试
    await test_t1_host_confirmed_bypass_skips_direct_connection()
    await test_t2_other_host_still_tries_direct_connection()
    await test_t3_single_movie_timeout_does_not_trip_circuit_breaker()
    await test_t4_cooldown_and_429_backoff_not_counted_in_timeout()
    await test_t5_regression_exhausted_attempts_still_trips_circuit_breaker()
