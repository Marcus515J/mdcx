import pytest

from mdcx.config.enums import FixedScrapingType, Website
from mdcx.config.models import Config, FieldConfig, FieldPriorityConfig
from mdcx.core.actor_quality import fallback_mgstage_actors, has_mgstage_age_marker, strip_mgstage_age_marker
from mdcx.core.file_crawler import FileScraper, ScrapeClassification
from mdcx.gen.field_enums import CrawlerResultFields
from mdcx.models.types import CrawlerDebugInfo, CrawlerInput, CrawlerResponse, CrawlerResult


class _RecordingCrawler:
    def __init__(self, site: Website, records: list[Website], data: CrawlerResult | None):
        self._site = site
        self._records = records
        self._data = data

    async def run(self, task_input: CrawlerInput) -> CrawlerResponse:
        self._records.append(self._site)
        return CrawlerResponse(
            debug_info=CrawlerDebugInfo(execution_time=0.01),
            data=self._data,
        )


class _RecordingProvider:
    def __init__(self, crawlers: dict[Website, _RecordingCrawler]):
        self._crawlers = crawlers

    async def get(self, site: Website):
        return self._crawlers[site]


def _make_input(number: str) -> CrawlerInput:
    task_input = CrawlerInput.empty()
    task_input.number = number
    return task_input


def _make_result(
    source: Website,
    *,
    title: str = "",
    actors: list[str] | None = None,
    all_actors: list[str] | None = None,
    score: str = "",
    score_max: str = "",
) -> CrawlerResult:
    res = CrawlerResult.empty()
    res.source = source.value
    res.external_id = f"{source.value}:test"
    res.title = title
    res.actors = list(actors or [])
    res.all_actors = list(all_actors or [])
    res.score = score
    res.score_max = score_max
    return res


def _make_suren_config() -> Config:
    config = Config()
    sites = [Website.MGSTAGE, Website.DMM, Website.AVBASE]
    config.website_suren = sites
    for field in CrawlerResultFields:
        config.field_configs[field] = FieldConfig(site_prority=[Website.MGSTAGE])
    config.field_configs[CrawlerResultFields.ACTORS] = FieldConfig(site_prority=sites)
    config.field_configs[CrawlerResultFields.ALL_ACTORS] = FieldConfig(site_prority=sites)
    config.field_configs[CrawlerResultFields.SCORE] = FieldConfig(site_prority=[Website.DMM])
    config.type_field_configs[FixedScrapingType.SUREN.value] = {
        CrawlerResultFields.ACTORS.value: FieldPriorityConfig(site_prority=sites),
        CrawlerResultFields.ALL_ACTORS.value: FieldPriorityConfig(site_prority=sites),
        CrawlerResultFields.SCORE.value: FieldPriorityConfig(site_prority=[Website.DMM]),
    }
    return config


def test_mgstage_age_marker_helpers():
    assert has_mgstage_age_marker("星野みく25歳会社員") is True
    assert has_mgstage_age_marker("星野みく 25 歳") is True
    assert has_mgstage_age_marker("白石ゆい") is False

    assert strip_mgstage_age_marker("星野みく25歳会社員") == "星野みく"
    assert strip_mgstage_age_marker("星野みく / 25歳会社員") == "星野みく"
    assert strip_mgstage_age_marker("25歳会社員") == ""

    assert fallback_mgstage_actors(["星野みく25歳会社員"]) == ["星野みく"]
    assert fallback_mgstage_actors(["25歳会社員"]) == []
    assert fallback_mgstage_actors(["未知演员25歳会社員"]) == []


@pytest.mark.asyncio
async def test_mgstage_aged_actor_uses_subsequent_already_fetched_site_without_new_requests():
    config = _make_suren_config()
    records: list[Website] = []
    # mgstage has age-marked actor and no score; dmm is fetched for score and has valid actor;
    # avbase is never needed by any field and must NOT be requested.
    provider = _RecordingProvider(
        {
            Website.MGSTAGE: _RecordingCrawler(
                Website.MGSTAGE,
                records,
                _make_result(
                    Website.MGSTAGE,
                    title="テスト作品",
                    actors=["星野みく25歳会社員"],
                    all_actors=["星野みく25歳会社員"],
                ),
            ),
            Website.DMM: _RecordingCrawler(
                Website.DMM,
                records,
                _make_result(
                    Website.DMM,
                    actors=["星野みく"],
                    all_actors=["星野みく"],
                    score="4.5",
                    score_max="5",
                ),
            ),
            Website.AVBASE: _RecordingCrawler(
                Website.AVBASE,
                records,
                _make_result(
                    Website.AVBASE,
                    actors=["別の名前"],
                    all_actors=["別の名前"],
                ),
            ),
        }
    )

    scraper = FileScraper(config, provider)
    classification = ScrapeClassification(
        FixedScrapingType.SUREN,
        "auto",
        sites=[Website.MGSTAGE, Website.DMM, Website.AVBASE],
    )
    res = await scraper._call_crawlers(_make_input("999TEST-001"), classification)

    assert res is not None
    assert res.actors == ["星野みく"]
    assert res.all_actors == ["星野みく"]
    assert res.field_sources[CrawlerResultFields.ACTORS] == Website.DMM.value
    assert res.field_sources[CrawlerResultFields.ALL_ACTORS] == Website.DMM.value
    assert res.actor_amazon == ["星野みく"]
    assert Website.AVBASE not in records


