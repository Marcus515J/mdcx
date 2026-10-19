from unittest.mock import patch

import pytest

from mdcx.config.enums import Language, Website
from mdcx.crawlers.base import BaseCrawler, CrawlerInput
from mdcx.models.types import CrawlerResult
from mdcx.web_async import AsyncWebClient


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        headers: dict[str, str] | None = None,
        content: bytes = b"ok",
        url: str = "https://www.javlibrary.com/ja/vl_searchbyid.php?keyword=SSNI-126",
    ):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content
        self.url = url
        self.encoding = "utf-8"

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding, errors="replace")


def _fake_response(**kwargs) -> FakeResponse:
    return FakeResponse(**kwargs)


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
            "https://www.javlibrary.com/ja/vl_searchbyid.php?keyword=SSNI-126"
        )
        if text is None:
            return None
        data = CrawlerResult.empty()
        data.title = "Test Title"
        return data


def _crawl_input(number: str = "SSNI-126"):
    return CrawlerInput(
        appoint_number="",
        appoint_url="",
        file_path=None,
        number=number,
        mosaic="有码",
        short_number="",
        language=Language.UNDEFINED,
        org_language=Language.UNDEFINED,
    )


@pytest.mark.asyncio
async def test_t1_mirror_first_429_with_retry_after_retries_and_succeeds():
    """T1: mirror 首次 429（带 Retry-After: 2），重试 200 -> 返回 200 页面；未调用 /html；断路器计数不变。"""
    logs: list[str] = []
    client = AsyncWebClient(timeout=10, cf_bypass_url="http://127.0.0.1:8000", log_fn=logs.append)
    crawler = DummyJavCrawler(client)

    mirror_calls = 0
    html_calls = 0
    sleeps: list[float] = []

    async def fake_curl_request(*args, **kwargs):
        nonlocal mirror_calls
        url = str(kwargs.get("url") or "")
        # First request is direct request -> trigger CF challenge
        if "127.0.0.1:8000" not in url:
            return _fake_response(
                status_code=503,
                headers={"server": "cloudflare", "cf-ray": "abc123ray"},
                content=b"<html>just a moment cf-chl</html>",
            )
        # Mirror requests to bypass server
        mirror_calls += 1
        if mirror_calls == 1:
            return _fake_response(
                status_code=429,
                headers={"Retry-After": "2"},
                content=b"Too Many Requests",
            )
        return _fake_response(status_code=200, content=b"<html>detail page ok</html>")

    async def fake_call_html(*args, **kwargs):
        nonlocal html_calls
        html_calls += 1
        return _fake_response(status_code=200, content=b"<html>html mode</html>"), ""

    async def fake_sleep(sec: float):
        sleeps.append(sec)

    client._curl_request = fake_curl_request  # type: ignore[method-assign]
    client._call_bypass_html = fake_call_html  # type: ignore[method-assign]

    with patch("asyncio.sleep", fake_sleep):
        resp = await crawler.run(_crawl_input())

    assert resp.data is not None
    assert mirror_calls == 2
    assert html_calls == 0
    assert not crawler._site_failure
    assert 2.0 in sleeps
    assert any("⏳ [限流] javlibrary 返回 429，等待 2s 后重试 (1/2)" in line for line in logs)
    await client.close()


@pytest.mark.asyncio
async def test_t2_mirror_continuous_429_exceeds_retry_limit_trips_circuit_breaker():
    """T2: mirror 连续 429 超过重试上限 -> 不调用 /html；按一次失败计入断路器；日志含限流文案。"""
    logs: list[str] = []
    client = AsyncWebClient(timeout=10, cf_bypass_url="http://127.0.0.1:8000", log_fn=logs.append)
    crawler = DummyJavCrawler(client)

    mirror_calls = 0
    html_calls = 0

    async def fake_curl_request(*args, **kwargs):
        nonlocal mirror_calls
        url = str(kwargs.get("url") or "")
        if "127.0.0.1:8000" not in url:
            return _fake_response(
                status_code=503,
                headers={"server": "cloudflare", "cf-ray": "abc123ray"},
                content=b"<html>just a moment cf-chl</html>",
            )
        mirror_calls += 1
        return _fake_response(status_code=429, content=b"Too Many Requests")

    async def fake_call_html(*args, **kwargs):
        nonlocal html_calls
        html_calls += 1
        return None, "html 模式不应被调用"

    async def fake_sleep(sec: float):
        pass

    client._curl_request = fake_curl_request  # type: ignore[method-assign]
    client._call_bypass_html = fake_call_html  # type: ignore[method-assign]

    with patch("asyncio.sleep", fake_sleep):
        resp = await crawler.run(_crawl_input())

    assert resp.data is None
    assert html_calls == 0
    # 1 initial + 2 retries = 3 mirror calls
    assert mirror_calls == 3
    # Exactly one failure opened the circuit breaker
    assert crawler._site_failure == "允许的请求尝试已耗尽，未取得页面"
    assert any("⏳ [限流] javlibrary 返回 429" in line for line in logs)
    assert any("跳过 /html 回退" in line for line in logs)

    # Subsequent runs are skipped by circuit breaker
    resp2 = await crawler.run(_crawl_input("SSNI-127"))
    assert resp2.data is None
    assert mirror_calls == 3  # unchanged, not requested
    await client.close()


