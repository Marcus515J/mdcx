"""Issue #52: exhausted CF attempts share the existing per-movie pause/counter."""

import asyncio

import pytest
from curl_cffi.requests.exceptions import Timeout

from mdcx.crawlers.fc2hub import Fc2hubCrawler
from mdcx.crawlers.javlibrary import JavlibraryCrawler
from mdcx.web_async import AsyncWebClient, SiteCircuitOpen, exempt_crawl_timeout
from tests.cf_fake_server import FakeBypassServer, ProbeCrawler
from tests.crawlers.test_anti_ban_step2 import DummyJavCrawler, _crawl_input
from tests.crawlers.test_javlibrary_429_backoff import FakeResponse


@pytest.fixture
def probe():
    class Probe:
        def __init__(self):
            self.now = 1000.0
            self.mode = "cf"
            self.calls = []
            self.sleeps = []
            self.logs = []
            self.client = AsyncWebClient(timeout=10, cf_bypass_url="http://bypass.test:8000", log_fn=self.logs.append)
            self.client._time_fn = lambda: self.now
            self.client._sleep = self.sleep
            self.client._curl_request = self.request
            self.client._cf_bypass_min_interval = 0
            self.client._cf_site_min_intervals = {}

        async def sleep(self, delay):
            self.sleeps.append(delay)
            self.now += delay

        async def request(self, **kwargs):
            url = str(kwargs["url"])
            kind = "html" if url.endswith("/html") else "mirror" if "x-hostname" in kwargs["headers"] else "direct"
            self.calls.append((kind, self.now))
            if self.mode == "cf":
                if kind == "mirror":
                    raise Timeout("offline mirror timeout")
                if kind == "html":
                    return FakeResponse(status_code=500, url=url)
                return FakeResponse(status_code=503, content=b"<html>just a moment cf-chl</html>", url=url)
            if self.mode == "ban":
                return FakeResponse(status_code=403, content=b"Forbidden", url=url)
            return FakeResponse(status_code=200, content=b"<html>ok</html>", url=url)

    return Probe()


@pytest.mark.asyncio
@pytest.mark.parametrize("crawler_cls", [JavlibraryCrawler, Fc2hubCrawler])
async def test_three_cf_failures_pause_then_stop_without_extra_attempts(probe, crawler_cls):
    crawler = crawler_cls(probe.client)
    try:
        for index in range(1, 4):
            assert (await crawler.run(_crawl_input(f"FC2-{index}"))).data is None
            state = probe.client._site_ban_states[crawler.site().value]
            assert state.failure_count == index
            assert state.pause_until == probe.now + 60
            assert bool(crawler._site_failure) == (index == 3)
            assert [kind for kind, _ in probe.calls] == ["direct", "mirror", "html"] * index
            assert probe.sleeps == [60.0] * (index - 1)
        result = await crawler.run(_crawl_input("FC2-4"))
        assert isinstance(result.debug_info.error, SiteCircuitOpen)
        assert len(probe.calls) == 9
        assert sum("暂停该站 60s" in line for line in probe.logs) == 3
    finally:
        await probe.client.close()


@pytest.mark.asyncio
async def test_cf_and_403_share_counter_and_success_resets_it(probe):
    crawler = DummyJavCrawler(probe.client)
    try:
        for index, mode in enumerate(["cf", "ban", "ok", "cf", "ban", "cf"]):
            probe.mode = mode
            result = await crawler.run(_crawl_input(f"MOVIE-{index}"))
            assert (result.data is not None) == (mode == "ok")
            assert probe.client._site_ban_states["javlibrary"].failure_count == [1, 2, 0, 1, 2, 3][index]
            assert bool(crawler._site_failure) == (index == 5)
        assert sum("失败计数清零" in line for line in probe.logs) == 1
        assert [kind for kind, _ in probe.calls].count("html") == 3
    finally:
        await probe.client.close()


@pytest.mark.asyncio
async def test_same_movie_abandons_later_reads_without_retry_or_double_count(probe):
    crawler = DummyJavCrawler(probe.client)

    async def multiple_reads(ctx):
        assert (await probe.client.get_text(crawler.base_url + "/first"))[0] is None
        assert (await probe.client.get_text(crawler.base_url + "/second"))[0] is None
        return None

    crawler._run = multiple_reads
    try:
        await crawler.run(_crawl_input())
        assert [kind for kind, _ in probe.calls] == ["direct", "mirror", "html"]
        assert probe.sleeps == []
        assert probe.client._site_ban_states["javlibrary"].failure_count == 1
        assert not crawler._site_failure
    finally:
        await probe.client.close()


