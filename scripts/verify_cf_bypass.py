"""Task C acceptance with real HTTP and real 60/90/100/120-second waits.

Run from the repository root: python -u -m scripts.verify_cf_bypass
No NAS, external sites, or user media files are contacted.
"""

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import patch

from mdcx.core.network_check import (
    NetworkCheckSpec,
    NetworkCheckStatus,
    run_network_check,
    run_network_check_item,
)
from tests.cf_fake_server import FakeBypassServer, ProbeCrawler, Scenario
from tests.test_crawl_circuit import crawl_input


def log(message):
    print(f"{time.strftime('%H:%M:%S')} {message}", flush=True)


async def timed(coro):
    start = time.monotonic()
    result = await coro
    return result, round(time.monotonic() - start, 3)


async def main():
    results = {}
    log("BEGIN real-time acceptance: six cold sites, each /html delay=60s")
    async with FakeBypassServer(log=log) as server:
        for i in range(6):
            server.scenarios[f"cold{i}.test"].html_delay = 60
        server.scenarios["slow.test"] = Scenario(direct_status=200, direct_delay=130)
        client = server.client()
        cap_client = server.client(timeout=200, cf_bypass_url="")
        fake_manager = SimpleNamespace(config=SimpleNamespace(cf_bypass_url=server.base, timeout=10))

        async def specs():
            return [
                NetworkCheckSpec(
                    name=f"cold{i}", group="刮削站点", url=server.url(f"cold{i}.test"), enable_cf_bypass=True
                )
                for i in range(6)
            ]

        with (
            patch("mdcx.core.network_check._manager", lambda: fake_manager),
            patch("mdcx.core.network_check.build_network_check_specs", specs),
        ):
            check_task = asyncio.create_task(
                timed(run_network_check(client=client, concurrency=6, emit_header=False, progress=log))
            )
            async with asyncio.timeout(10):
                while server.count("html", "cold0.test") == 0:
                    await asyncio.sleep(0.01)
            await asyncio.sleep(0.2)
            first = ProbeCrawler(client, server.url("cold0.test").rstrip("/"))
            last = ProbeCrawler(client, server.url("cold5.test").rstrip("/"))
            capped = ProbeCrawler(cap_client, server.url("slow.test").rstrip("/"))
            scraped = await asyncio.gather(
                timed(first.run(crawl_input("FIRST"))),
                timed(last.run(crawl_input("LAST"))),
                timed(capped.run(crawl_input("CAP"))),
            )
            assert scraped[0][0].data is not None and 59 <= scraped[0][1] < 70
            assert isinstance(scraped[1][0].debug_info.error, TimeoutError)
            assert isinstance(scraped[2][0].debug_info.error, TimeoutError)
            assert all(119 <= scraped[i][1] < 125 for i in [1, 2])
            results["scrape_wait_same_first_host_s"] = scraped[0][1]
            results["scrape_wait_same_last_host_s"] = scraped[1][1]
            results["total_cap_s"] = scraped[2][1]
            before = len(server.events)
            await capped.run(crawl_input("NEXT"))
            await last.run(crawl_input("NEXT"))
            assert len(server.events) == before
            checks, elapsed = await check_task
            assert all(c.status == NetworkCheckStatus.OK for c in checks)
            assert 359 <= elapsed < 380
            assert server.html_peak == 1
            assert all(server.count("html", f"cold{i}.test") == 1 for i in range(6))
            assert (await first.run(crawl_input("WARM"))).data is not None
            assert server.count("html", "cold0.test") == 1
            results["six_detection_total_s"] = elapsed
            results["html_peak"] = server.html_peak
            results["html_events"] = [e for e in server.events if e["kind"] == "html"]
            log(f"PASS six cold checks, 60s success, cache, 120s cap: {json.dumps(results)}")
        await client.close()
        await cap_client.close()

    log("BEGIN /html delay=100s, client default=90s, retry setting=5")
    async with FakeBypassServer(log=log) as server:
        server.scenarios["cold0.test"].html_delay = 100
        client = server.client()
        fake_manager = SimpleNamespace(config=SimpleNamespace(cf_bypass_url=server.base, timeout=10))
        with patch("mdcx.core.network_check._manager", lambda: fake_manager):
            spec = NetworkCheckSpec(name="100s", group="刮削站点", url=server.url("cold0.test"), enable_cf_bypass=True)
            checked, elapsed = await timed(run_network_check_item(spec, client=client))
        assert checked.status == NetworkCheckStatus.FAILED
        assert 89 <= elapsed < 95
        assert server.count("html", "cold0.test") == 1
        results["html_100s_failure_at_s"] = elapsed
        # The fixture deliberately continues work after the client disconnects.
        while server.html_active:
            await asyncio.sleep(0.1)
        assert server.count("html", "cold0.test") == 1
        crawler = ProbeCrawler(client, server.url("cold0.test").rstrip("/"))
        assert (await crawler.run(crawl_input("AFTER_CHECK"))).data is not None
        assert not crawler._site_failure
        assert server.count("html", "cold0.test") == 1
        results["failed_detection_does_not_trip_scrape"] = True
        log(f"PASS 100s delay fails at {elapsed}s, /html count=1; no second round; scrape remains eligible")
        await client.close()
    print("RESULT " + json.dumps(results, ensure_ascii=False), flush=True)
    log("PASS real-time acceptance complete")


if __name__ == "__main__":
    asyncio.run(main())