@pytest.mark.asyncio
async def test_t3_429_without_retry_after_uses_backoff_and_bounded_by_timeout():
    """T3: 429 不带 Retry-After -> 用退避时间；总等待不超过 site_total_timeout。"""
    logs: list[str] = []
    client = AsyncWebClient(
        timeout=10,
        site_total_timeout=8.0,
        cf_bypass_url="http://127.0.0.1:8000",
        log_fn=logs.append,
    )

    mirror_calls = 0
    sleeps: list[float] = []

    async def fake_curl_request(*args, **kwargs):
        nonlocal mirror_calls
        url = str(kwargs.get("url") or "")
        if "127.0.0.1:8000" not in url:
            return _fake_response(
                status_code=503,
                headers={"server": "cloudflare", "cf-ray": "abc123ray"},
                content=b"<html>just a moment cf-chl</html>",
            )
        mirror_calls += 1
        return _fake_response(status_code=429, content=b"Too Many Requests")

    async def fake_sleep(sec: float):
        sleeps.append(sec)

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    with patch("asyncio.sleep", fake_sleep):
        res, err = await client.request("GET", "https://www.javlibrary.com/ja/vl_searchbyid.php?keyword=SSNI-126")

    assert res is None
    assert mirror_calls == 3
    # Attempt 1: backoff is 5.0s (< 8.0s site_total_timeout)
    assert sleeps[0] == 5.0
    # Attempt 2: normal backoff would be 10.0s, but bounded by site_total_timeout=8.0s!
    assert sleeps[1] == 8.0
    assert all(s <= 8.0 for s in sleeps)
    await client.close()


@pytest.mark.asyncio
async def test_t4_regression_mirror_terminal_400_skips_html_and_stops_retry():
    """T4: 原有行为回归：mirror 终态 400 -> 仍跳过 /html、停止重试（与 master 一致）。"""
    logs: list[str] = []
    client = AsyncWebClient(timeout=10, cf_bypass_url="http://127.0.0.1:8000", log_fn=logs.append)

    mirror_calls = 0
    html_calls = 0

    async def fake_curl_request(*args, **kwargs):
        nonlocal mirror_calls
        url = str(kwargs.get("url") or "")
        if "127.0.0.1:8000" not in url:
            return _fake_response(
                status_code=503,
                headers={"server": "cloudflare", "cf-ray": "abc123ray"},
                content=b"<html>just a moment cf-chl</html>",
            )
        mirror_calls += 1
        return _fake_response(status_code=400, content=b"Bad Request")

    async def fake_call_html(*args, **kwargs):
        nonlocal html_calls
        html_calls += 1
        return None, "html 模式不应被调用"

    client._curl_request = fake_curl_request  # type: ignore[method-assign]
    client._call_bypass_html = fake_call_html  # type: ignore[method-assign]

    res, err = await client.request("GET", "https://missav.ws/cn/ssni-126")

    assert res is None
    assert mirror_calls == 1  # 400 stops immediately, no 429 retry
    assert html_calls == 0  # /html is skipped
    assert any("mirror 返回终态 HTTP 400，跳过 /html 回退" in line for line in logs)
    assert any("bypass 命中终态 HTTP 400，停止重试" in line for line in logs)
    await client.close()


