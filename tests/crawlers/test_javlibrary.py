import pytest

from mdcx.config.enums import Language, Website
from mdcx.config.manager import manager
from mdcx.config.models import Config, FieldConfig
from mdcx.core.file_crawler import FileScraper
from mdcx.crawlers.base import get_crawler
from mdcx.crawlers.javlibrary import JavlibraryCrawler
from mdcx.gen.field_enums import CrawlerResultFields
from mdcx.models.types import CrawlerInput


class FakeJavlibraryClient:
    async def get_text(self, url, **kwargs):
        if url == "https://www.javlibrary.com/ja/vl_searchbyid.php?keyword=FSDSS-200":
            return _search_html("/ja/?v=javtest200", "FSDSS-200 Japanese Title"), ""
        if url == "https://www.javlibrary.com/ja/?v=javtest200":
            return _detail_html("FSDSS-200 Japanese Title", "女優A"), ""
        if url == "https://www.javlibrary.com/cn/?v=javtest200":
            return _detail_html("FSDSS-200 中文标题", "演员A"), ""
        return None, f"unexpected url: {url}"


def _search_html(href: str, title: str) -> str:
    return f"""
    <html><body>
      <a href="{href}" title="{title}"></a>
    </body></html>
    """


def _detail_html(title: str, actor: str) -> str:
    return f"""
    <html><body>
      <div id="video_title"><h3><a>{title}</a></h3></div>
      <div id="video_id"><table><tr><td class="text">FSDSS-200</td></tr></table></div>
      <div id="video_cast"><table><tr><td class="text"><span><span class="star"><a>{actor}</a></span></span></td></tr></table></div>
      <img id="video_jacket_img" src="//img.example.test/cover.jpg" />
      <div id="video_genres"><table><tr><td class="text"><span><a>剧情</a></span></td></tr></table></div>
      <div id="video_date"><table><tr><td class="text">2026-04-03</td></tr></table></div>
      <div id="video_maker"><table><tr><td class="text"><span><a>制作商</a></span></td></tr></table></div>
      <div id="video_label"><table><tr><td class="text"><span><a>发行商</a></span></td></tr></table></div>
      <div id="video_length"><table><tr><td><span class="text">120</span></td></tr></table></div>
      <div id="video_review"><table><tr><td><span class="score">(4.20)</span></td></tr></table></div>
      <div id="video_director"><table><tr><td class="text"><span><a>导演A</a></span></td></tr></table></div>
      <a href="userswanted.php?mode=add">99</a>
    </body></html>
    """


@pytest.mark.asyncio
async def test_javlibrary_crawler_uses_one_jp_result_even_with_chinese_fields():
    manager.config.set_field_language(CrawlerResultFields.TITLE, Language.ZH_CN)
    crawler = JavlibraryCrawler(client=FakeJavlibraryClient(), base_url="https://www.javlibrary.com")
    res = await crawler.run(
        CrawlerInput(
            appoint_number="",
            appoint_url="",
            file_path=None,
            mosaic="",
            number="FSDSS-200",
            short_number="FSDSS-200",
            language=Language.ZH_CN,
            org_language=Language.ZH_CN,
        )
    )

    assert res.debug_info.error is None
    assert res.data is not None
    assert res.debug_info.search_urls == ["https://www.javlibrary.com/ja/vl_searchbyid.php?keyword=FSDSS-200"]
    assert res.debug_info.detail_urls == [
        "https://www.javlibrary.com/ja/?v=javtest200",
    ]
    assert res.data.source == "javlibrary"
    assert res.data.number == "FSDSS-200"
    assert res.data.title == "Japanese Title"
    assert res.data.originaltitle == "Japanese Title"
    assert res.data.actors == ["女優A"]
    assert res.data.tags == ["剧情"]
    assert res.data.release == "2026-04-03"
    assert res.data.year == "2026"
    assert res.data.runtime == "120"
    assert res.data.score == "4.20"
    assert res.data.directors == ["导演A"]
    assert res.data.studio == "制作商"
    assert res.data.publisher == "发行商"
    assert res.data.thumb == "https://img.example.test/cover.jpg"
    assert res.data.wanted == "99"


def test_javlibrary_crawler_is_registered():
    assert get_crawler(Website.JAVLIBRARY) is JavlibraryCrawler


@pytest.mark.asyncio
@pytest.mark.parametrize("redirected", [True, False])
@pytest.mark.parametrize("number", ["MTES-003", "MTES-004", "MEYD-849"])
async def test_javlibrary_reuses_result_across_all_field_languages(number, redirected):
    calls = []
    detail = _detail_html(f"{number} Sample", "女優A").replace("FSDSS-200", number)
    detail = detail.replace("<h3><a>", '<h3><a href="/ja/?v=javsample">')

    class Client:
        async def get_text(self, url, **kwargs):
            calls.append(url)
            if "vl_searchbyid" in url:
                return (detail if redirected else _search_html("/ja/?v=javsample", f"{number} Sample")), ""
            assert url == "https://www.javlibrary.com/ja/?v=javsample"
            return detail, ""

    crawler = JavlibraryCrawler(Client(), base_url="https://www.javlibrary.com")
    runs = []

    class Provider:
        async def get(self, site):
            runs.append(site)
            return crawler

    config = Config()
    for field in CrawlerResultFields:
        config.field_configs[field] = FieldConfig(site_prority=[Website.JAVLIBRARY])
    config.set_field_language(CrawlerResultFields.TITLE, Language.ZH_CN)
    config.set_field_language(CrawlerResultFields.ACTORS, Language.JP)
    config.set_field_language(CrawlerResultFields.TAGS, Language.ZH_TW)
    task_input = CrawlerInput.empty()
    task_input.number = number
    result = await FileScraper(config, Provider())._call_crawlers(task_input, [Website.JAVLIBRARY])

    assert result is not None
    assert result.actors == ["女優A"]
    assert result.originaltitle == "Sample"
    assert result.title == "Sample"
    assert result.score == "4.20"
    assert result.wanted == "99"
    assert result.thumb == "https://img.example.test/cover.jpg"
    assert result.field_sources[CrawlerResultFields.ACTORS] == "javlibrary"
    assert runs == [Website.JAVLIBRARY]
    assert len(calls) == (1 if redirected else 2)
    assert all("/ja/" in url for url in calls)


@pytest.mark.asyncio
async def test_javlibrary_failed_search_is_not_repeated_for_other_languages():
    calls = []

    class Client:
        async def get_text(self, url, **kwargs):
            calls.append(url)
            return "<html>No matching video</html>", ""

    crawler = JavlibraryCrawler(Client(), base_url="https://www.javlibrary.com")

    class Provider:
        async def get(self, site):
            return crawler

    config = Config()
    for field in CrawlerResultFields:
        config.field_configs[field] = FieldConfig(site_prority=[Website.JAVLIBRARY], language=Language.ZH_CN)
    config.set_field_language(CrawlerResultFields.ACTORS, Language.JP)
    task_input = CrawlerInput.empty()
    task_input.number = "MDON-078"
    result = await FileScraper(config, Provider())._call_crawlers(task_input, [Website.JAVLIBRARY])
    assert result is None
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_javlibrary_rejects_redirect_to_different_video():
    class Client:
        async def get_text(self, url, **kwargs):
            return _detail_html("FSDSS-200 Sample", "女優A"), ""

    task_input = CrawlerInput.empty()
    task_input.number = "FSDSS-201"
    res = await JavlibraryCrawler(Client(), base_url="https://www.javlibrary.com").run(task_input)
    assert res.data is None
    assert "番号不匹配" in str(res.debug_info.error)