@pytest.mark.asyncio
async def test_mgstage_aged_actor_falls_back_to_name_before_age_when_no_subsequent_actor():
    config = _make_suren_config()
    records: list[Website] = []
    provider = _RecordingProvider(
        {
            Website.MGSTAGE: _RecordingCrawler(
                Website.MGSTAGE,
                records,
                _make_result(
                    Website.MGSTAGE,
                    title="テスト作品",
                    actors=["星野みく / 25歳会社員"],
                    all_actors=["星野みく / 25歳会社員"],
                ),
            ),
            Website.DMM: _RecordingCrawler(
                Website.DMM,
                records,
                _make_result(Website.DMM, score="4.5", score_max="5"),
            ),
            Website.AVBASE: _RecordingCrawler(
                Website.AVBASE,
                records,
                _make_result(Website.AVBASE, actors=["別の名前"], all_actors=["別の名前"]),
            ),
        }
    )

    scraper = FileScraper(config, provider)
    classification = ScrapeClassification(
        FixedScrapingType.SUREN,
        "auto",
        sites=[Website.MGSTAGE, Website.DMM, Website.AVBASE],
    )
    res = await scraper._call_crawlers(_make_input("999TEST-002"), classification)

    assert res is not None
    assert res.actors == ["星野みく"]
    assert res.all_actors == ["星野みく"]
    assert res.field_sources[CrawlerResultFields.ACTORS] == Website.MGSTAGE.value
    assert res.field_sources[CrawlerResultFields.ALL_ACTORS] == Website.MGSTAGE.value
    assert Website.AVBASE not in records


@pytest.mark.asyncio
async def test_mgstage_aged_actor_empty_before_age_becomes_no_valid_actor():
    config = _make_suren_config()
    records: list[Website] = []
    provider = _RecordingProvider(
        {
            Website.MGSTAGE: _RecordingCrawler(
                Website.MGSTAGE,
                records,
                _make_result(
                    Website.MGSTAGE,
                    title="テスト作品",
                    actors=["25歳会社員"],
                    all_actors=["25歳会社員"],
                ),
            ),
            Website.DMM: _RecordingCrawler(
                Website.DMM,
                records,
                _make_result(Website.DMM, score="4.0", score_max="5"),
            ),
        }
    )

    scraper = FileScraper(config, provider)
    classification = ScrapeClassification(
        FixedScrapingType.SUREN,
        "auto",
        sites=[Website.MGSTAGE, Website.DMM],
    )
    res = await scraper._call_crawlers(_make_input("999TEST-003"), classification)

    assert res is not None
    assert res.actors == []
    assert res.all_actors == []
    assert CrawlerResultFields.ACTORS not in res.field_sources
    assert CrawlerResultFields.ALL_ACTORS not in res.field_sources


@pytest.mark.asyncio
async def test_mgstage_actor_without_age_marker_is_unchanged():
    config = _make_suren_config()
    records: list[Website] = []
    provider = _RecordingProvider(
        {
            Website.MGSTAGE: _RecordingCrawler(
                Website.MGSTAGE,
                records,
                _make_result(
                    Website.MGSTAGE,
                    title="テスト作品",
                    actors=["白石ゆい"],
                    all_actors=["白石ゆい"],
                ),
            ),
            Website.DMM: _RecordingCrawler(
                Website.DMM,
                records,
                _make_result(
                    Website.DMM,
                    actors=["別の名前"],
                    all_actors=["別の名前"],
                    score="4.5",
                    score_max="5",
                ),
            ),
        }
    )

    scraper = FileScraper(config, provider)
    classification = ScrapeClassification(
        FixedScrapingType.SUREN,
        "auto",
        sites=[Website.MGSTAGE, Website.DMM],
    )
    res = await scraper._call_crawlers(_make_input("999TEST-004"), classification)

    assert res is not None
    assert res.actors == ["白石ゆい"]
    assert res.all_actors == ["白石ゆい"]
    assert res.field_sources[CrawlerResultFields.ACTORS] == Website.MGSTAGE.value
    assert res.field_sources[CrawlerResultFields.ALL_ACTORS] == Website.MGSTAGE.value


@pytest.mark.asyncio
async def test_youma_wuma_fc2_actor_behavior_unchanged():
    config = _make_suren_config()
    config.website_youma = [Website.MGSTAGE, Website.DMM]
    config.website_wuma = [Website.MGSTAGE, Website.DMM]
    config.website_fc2 = [Website.MGSTAGE, Website.DMM]
    for scraping_type in (FixedScrapingType.YOUMA, FixedScrapingType.WUMA, FixedScrapingType.FC2):
        config.type_field_configs[scraping_type.value] = {
            CrawlerResultFields.ACTORS.value: FieldPriorityConfig(site_prority=[Website.MGSTAGE, Website.DMM]),
            CrawlerResultFields.ALL_ACTORS.value: FieldPriorityConfig(site_prority=[Website.MGSTAGE, Website.DMM]),
            CrawlerResultFields.SCORE.value: FieldPriorityConfig(site_prority=[Website.DMM]),
        }
        records: list[Website] = []
        provider = _RecordingProvider(
            {
                Website.MGSTAGE: _RecordingCrawler(
                    Website.MGSTAGE,
                    records,
                    _make_result(
                        Website.MGSTAGE,
                        title="テスト作品",
                        actors=["星野みく25歳会社員"],
                        all_actors=["星野みく25歳会社員"],
                    ),
                ),
                Website.DMM: _RecordingCrawler(
                    Website.DMM,
                    records,
                    _make_result(
                        Website.DMM,
                        actors=["星野みく"],
                        all_actors=["星野みく"],
                        score="4.5",
                        score_max="5",
                    ),
                ),
            }
        )
        scraper = FileScraper(config, provider)
        classification = ScrapeClassification(
            scraping_type,
            "auto",
            sites=[Website.MGSTAGE, Website.DMM],
        )
        res = await scraper._call_crawlers(_make_input("999TEST-005"), classification)
        assert res is not None
        assert res.actors == ["星野みく25歳会社員"]
        assert res.all_actors == ["星野みく25歳会社員"]
