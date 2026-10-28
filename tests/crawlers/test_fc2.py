import pytest
from lxml import etree

from mdcx.config.enums import Language, Website
from mdcx.config.manager import manager
from mdcx.config.models import Config
from mdcx.core.file_crawler import FileScraper
from mdcx.crawlers.fc2 import Fc2Crawler, getOutline
from mdcx.gen.field_enums import CrawlerResultFields
from mdcx.manual import ManualConfig
from mdcx.models.types import CrawlerDebugInfo, CrawlerInput, CrawlerResponse, CrawlerResult


class FakeFc2Client:
    async def get_text(self, url, **kwargs):
        if url == "https://adult.contents.fc2.com/article/1723984/":
            return (
                """
                <html>
                  <head>
                    <title>FC2 sample</title>
                    <script type="application/ld+json">{"aggregateRating":{"ratingValue":"4.5"}}</script>
                  </head>
                  <body>
                    <section class="items_article_wrapper"></section>
                    <div data-section="userInfo"><h3><span></span> Sample Title</h3></div>
                    <ul class="items_article_SampleImagesArea">
                      <li><a href="//example.test/sample1.jpg"></a></li>
                    </ul>
                    <div class="items_article_MainitemThumb"><span><img src="//example.test/thumb.jpg" /></span></div>
                    <div class="items_article_Releasedate"><p>2026/04/03</p></div>
                    <div class="items_article_headerInfo"><ul><li><a>分类</a></li><li><a>卖家</a></li></ul></div>
                    <a class="tag tagTag">無修正</a><a class="tag tagTag">素人</a>
                    <section class="items_article_Contents">商品説明 紹介文</section>
                    <p class="items_article_info">01:02:03</p>
                  </body>
                </html>
                """,
                "",
            )
        if url == "https://adult.contents.fc2.com/api/v2/videos/1723984/sample":
            return '{"path":"https://example.test/sample.mp4?mid=token"}', ""
        return None, f"unexpected url: {url}"


@pytest.mark.asyncio
async def test_fc2_crawler_maps_detail_and_sample_api(monkeypatch):
    monkeypatch.setattr(manager.config, "fields_rule", "")
    crawler = Fc2Crawler(client=FakeFc2Client())
    res = await crawler.run(
        CrawlerInput(
            appoint_number="",
            appoint_url="",
            file_path=None,
            mosaic="",
            number="FC2-1723984",
            short_number="FC2-1723984",
            language=Language.UNDEFINED,
            org_language=Language.UNDEFINED,
        )
    )

    assert res.debug_info.error is None
    assert res.data is not None
    assert res.data.number == "FC2-1723984"
    assert res.data.title == "Sample Title"
    assert res.data.tags == ["素人"]
    assert res.data.release == "2026-04-03"
    assert res.data.year == "2026"
    assert res.data.runtime == "62"
    assert res.data.score == "4.5"
    assert res.data.trailer == "https://example.test/sample.mp4?mid=token"
    assert res.data.source == "fc2"


@pytest.mark.parametrize(
    "placeholder", ["看更多", "看更多内容", "看更多內容", "查看更多内容", "もっと見る", "See more"]
)
@pytest.mark.parametrize("body", ["", "本片的有效简介"])
def test_fc2_outline_discards_more_link_and_preserves_real_text(placeholder, body):
    html = etree.HTML(
        f'<section class="items_article_Contents"><h2>商品説明</h2>'
        f"<p>{body}</p><a> {placeholder} </a><script>noise</script></section>"
    )
    assert getOutline(html) == body


@pytest.mark.asyncio
async def test_fc2_placeholder_allows_both_plot_fields_to_use_next_source(monkeypatch):
    class PlaceholderClient(FakeFc2Client):
        async def get_text(self, url, **kwargs):
            text, error = await super().get_text(url, **kwargs)
            return text.replace("商品説明 紹介文", "看更多") if text else text, error

    official = Fc2Crawler(PlaceholderClient())
    calls = []

    class FallbackCrawler:
        async def run(self, task_input):
            calls.append("fc2hub")
            data = CrawlerResult.empty()
            data.source = "fc2hub"
            data.outline = data.originalplot = "后续来源的有效简介"
            return CrawlerResponse(data=data, debug_info=CrawlerDebugInfo(execution_time=0.01))

    class Provider:
        async def get(self, site):
            return official if site == Website.FC2 else FallbackCrawler()

    monkeypatch.setattr(ManualConfig, "REDUCED_FIELDS", (CrawlerResultFields.OUTLINE, CrawlerResultFields.ORIGINALPLOT))
    config = Config(
        field_configs={
            field: {"site_prority": [Website.FC2, Website.FC2HUB]}
            for field in [CrawlerResultFields.OUTLINE, CrawlerResultFields.ORIGINALPLOT]
        }
    )
    task_input = CrawlerInput.empty()
    task_input.number = "FC2-1723984"
    result = await FileScraper(config, Provider())._call_crawlers(task_input, [Website.FC2, Website.FC2HUB])
    assert result.outline == result.originalplot == "后续来源的有效简介"
    assert result.field_sources[CrawlerResultFields.OUTLINE] == "fc2hub"
    assert result.field_sources[CrawlerResultFields.ORIGINALPLOT] == "fc2hub"
    assert calls == ["fc2hub"]
