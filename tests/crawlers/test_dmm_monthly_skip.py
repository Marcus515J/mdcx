"""DMM 详情阶段不再请求 monthly 候选，也不因此记 REQUEST_ERROR。"""

import pytest

from mdcx.crawlers.base.types import CrawlerData
from mdcx.crawlers.dmm_new import Category, DMMContext, DmmCrawler
from mdcx.crawlers.dmm_new.parsers import parse_category
from mdcx.models.crawl_status import CrawlStatus, observations, record_request_error
from mdcx.models.types import CrawlerInput
from mdcx.web_async import AsyncWebClient


@pytest.mark.asyncio
async def test_detail_skips_monthly_candidates_without_request_error(monkeypatch: pytest.MonkeyPatch):
    crawler = DmmCrawler(client=AsyncWebClient(timeout=1))
    ctx = DMMContext(input=CrawlerInput.empty())
    mono_url = "https://www.dmm.co.jp/mono/dvd/-/detail/=/cid=ipzz00841/"
    monthly_url = "https://www.dmm.co.jp/monthly/premium/-/detail/=/cid=ipzz00841/"
    assert parse_category(monthly_url) == Category.MONTHLY

    requested: list[str] = []
    issues = []
    token = observations.set(issues)

    async def fake_fetch_and_parse(inner_ctx, url: str, parser):
        requested.append(url)
        if parse_category(url) == Category.MONTHLY:
            # 真实 fetch_and_parse 请求失败时会这样记；monthly 一旦被请求，本测试应失败
            record_request_error("HTTP 503")
            return CrawlerData()
        return CrawlerData(title="mono title", external_id=url)

    async def fake_sanitize_candidate_images(inner_ctx, category, url: str, item: CrawlerData):
        return item

    async def fake_finalize_result_images(inner_ctx, item, *, label: str, validate_thumb: bool):
        return item

    monkeypatch.setattr(crawler, "fetch_and_parse", fake_fetch_and_parse)
    monkeypatch.setattr(crawler, "_sanitize_candidate_images", fake_sanitize_candidate_images)
    monkeypatch.setattr(crawler, "_finalize_result_images", fake_finalize_result_images)

    try:
        result = await crawler._detail(ctx, [mono_url, monthly_url])
    finally:
        observations.reset(token)

    assert requested == [mono_url]
    assert result is not None and result.title == "mono title"
    assert all(issue.status != CrawlStatus.REQUEST_ERROR for issue in issues)
