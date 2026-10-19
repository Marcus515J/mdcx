import asyncio

import pytest

from mdcx.config.enums import Language
from mdcx.models.types import CrawlerInput, CrawlerResult
from mdcx.web_async import AsyncWebClient
from tests.cf_fake_server import FakeBypassServer, ProbeCrawler, Scenario
from tests.crawlers.test_javlibrary_429_backoff import (
    FakeResponse,
    test_t1_mirror_first_429_with_retry_after_retries_and_succeeds,
    test_t2_mirror_continuous_429_exceeds_retry_limit_trips_circuit_breaker,
    test_t3_429_without_retry_after_uses_backoff_and_bounded_by_timeout,
    test_t4_regression_mirror_terminal_400_skips_html_and_stops_retry,
    test_t5_regression_mirror_general_5xx_falls_back_to_html,
    test_t6_site_minimum_interval_javlibrary_vs_other_site,
)


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


@pytest.mark.asyncio
async def test_t1_host_confirmed_bypass_skips_direct_connection():
    """T1: 同一 host 第 1 个请求遇挑战页、bypass 成功；第 2 个请求不发直连，直接走 bypass；提示日志只出现一次。"""
    logs: list[str] = []
    client = AsyncWebClient(
        timeout=10,
        cf_bypass_url="http://127.0.0.1:8000",
        log_fn=logs.append,
    )

    direct_calls: list[str] = []
    mirror_calls: list[str] = []

    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        if "127.0.0.1:8000" in url:
            mirror_calls.append(url)
            return FakeResponse(
                status_code=200,
                content=b"<html>success</html>",
                url=url,
            )
        direct_calls.append(url)
        return FakeResponse(
            status_code=503,
            headers={"server": "cloudflare", "cf-ray": "1234567890"},
            content=b"<html>just a moment cf-chl</html>",
            url=url,
        )

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    # 第 1 个请求: 直连遇到挑战页 -> bypass 成功
    res1, err1 = await client.request("GET", "https://www.javlibrary.com/ja/vl_searchbyid.php?keyword=SSNI-126")
    assert res1 is not None
    assert err1 == ""
    assert len(direct_calls) == 1
    assert len(mirror_calls) == 1
    assert "www.javlibrary.com" in client._cf_known_bypass_hosts

    confirmed_log = "🛡️ [CF] www.javlibrary.com 已确认需要 bypass，本次运行后续请求直接走 bypass"
    assert sum(confirmed_log in line for line in logs) == 1

    # 第 2 个请求: 直接走 bypass，不发直连
    res2, err2 = await client.request("GET", "https://www.javlibrary.com/ja/?v=javli12345")
    assert res2 is not None
    assert err2 == ""
    # 直连调用数保持 1，没有新增直连
    assert len(direct_calls) == 1
    # mirror 调用增加到 2
    assert len(mirror_calls) == 2
    # 确认日志只打印一次
    assert sum(confirmed_log in line for line in logs) == 1

    await client.close()


@pytest.mark.asyncio
async def test_t2_other_host_still_tries_direct_connection():
    """T2: 另一个从未遇挑战的 host，仍按原逻辑先直连。"""
    logs: list[str] = []
    client = AsyncWebClient(
        timeout=10,
        cf_bypass_url="http://127.0.0.1:8000",
        log_fn=logs.append,
    )
    # 模拟 host1 已经确认 bypass
    client._cf_known_bypass_hosts.add("www.javlibrary.com")

    direct_calls: list[str] = []
    mirror_calls: list[str] = []

    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        if "127.0.0.1:8000" in url:
            mirror_calls.append(url)
            return FakeResponse(status_code=200, content=b"<html>mirror success</html>", url=url)
        direct_calls.append(url)
        return FakeResponse(status_code=200, content=b"<html>direct success</html>", url=url)

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    # 请求未遭遇过挑战的 host2 (如 dmm.co.jp)
    res, err = await client.request("GET", "https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=ssni126/")
    assert res is not None
    assert err == ""
    # host2 必须走直连，不走 bypass
    assert len(direct_calls) == 1
    assert "www.dmm.co.jp" in direct_calls[0]
    assert len(mirror_calls) == 0

    await client.close()


