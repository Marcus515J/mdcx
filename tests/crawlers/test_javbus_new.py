import pytest

from mdcx.config.enums import Language
from mdcx.crawlers.javbus import JavbusCrawler
from mdcx.models.types import CrawlerInput


class FakeJavbusClient:
    async def get_text(self, url, **kwargs):
        assert url == "https://www.javbus.com/SSIS-243"
        assert "headers" in kwargs
        return (
            """
            <html>
              <body>
                <li class="active"><a>有碼</a></li>
                <h3>SSIS-243 Sample Title</h3>
                <p><span class="header">識別碼:</span><span>SSIS-243</span></p>
                <p><span class="header">發行日期:</span>2026/04/03</p>
                <p><span class="header">長度:</span>120分鐘</p>
                <a class="bigImage" href="/pics/cover/ssis243_b.jpg"></a>
                <div class="star-name"><a>演员A</a></div>
                <span class="genre"><label><a href="/genre/a">剧情</a></label></span>
                <a href="/studio/abc">制作商</a>
                <a href="/label/abc">发行商</a>
                <a href="/director/abc">导演</a>
                <a href="/series/abc">系列</a>
                <div id="sample-waterfall"><a href="/sample1.jpg"></a></div>
              </body>
            </html>
            """,
            "",
        )


@pytest.mark.asyncio
async def test_javbus_crawler_maps_detail_page():
    crawler = JavbusCrawler(client=FakeJavbusClient(), base_url="https://www.javbus.com")
    res = await crawler.run(
        CrawlerInput(
            appoint_number="",
            appoint_url="",
            file_path=None,
            mosaic="",
            number="SSIS-243",
            short_number="SSIS-243",
            language=Language.UNDEFINED,
            org_language=Language.UNDEFINED,
        )
    )

    assert res.debug_info.error is None
    assert res.data is not None
    assert res.data.number == "SSIS-243"
    assert res.data.title == "Sample Title"
    assert res.data.actors == ["演员A"]
    assert res.data.tags == ["剧情"]
    assert res.data.release == "2026-04-03"
    assert res.data.runtime == "120"
    assert res.data.studio == "制作商"
    assert res.data.publisher == "发行商"
    assert res.data.directors == ["导演"]
    assert res.data.series == "系列"
    assert res.data.source == "javbus"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("number", "mosaic", "search_path"),
    [
        ("HEYZO-3640", "无码", "/uncensored/search/HEYZO-3640&type=0&parent=uc"),
        ("300MIUM-1369", "有码", "/search/300MIUM-1369&type=&parent=ce"),
        ("SERO-0124", "有码", "/search/SERO-0124&type=&parent=ce"),
    ],
)
async def test_javbus_404_search_initializes_urls_and_uses_correct_section(number, mosaic, search_path):
    calls = []
    detail_url = f"https://www.javbus.com/{number}_1"

    class Client:
        async def get_text(self, url, **kwargs):
            calls.append(url)
            if url == f"https://www.javbus.com/{number}":
                return None, "404 Not Found"
            if url == "https://www.javbus.com" + search_path:
                return f'<a class="movie-box" href="{detail_url}"></a>', ""
            assert url == detail_url
            return (
                f'<html><li class="active"><a>{"無碼" if mosaic == "无码" else "有碼"}</a></li><h3>{number} Sample</h3></html>',
                "",
            )

    task_input = CrawlerInput.empty()
    task_input.number = number
    task_input.mosaic = mosaic
    res = await JavbusCrawler(Client(), base_url="https://www.javbus.com").run(task_input)

    assert res.debug_info.error is None
    assert res.data is not None
    assert res.data.mosaic == mosaic
    assert res.debug_info.search_urls == ["https://www.javbus.com" + search_path]
    assert res.debug_info.detail_urls == [detail_url]
    assert len(calls) == 3
