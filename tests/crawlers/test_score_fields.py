import pytest
from lxml import etree
from parsel import Selector

from mdcx.config.enums import Language, Website
from mdcx.config.models import Config, FieldConfig
from mdcx.core.file_crawler import FileScraper
from mdcx.crawlers.dmm_new.parsers import DigitalParser
from mdcx.crawlers.dmm_new.tv import ReviewSummary
from mdcx.crawlers.fc2 import getScore, getScoreInfo
from mdcx.crawlers.javdb_new import Parser as JavdbParser
from mdcx.crawlers.javlibrary import JavlibraryCrawler
from mdcx.gen.field_enums import CrawlerResultFields
from mdcx.models.types import CrawlerInput, score_to_10
from tests.crawlers.test_javlibrary import FakeJavlibraryClient, _detail_html


def _html(content: str):
    return etree.fromstring(f"<html><body>{content}</body></html>", etree.HTMLParser())


def _ld_json_script(payload: str) -> str:
    return f'<script type="application/ld+json">{payload}</script>'


def test_fc2_score_info_with_rating_count_and_best_rating():
    html = _html(
        _ld_json_script(
            '{"@type":"Product","aggregateRating":{"@type":"AggregateRating","bestRating":5,"worstRating":1,"ratingCount":799,"ratingValue":4.5}}'
        )
    )
    assert getScoreInfo(html) == ("4.5", "5", "799")
    assert getScore(html) == "4.5"


def test_fc2_score_info_defaults_best_rating_to_5():
    # schema.org: bestRating 缺省时按 5 处理
    html = _html(_ld_json_script('{"aggregateRating":{"ratingValue":4.0,"ratingCount":12}}'))
    assert getScoreInfo(html) == ("4.0", "5", "12")


def test_fc2_score_info_missing_count_stays_empty():
    html = _html(_ld_json_script('{"aggregateRating":{"ratingValue":4.0}}'))
    assert getScoreInfo(html) == ("4.0", "5", "")


def test_fc2_score_info_no_aggregate_rating():
    html = _html(_ld_json_script('{"@type":"Product","name":"x"}'))
    assert getScoreInfo(html) == ("", "", "")


@pytest.mark.asyncio
async def test_javdb_score_max_and_count():
    html = Selector("<html><body><div><span class='score-stars'></span>4.36分, 由 1,234 人評價</div></body></html>")
    parser = JavdbParser()
    assert await parser.score(None, html) == "4.36"
    assert await parser.score_max(None, html) == "5"
    assert await parser.score_count(None, html) == "1234"


@pytest.mark.asyncio
async def test_javdb_score_count_unknown_stays_empty():
    html = Selector("<html><body><div><span class='score-stars'></span>4.36分</div></body></html>")
    parser = JavdbParser()
    assert await parser.score_count(None, html) == ""
    assert await parser.score_max(None, html) == "5"


def test_dmm_tv_review_summary_keeps_missing_distinct_from_zero():
    empty = ReviewSummary()
    assert empty.averagePoint is None
    assert empty.reviewerCount is None
    filled = ReviewSummary(averagePoint=4.5, reviewerCount=87)
    assert filled.averagePoint == 4.5
    assert filled.reviewerCount == 87


@pytest.mark.asyncio
async def test_dmm_digital_parser_json_ld_rating_count():
    html = Selector(
        "<html><head>"
        + _ld_json_script(
            '{"name":"t","aggregateRating":{"@type":"AggregateRating","ratingValue":4.21,"bestRating":5,"ratingCount":321}}'
        )
        + "</head><body></body></html>"
    )
    parser = DigitalParser()
    data = await parser.parse(None, html)
    assert data.score == "4.21"
    assert data.score_max == "5"
    assert data.score_count == "321"


@pytest.mark.asyncio
async def test_javlibrary_result_carries_score_max():
    crawler = JavlibraryCrawler(client=FakeJavlibraryClient(), base_url="https://www.javlibrary.com")
    res = await crawler.run(
        CrawlerInput(
            appoint_number="",
            appoint_url="",
            file_path=None,
            mosaic="",
            number="FSDSS-200",
            short_number="FSDSS-200",
            language=Language.JP,
            org_language=Language.JP,
        )
    )
    assert res.data is not None
    assert res.data.score == "4.20"
    assert res.data.score_max == "10"
    assert res.data.score_count == ""
    assert res.data.wanted == "99"
    assert score_to_10(res.data.score, res.data.score_max) == "4.2"


@pytest.mark.asyncio
async def test_javlibrary_detail_score_10_scale_conversion():
    detail_860 = _detail_html("FSDSS-200 Japanese Title", "女優A").replace("(4.20)", "(8.60)")

    class Client860:
        async def get_text(self, url, **kwargs):
            return detail_860, ""

    crawler = JavlibraryCrawler(client=Client860(), base_url="https://www.javlibrary.com")
    task_input = CrawlerInput.empty()
    task_input.number = "FSDSS-200"
    task_input.appoint_url = "https://www.javlibrary.com/ja/?v=javtest200"
    res = await crawler.run(task_input)
    assert res.data is not None
    assert res.data.score == "8.60"
    assert res.data.score_max == "10"
    assert score_to_10(res.data.score, res.data.score_max) == "8.6"


@pytest.mark.asyncio
async def test_reduce_copies_same_source_score_fields_and_logs_summary():
    crawler = JavlibraryCrawler(client=FakeJavlibraryClient(), base_url="https://www.javlibrary.com")

    class Provider:
        async def get(self, site):
            return crawler

    config = Config()
    for field in CrawlerResultFields:
        config.field_configs[field] = FieldConfig(site_prority=[Website.JAVLIBRARY])

    task_input = CrawlerInput.empty()
    task_input.number = "FSDSS-200"
    result = await FileScraper(config, Provider())._call_crawlers(task_input, [Website.JAVLIBRARY])

    assert result is not None
    assert result.score == "4.20"
    assert result.score_max == "10"
    assert result.score_count == ""
    assert result.field_sources[CrawlerResultFields.SCORE] == "javlibrary"
    assert "📊 评分汇总" in result.field_log
    assert "javlibrary" in result.field_log
    assert "评分人数 未知" in result.field_log
    assert "想看人数 99" in result.field_log
    assert "rating(10分制) 4.2" in result.field_log