@pytest.mark.asyncio
async def test_t3_single_movie_timeout_does_not_trip_circuit_breaker():
    """T3: 一部片在某站累计超 site_total_timeout -> 该片该站放弃；断路器未打开；同站下一部片仍会请求。"""
    async with FakeBypassServer(log=lambda _: None) as server:
        # slow.test 在途延时 0.4s
        server.scenarios["slow.test"] = Scenario(direct_status=200, direct_delay=0.4)
        client = server.client(cf_bypass_url="", site_total_timeout=0.1)
        crawler = ProbeCrawler(client, server.url("slow.test").rstrip("/"))

        # 第一部片耗时超限 (0.4s > 0.1s)
        result1 = await crawler.run(_crawl_input("MOVIE-001"))
        assert result1.data is None
        assert isinstance(result1.debug_info.error, TimeoutError)
        # 断路器未打开！
        assert crawler._site_failure == ""

        # 第二部片恢复正常
        server.scenarios["slow.test"].direct_delay = 0.0
        result2 = await crawler.run(_crawl_input("MOVIE-002"))
        assert result2.data is not None
        assert server.count("direct", "slow.test") == 2

        await client.close()


@pytest.mark.asyncio
async def test_t4_cooldown_and_429_backoff_not_counted_in_timeout():
    """T4: 排队等冷却 + 429 退避合计超过 site_total_timeout，但在途时间不超 -> 不判超时。"""
    async with FakeBypassServer(log=lambda _: None) as server:
        # 设置单番号在途上限为 0.25 秒
        client = server.client(cf_bypass_url="", site_total_timeout=0.25)
        crawler = ProbeCrawler(client, server.url("plain.test").rstrip("/"))

        # 模拟 2 次请求，每次在途仅 0.05 秒 (合计 0.1s < 0.25s)，但中间发生 0.4 秒的排队/冷却/429退避
        server.scenarios["plain.test"] = Scenario(direct_status=200, direct_delay=0.05)

        async def simulated_run(ctx):
            from mdcx.web_async import extend_crawl_timeout

            # 首次在途请求 (0.05s)
            r1, _ = await crawler.async_client.request("GET", crawler.base_url + "/one")
            assert r1 is not None

            # 模拟排队与429退避合计等待 0.4 秒 (已远超 0.25 秒预算)
            wait_time = 0.4
            extend_crawl_timeout(wait_time)
            await asyncio.sleep(wait_time)

            # 第二次在途请求 (0.05s)
            r2, _ = await crawler.async_client.request("GET", crawler.base_url + "/two")
            assert r2 is not None

            res = CrawlerResult.empty()
            res.title = "ok"
            return res

        crawler._run = simulated_run  # type: ignore[method-assign]

        start_time = asyncio.get_running_loop().time()
        result = await crawler.run(_crawl_input("MOVIE-T4"))
        total_wall_clock = asyncio.get_running_loop().time() - start_time

        # 墙钟耗时确实超过了 0.4 秒
        assert total_wall_clock >= 0.45
        # 但因为在途时间仅 0.1s，不判超时，成功取得数据！
        assert result.data is not None
        assert result.debug_info.error is None
        assert crawler._site_failure == ""

        await client.close()


@pytest.mark.asyncio
async def test_t5_regression_exhausted_attempts_still_trips_circuit_breaker():
    """T5: 回归：「允许的请求尝试已耗尽」仍打开断路器（与 master 一致）。"""
    async with FakeBypassServer(log=lambda _: None) as server:
        # plain.test 返回 500
        server.scenarios["plain.test"] = Scenario(direct_status=500, direct_body=b"failure")
        client = server.client(cf_bypass_url="", retry=2)
        client._calc_retry_sleep_seconds = lambda *args, **kwargs: 0
        crawler = ProbeCrawler(client, server.url("plain.test").rstrip("/"))

        res1 = await crawler.run(_crawl_input("ONE"))
        assert res1.data is None
        # 尝试耗尽触发断路器
        assert crawler._site_failure == "允许的请求尝试已耗尽，未取得页面"

        # 后续番号直接跳过
        res2 = await crawler.run(_crawl_input("TWO"))
        assert res2.data is None
        # 总请求数依然为 2 (第一次番号的 2 次 retry 耗尽，后续番号未发请求)
        assert server.count("direct", "plain.test") == 2

        await client.close()


@pytest.mark.asyncio
async def test_t6_regression_v26_all_tests_pass():
    """T6: 回归：v2.6 的 T1–T6 全部仍通过。"""
    await test_t1_mirror_first_429_with_retry_after_retries_and_succeeds()
    await test_t2_mirror_continuous_429_exceeds_retry_limit_trips_circuit_breaker()
    await test_t3_429_without_retry_after_uses_backoff_and_bounded_by_timeout()
    await test_t4_regression_mirror_terminal_400_skips_html_and_stops_retry()
    await test_t5_regression_mirror_general_5xx_falls_back_to_html()
    await test_t6_site_minimum_interval_javlibrary_vs_other_site()