@pytest.mark.asyncio
async def test_movie_waiting_for_interval_rechecks_pause_before_sending(probe):
    crawler = DummyJavCrawler(probe.client)
    waiting = asyncio.Event()
    release = asyncio.Event()
    original_wait = probe.client._wait_for_site_request_interval

    async def wait_interval(site_key, host):
        if asyncio.current_task().get_name() == "waiting-movie":
            waiting.set()
            await release.wait()
        await original_wait(site_key, host)

    probe.client._wait_for_site_request_interval = wait_interval
    task = asyncio.create_task(crawler.run(_crawl_input("WAITING")), name="waiting-movie")
    try:
        await waiting.wait()
        await crawler.run(_crawl_input("FIRST"))
        pause_end = probe.client._site_ban_states["javlibrary"].pause_until
        release.set()
        await task
        assert probe.calls[3][1] >= pause_end
        assert probe.sleeps == [60.0]
        # This request was already queued before the first failure; preserve batch deduplication.
        assert probe.client._site_ban_states["javlibrary"].failure_count == 1
    finally:
        release.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await probe.client.close()


@pytest.mark.asyncio
async def test_real_transport_obeys_pause_and_resets_after_bypass_recovers():
    async with FakeBypassServer(log=lambda _: None) as server:
        server.scenarios["cold0.test"].html_status = 500
        client = server.client()
        client._cf_bypass_min_interval = 0
        client._cf_site_min_intervals = {}
        now = 1000.0
        sleeps = []
        client._time_fn = lambda: now

        async def sleep(delay):
            nonlocal now
            sleeps.append(delay)
            now += delay

        client._sleep = sleep
        crawler = ProbeCrawler(client, server.url("cold0.test").rstrip("/"))
        try:
            assert (await crawler.run(_crawl_input("ONE"))).data is None
            assert not crawler._site_failure
            assert client._site_ban_states["jav321"].failure_count == 1
            assert server.count("html", "cold0.test") == 1
            server.scenarios["cold0.test"].html_status = 200
            assert (await crawler.run(_crawl_input("TWO"))).data is not None
            assert sleeps == [60.0]
            assert server.count("html", "cold0.test") == 2
            assert client._site_ban_states["jav321"].failure_count == 0
        finally:
            await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("wait_kind", ["bypass_lock", "site_pause"])
async def test_exempt_wait_longer_than_movie_budget_does_not_expire_or_open_circuit(probe, wait_kind):
    probe.client.site_total_timeout = 0.03
    crawler = DummyJavCrawler(probe.client)
    release_task = None
    if wait_kind == "bypass_lock":
        lock = await probe.client._get_cf_host_lock("www.javlibrary.com")
        await lock.acquire()

        async def release():
            await asyncio.sleep(0.08)
            lock.release()

        release_task = asyncio.create_task(release())
    else:
        await crawler.run(_crawl_input("FIRST"))

        async def pause(delay):
            await asyncio.sleep(0.08)
            await probe.sleep(delay)

        probe.client._sleep = pause
    try:
        await crawler.run(_crawl_input("NEXT"))
        assert not any("Cannot change state" in line for line in probe.logs)
        assert not crawler._site_failure
        assert probe.client._site_ban_states["javlibrary"].failure_count == (1 if wait_kind == "bypass_lock" else 2)
    finally:
        if release_task is not None:
            await release_task
        await probe.client.close()


@pytest.mark.asyncio
async def test_nested_exempt_wait_does_not_disable_real_work_timeout(probe):
    probe.client.site_total_timeout = 0.03
    crawler = DummyJavCrawler(probe.client)

    async def run(ctx):
        async with exempt_crawl_timeout():
            await asyncio.sleep(0.04)
            async with exempt_crawl_timeout():
                await asyncio.sleep(0.04)
        await asyncio.sleep(0.1)

    crawler._run = run
    try:
        result = await crawler.run(_crawl_input())
        assert isinstance(result.debug_info.error, TimeoutError)
        assert not crawler._site_failure
        assert not any("Cannot change state" in line for line in probe.logs)
    finally:
        await probe.client.close()


@pytest.mark.asyncio
async def test_external_cancellation_still_cancels_exempt_wait(probe):
    crawler = DummyJavCrawler(probe.client)
    waiting = asyncio.Event()

    async def run(ctx):
        async with exempt_crawl_timeout():
            waiting.set()
            await asyncio.sleep(60)

    crawler._run = run
    task = asyncio.create_task(crawler.run(_crawl_input()))
    try:
        await waiting.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not crawler._site_failure
    finally:
        await probe.client.close()