@pytest.mark.asyncio
async def test_t5_regression_mirror_general_5xx_falls_back_to_html():
    """T5: 原有行为回归：mirror 一般失败（如 5xx）-> 仍按原逻辑回退 /html。"""
    logs: list[str] = []
    client = AsyncWebClient(timeout=10, cf_bypass_url="http://127.0.0.1:8000", log_fn=logs.append)

    mirror_calls = 0
    html_calls = 0

    async def fake_curl_request(*args, **kwargs):
        nonlocal mirror_calls
        url = str(kwargs.get("url") or "")
        if "127.0.0.1:8000" not in url:
            return _fake_response(
                status_code=503,
                headers={"server": "cloudflare", "cf-ray": "abc123ray"},
                content=b"<html>just a moment cf-chl</html>",
            )
        mirror_calls += 1
        return _fake_response(status_code=500, content=b"Internal Server Error")

    async def fake_call_html(*args, **kwargs):
        nonlocal html_calls
        html_calls += 1
        return _fake_response(status_code=200, content=b"<html>html success</html>"), ""

    client._curl_request = fake_curl_request  # type: ignore[method-assign]
    client._call_bypass_html = fake_call_html  # type: ignore[method-assign]

    res, err = await client.request("GET", "https://www.javlibrary.com/ja/vl_searchbyid.php?keyword=SSNI-126")

    assert res is not None
    assert mirror_calls == 1
    assert html_calls == 1  # /html was called!
    assert any("回退 /html: mirror HTTP 500" in line for line in logs)
    await client.close()


@pytest.mark.asyncio
async def test_t6_site_minimum_interval_javlibrary_vs_other_site():
    """T6: 同站最小间隔 -> javlibrary 相邻两次请求的发出时间差 ≥ 设定值；另一个站不受影响（用 mock 时钟）。"""
    client = AsyncWebClient(timeout=10, cf_bypass_url="http://127.0.0.1:8000")

    # Verify per-site interval configuration
    assert client._get_cf_bypass_min_interval("www.javlibrary.com") == 3.0
    assert client._get_cf_bypass_min_interval("javlibrary.com") == 3.0
    assert client._get_cf_bypass_min_interval("missav.ws") == 2.0
    assert client._get_cf_bypass_min_interval("www.dmm.co.jp") == 2.0

    current_time = 1000.0
    sleeps: list[float] = []

    def fake_monotonic():
        return current_time

    async def fake_sleep(sec: float):
        nonlocal current_time
        sleeps.append(sec)
        current_time += sec

    async def fake_mirror(**kwargs):
        return _fake_response(status_code=200, content=b"ok"), ""

    client._call_bypass_mirror = fake_mirror  # type: ignore[method-assign]

    with patch("time.monotonic", fake_monotonic), patch("asyncio.sleep", fake_sleep):
        # 1. First request to javlibrary at t=1000.0
        resp1, err1 = await client._try_bypass_cloudflare(
            host="www.javlibrary.com",
            method="GET",
            target_url="https://www.javlibrary.com/ja/jav1.html",
            headers={},
            cookies=None,
            data=None,
            json_data=None,
            timeout=None,
            allow_redirects=True,
            use_proxy=False,
        )
        assert resp1 is not None
        assert len(sleeps) == 0  # first request, no cooldown wait

        # Advance time by 1.0 second (t=1001.0, elapsed = 1.0s < 3.0s)
        current_time = 1001.0

        # 2. Second request to javlibrary at t=1001.0
        resp2, err2 = await client._try_bypass_cloudflare(
            host="www.javlibrary.com",
            method="GET",
            target_url="https://www.javlibrary.com/ja/jav2.html",
            headers={},
            cookies=None,
            data=None,
            json_data=None,
            timeout=None,
            allow_redirects=True,
            use_proxy=False,
        )
        assert resp2 is not None
        # Had to wait 3.0 - 1.0 = 2.0 seconds
        assert len(sleeps) == 1
        assert pytest.approx(sleeps[0], 0.01) == 2.0

        # 3. Request to another site (missav.ws) at t=1003.0
        # missav has never made a bypass request, so no cooldown wait
        resp3, err3 = await client._try_bypass_cloudflare(
            host="missav.ws",
            method="GET",
            target_url="https://missav.ws/cn/ssni-126",
            headers={},
            cookies=None,
            data=None,
            json_data=None,
            timeout=None,
            allow_redirects=True,
            use_proxy=False,
        )
        assert resp3 is not None
        # missav request was immediate, no additional sleep
        assert len(sleeps) == 1

        # Advance time by 0.5 second for missav (elapsed = 0.5s < 2.0s)
        current_time += 0.5
        resp4, err4 = await client._try_bypass_cloudflare(
            host="missav.ws",
            method="GET",
            target_url="https://missav.ws/cn/ssni-127",
            headers={},
            cookies=None,
            data=None,
            json_data=None,
            timeout=None,
            allow_redirects=True,
            use_proxy=False,
        )
        assert resp4 is not None
        # missav waited 2.0 - 0.5 = 1.5 seconds (not 3.0 seconds!)
        assert len(sleeps) == 2
        assert pytest.approx(sleeps[1], 0.01) == 1.5

    await client.close()
