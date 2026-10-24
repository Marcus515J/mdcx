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
from mdcx.web_async import (
    AsyncWebClient,
    CrawlRequestState,
    SiteCircuitOpen,
    crawl_request_state,
    movie_request_scope,
)
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
async def test_three_distinct_movies_fail_once_each_trips_dmm_circuit_breaker():
    """第 3 项: 3 部不同的片各失败一次，DMM 才被停站（第 1、2 部各失败一次不停站，第 3 部失败才停站，第二步规则不被破坏）."""
    clock = VirtualClock()
    client = _client(clock)
    calls: list[str] = []
    _always_403(client, calls)

    original_retry = manager.config.retry
    manager.config.retry = 5
    try:
        with _patch_computed(client), patch.object(base_web.asyncio, "sleep", clock.sleep):
            # 第 1 部片：内部重试 5 次，但整部片只记 1 次失败；不停站 (circuit_open=False)
            res1 = await base_web._validate_dmm_image_url(DMM_IMAGE)
            assert res1 is None
            state = client._site_ban_states["dmm"]
            assert state.failure_count == 1
            assert not state.circuit_open
            assert not client._is_site_circuit_open("dmm")

            # 模拟时间流逝，度过第 1 部片触发的 60s 站点暂停
            clock.now += 100

            # 第 2 部片：同样内部重试 5 次，只累计第 2 次失败；依然不停站 (circuit_open=False)
            res2 = await base_web._validate_dmm_image_url(DMM_IMAGE)
            assert res2 is None
            assert state.failure_count == 2
            assert not state.circuit_open
            assert not client._is_site_circuit_open("dmm")

            # 再次度过 60s 站点暂停
            clock.now += 100

            # 第 3 部片：累计达到第 3 次失败，此时断路器触发停站！(circuit_open=True)
            res3 = await base_web._validate_dmm_image_url(DMM_IMAGE)
            assert res3 is None
            assert state.failure_count == 3
            assert state.circuit_open
            assert client._is_site_circuit_open("dmm")

            # 断路后后续请求直接抛出 SiteCircuitOpen，不再发起实际网络请求
            calls_before = len(calls)
            with pytest.raises(SiteCircuitOpen, match="已断路"):
                await client.request("GET", DMM_IMAGE)
            assert len(calls) == calls_before
    finally:
        manager.config.retry = original_retry
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

    # 明确断言：切换到不同站点（javbus），距离上一次 javdb 请求仅 0 秒，但互不等待
    sleeps_before = len(clock.sleeps)
    await client.request("GET", "https://javbus.com/a")
    assert len(clock.sleeps) == sleeps_before, "不同站点之间互不等待，请求 javbus 不应增加 sleep"
    await client.close()


@pytest.mark.asyncio
async def test_concurrent_threads_same_site_wait_but_different_sites_do_not_wait():
    """第 4 项: 两个线程同时请求同一站点，间隔不小于设定值；不同站点之间互不等待."""
    clock = VirtualClock()
    client = _client(clock, request_interval=3)

    async def fake_curl_request(*args, **kwargs):
        url = str(kwargs.get("url") or "")
        return FakeResponse(status_code=200, content=b"ok", url=url)

    client._curl_request = fake_curl_request  # type: ignore[method-assign]

    # Part A: 同时请求不同站点 (javdb 与 javbus) —— 互不等待 (0 延迟)
    clock.sleeps.clear()
    await asyncio.gather(
        client.request("GET", "https://javdb.com/a1"),
        client.request("GET", "https://javbus.com/b1"),
    )
    assert clock.sleeps == [], "不同站点同时发起的首次请求应当互不等待 (sleep 为空)"

    # Part B: 立即（同一时刻）紧接着请求第三个站点 (mgstage) —— 依然互不等待
    await client.request("GET", "https://mgstage.com/c1")
    assert clock.sleeps == [], "向第三个站点发起请求不应受前两个站点影响 (sleep 为空)"

    # Part C: 两个并发任务同时请求「同一站点」(javdb) —— 必须串行等待，间隔 >= 3.0s
    clock.sleeps.clear()
    await asyncio.gather(
        client.request("GET", "https://javdb.com/a2"),
        client.request("GET", "https://javdb.com/a3"),
    )
    assert clock.sleeps == [pytest.approx(3.0), pytest.approx(3.0)], "同一站点并发请求必须分别满足 3.0s 最小间隔"

    # Part D: 在 javdb 刚刚发生过请求的瞬间，立即请求从未请求过的 site D (fanza) —— 互不等待！
    clock.sleeps.clear()
    await client.request("GET", "https://fanza.co.jp/d1")
    assert clock.sleeps == [], "不同站点之间互不等待：请求 site D 不应受 javdb 刚完成的请求阻塞"

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
