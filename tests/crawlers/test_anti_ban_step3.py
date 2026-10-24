"""防封第三步 (#21): DMM 图片校验失败计数修正 + 各站最小请求间隔."""

import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import mdcx.base.web as base_web
from mdcx.config.enums import Website
from mdcx.config.manager import manager
from mdcx.config.models import Config, SiteConfig
from mdcx.web_async import AsyncWebClient, CrawlRequestState, crawl_request_state, movie_request_scope
from tests.crawlers.test_javlibrary_429_backoff import FakeResponse

DMM_IMAGE = "https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/ssni00126/ssni00126pl.jpg"


class VirtualClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay


def _client(clock: VirtualClock, **kwargs) -> AsyncWebClient:
    client = AsyncWebClient(timeout=10, cf_bypass_url="", **kwargs)
    client._time_fn = clock.time
    client._sleep = clock.sleep
    return client


def _always_403(client: AsyncWebClient, calls: list[str]) -> None:
    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        calls.append(url)
        return FakeResponse(status_code=403, content=b"Forbidden", url=url)

    client._curl_request = fake_curl_request  # type: ignore[method-assign]


def _patch_computed(client: AsyncWebClient):
    @contextlib.asynccontextmanager
    async def fake_acquire():
        yield SimpleNamespace(async_client=client)

    return patch.object(manager, "acquire_computed", fake_acquire)


# ---- Part 1: 一部片最多记 1 次失败 ----


@pytest.mark.asyncio
async def test_dmm_image_validation_outer_retries_record_single_failure():
    """retry=5 时 DMM 图片校验外层重试 5 次, 全部 403, 同一部片只向断路器记 1 次失败."""
    clock = VirtualClock()
    client = _client(clock)
    calls: list[str] = []
    _always_403(client, calls)

    original_retry = manager.config.retry
    manager.config.retry = 5
    try:
        with _patch_computed(client), patch.object(base_web.asyncio, "sleep", clock.sleep):
            result = await base_web._validate_dmm_image_url(DMM_IMAGE)
    finally:
        manager.config.retry = original_retry

    assert result is None
    # 外层重试次数不变: 5 轮, 每轮 403 后含 1 次 15s 重试 => 10 次请求
    assert len(calls) == 10
    state = client._site_ban_states.get("dmm")
    assert state is not None
    assert state.failure_count == 1
    assert not state.circuit_open
    await client.close()


@pytest.mark.asyncio
async def test_unfixed_behavior_would_trip_breaker_without_movie_scope():
    """对照: 若每次外层重试各自记一次 (无同片状态), 3 次即断路 —— 说明修正前确会记满."""
    clock = VirtualClock()
    client = _client(clock)
    calls: list[str] = []
    _always_403(client, calls)

    for _ in range(3):
        # 每次调用都用全新的请求状态, 等价于修正前各次外层重试互不关联
        token = crawl_request_state.set(CrawlRequestState(is_blocked=lambda: False, site_name="dmm"))
        try:
            await client.request("GET", DMM_IMAGE, retry_count=1)
        finally:
            crawl_request_state.reset(token)
        clock.now += 100  # 越过 60s 暂停窗口

    state = client._site_ban_states["dmm"]
    assert state.failure_count == 3
    assert state.circuit_open
    await client.close()


@pytest.mark.asyncio
async def test_success_resets_counter_and_new_movie_counts_again():
    """成功一次计数归零; 不同影片 (不同请求状态) 仍各记 1 次, 连续 3 部才断路."""
    clock = VirtualClock()
    client = _client(clock)
    calls: list[str] = []
    mode = {"ok": False}

    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        calls.append(url)
        if mode["ok"]:
            return FakeResponse(status_code=200, content=b"img", url=url)
        return FakeResponse(status_code=403, content=b"Forbidden", url=url)

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    for _ in range(2):
        with movie_request_scope("dmm"):
            for _ in range(5):
                await client.request("GET", DMM_IMAGE, retry_count=1)
        clock.now += 100
    assert client._site_ban_states["dmm"].failure_count == 2

    mode["ok"] = True
    with movie_request_scope("dmm"):
        res, _ = await client.request("GET", DMM_IMAGE, retry_count=1)
    assert res is not None
    assert client._site_ban_states["dmm"].failure_count == 0
    await client.close()


def test_dmm_hosts_share_one_site_key():
    client = AsyncWebClient(timeout=1)
    assert client._resolve_site_key("awsimgsrc.dmm.co.jp") == "dmm"
    assert client._resolve_site_key("pics.dmm.co.jp") == "dmm"
    assert client._resolve_site_key("www.dmm.co.jp") == "dmm"
    assert client._resolve_site_key("javdb.com") == "javdb.com"


# ---- Part 2: 各站最小请求间隔 ----


def test_config_default_and_old_config_loads():
    assert Config().request_interval == 3
    assert SiteConfig().request_interval is None
    cfg = Config.model_validate({"site_configs": {"dmm": {"request_interval": 5}}})
    assert cfg.request_interval == 3
    assert cfg.get_site_request_interval(Website.DMM) == 5
    assert cfg.get_site_request_interval(Website.JAVDB) == 3
    assert cfg.get_site_request_intervals() == {"dmm": 5.0}


@pytest.mark.asyncio
async def test_interval_enforced_across_requests_to_same_site():
    clock = VirtualClock()
    client = _client(clock, request_interval=3)
    calls: list[str] = []

    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        calls.append(url)
        return FakeResponse(status_code=200, content=b"ok", url=url)

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    await client.request("GET", "https://javdb.com/a")
    await client.request("GET", "https://javdb.com/b")
    assert clock.sleeps == [pytest.approx(3.0)]
    # 另一站点不受影响
    await client.request("GET", "https://javbus.com/a")
    assert clock.sleeps == [pytest.approx(3.0)]
    await client.close()


@pytest.mark.asyncio
async def test_interval_zero_means_unlimited_and_site_override():
    clock = VirtualClock()
    client = _client(clock, request_interval=0, site_request_intervals={"javdb": 5})

    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        return FakeResponse(status_code=200, content=b"ok", url=url)

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    for _ in range(3):
        await client.request("GET", "https://javbus.com/a")
    assert clock.sleeps == []

    await client.request("GET", "https://javdb.com/a")
    await client.request("GET", "https://javdb.com/b")
    assert clock.sleeps == [pytest.approx(5.0)]
    await client.close()


@pytest.mark.asyncio
async def test_interval_covers_dmm_image_domains_and_threads():
    """DMM 图片域名 (非主站域名) 与并发请求合计也受同一站点间隔约束."""
    clock = VirtualClock()
    client = _client(clock, request_interval=3)

    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        return FakeResponse(status_code=200, content=b"ok", url=url)

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    urls = [
        "https://www.dmm.co.jp/a",
        "https://awsimgsrc.dmm.co.jp/b.jpg",
        "https://pics.dmm.co.jp/c.jpg",
    ]
    await asyncio.gather(*(client.request("GET", u) for u in urls))
    assert sorted(clock.sleeps) == [pytest.approx(3.0), pytest.approx(3.0)]
    await client.close()


@pytest.mark.asyncio
async def test_javlibrary_keeps_3s_bypass_interval_and_config_override():
    client = AsyncWebClient(timeout=1, request_interval=0)
    assert client._get_cf_bypass_min_interval("www.javlibrary.com") == 3.0
    await client.close()
    client = AsyncWebClient(timeout=1, site_request_intervals={"javlibrary": 6})
    assert client._get_cf_bypass_min_interval("www.javlibrary.com") == 6.0
    await client.close()
