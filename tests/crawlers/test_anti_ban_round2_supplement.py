"""防封第②轮补充 (#25): 403/1015 重试日志补齐 + 预告片 404 记录 URL."""

import contextlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import mdcx.base.web as base_web
from mdcx.config.manager import manager
from mdcx.signals import signal
from mdcx.web_async import AsyncWebClient
from tests.crawlers.test_javlibrary_429_backoff import FakeResponse


class FastClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay


def _build_client(clock: FastClock, logs: list[str]) -> AsyncWebClient:
    client = AsyncWebClient(timeout=10, cf_bypass_url="", log_fn=logs.append)
    client._time_fn = clock.time
    client._sleep = clock.sleep
    return client


@pytest.mark.asyncio
async def test_403_retry_logs_each_attempt_with_host_and_status():
    """模拟一次 403 重试，断言每次尝试都有一行带主机和状态码。"""
    clock = FastClock()
    logs: list[str] = []
    client = _build_client(clock, logs)

    request_calls: list[str] = []

    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        request_calls.append(url)
        return FakeResponse(status_code=403, content=b"Forbidden", url=url)

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    test_url = "https://www.mgstage.com/product/product_detail/SIRO-5000/"
    resp, err = await client.request("GET", test_url, retry_count=3)
    assert resp is None
    # 第一次尝试 + 1 次封禁重试 = 2 次请求
    assert len(request_calls) == 2
    assert clock.sleeps == [15.0]

    # 断言第 1 次尝试有日志行带主机名和状态码
    attempt1_logs = [line for line in logs if "www.mgstage.com" in line and "403" in line and "重试 1 次" in line]
    assert len(attempt1_logs) == 1
    assert "⚠️ [封禁] www.mgstage.com 返回 403，等待 15s 后重试 1 次" in attempt1_logs[0]

    # 断言第 2 次尝试（重试）有日志行带主机名和状态码
    attempt2_logs = [line for line in logs if "www.mgstage.com" in line and "403" in line and "重试返回" in line]
    assert len(attempt2_logs) == 1
    assert "⚠️ [封禁] www.mgstage.com 重试返回 403" in attempt2_logs[0]

    # 总体验证：每一次尝试都有至少一行同时带主机和状态码
    host_and_status_logs = [line for line in logs if "www.mgstage.com" in line and "403" in line]
    assert len(host_and_status_logs) == 2

    await client.close()


@pytest.mark.asyncio
async def test_cf_1015_retry_logs_each_attempt_with_host_and_status():
    """模拟一次 1015 封禁重试，断言每次尝试都有一行带主机和状态码/失败类型。"""
    clock = FastClock()
    logs: list[str] = []
    client = _build_client(clock, logs)

    request_calls: list[str] = []

    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        request_calls.append(url)
        return FakeResponse(
            status_code=429,
            content=b"<html><title>Error 1015: You are being rate limited</title></html>",
            url=url,
        )

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    test_url = "https://www.javlibrary.com/test1015"
    resp, err = await client.request("GET", test_url, retry_count=3)
    assert resp is None
    assert len(request_calls) == 2

    # 断言第 1 次尝试带主机和 429 (1015)
    attempt1_logs = [
        line for line in logs if "www.javlibrary.com" in line and "429 (1015)" in line and "重试 1 次" in line
    ]
    assert len(attempt1_logs) == 1

    # 断言第 2 次尝试（重试）带主机和 429 (1015)
    attempt2_logs = [
        line for line in logs if "www.javlibrary.com" in line and "429 (1015)" in line and "重试返回" in line
    ]
    assert len(attempt2_logs) == 1

    await client.close()


@pytest.mark.asyncio
async def test_trailer_404_log_contains_url():
    """模拟预告片返回 404（Response 对象），断言日志行带上 URL。"""
    logs: list[str] = []

    class DummyClient:
        async def request(self, method: str, url: str, **kwargs):
            return FakeResponse(status_code=404, url=url), ""

    @contextlib.asynccontextmanager
    async def fake_acquire():
        yield SimpleNamespace(async_client=DummyClient())

    with (
        patch.object(manager, "acquire_computed", fake_acquire),
        patch.object(signal, "add_log", side_effect=logs.append),
    ):
        raw_url = "https://cc3001.dmm.co.jp/pv/dummykey/ssis00090_sm_w.mp4"
        expected_converted = "https://cc3001.dmm.co.jp/litevideo/freepv/s/ssi/ssis00090/ssis00090_sm_w.mp4"
        res = await base_web.get_dmm_trailer(raw_url)
        assert res == raw_url

        # 断言 404 日志行带上转换后的 URL
        log_404_lines = [line for line in logs if "返回404" in line]
        assert len(log_404_lines) == 1
        assert expected_converted in log_404_lines[0]
        assert f"⚠️ 转换后的URL返回404 ({expected_converted})，回退到原始链接" == log_404_lines[0]


@pytest.mark.asyncio
async def test_trailer_404_error_log_contains_url():
    """模拟预告片返回 404（error 字符串），断言日志行带上 URL。"""
    logs: list[str] = []

    class DummyClient:
        async def request(self, method: str, url: str, **kwargs):
            return None, "HTTP 404 Not Found"

    @contextlib.asynccontextmanager
    async def fake_acquire():
        yield SimpleNamespace(async_client=DummyClient())

    with (
        patch.object(manager, "acquire_computed", fake_acquire),
        patch.object(signal, "add_log", side_effect=logs.append),
    ):
        raw_url = "https://cc3001.dmm.co.jp/pv/dummykey/ssis00090_sm_w.mp4"
        expected_converted = "https://cc3001.dmm.co.jp/litevideo/freepv/s/ssi/ssis00090/ssis00090_sm_w.mp4"
        res = await base_web.get_dmm_trailer(raw_url)
        assert res == raw_url

        log_404_lines = [line for line in logs if "返回404" in line]
        assert len(log_404_lines) == 1
        assert expected_converted in log_404_lines[0]
        assert f"⚠️ 转换后的URL返回404 ({expected_converted})，回退到原始链接" == log_404_lines[0]
