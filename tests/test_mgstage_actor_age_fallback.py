from pathlib import Path
from types import SimpleNamespace

import pytest

from mdcx.config.enums import FixedScrapingType, Website
from mdcx.config.models import Config, FieldConfig, FieldPriorityConfig
from mdcx.core.actor_quality import is_pure_suren_actor, valid_suren_actor_names
from mdcx.core.file_crawler import FileScraper, ScrapeClassification
from mdcx.core.scrape_quality import QualityDeferred, QualityHeld, missing_required
from mdcx.gen.field_enums import CrawlerResultFields
from mdcx.models.crawl_status import BatchDiagnostics, CrawlStatus, batch_diagnostics
from mdcx.models.enums import FileMode
from mdcx.models.flags import Flags
from mdcx.models.types import CrawlerDebugInfo, CrawlerInput, CrawlerResponse, CrawlerResult, FileInfo
from mdcx.web_async import AsyncWebClient
from tests.crawlers.test_javlibrary_429_backoff import FakeResponse


class _RecordingCrawler:
    def __init__(self, site: Website, records: list[Website], data: CrawlerResult | None):
        self._site = site
        self._records = records
        self._data = data

    def is_stopped(self) -> bool:
        return False

    def reset_wall_timeout(self, _number: str) -> None:
        return None

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
    thumb: str = "",
    score: str = "",
    score_max: str = "",
) -> CrawlerResult:
    res = CrawlerResult.empty()
    res.source = source.value
    res.external_id = f"{source.value}:test"
    res.title = title
    res.actors = list(actors or [])
    res.all_actors = list(all_actors or [])
    res.thumb = thumb
    res.score = score
    res.score_max = score_max
    return res


def _make_suren_config(sites: list[Website] | None = None, score_sites: list[Website] | None = None) -> Config:
    config = Config()
    actor_sites = sites or [Website.MGSTAGE, Website.DMM, Website.AVBASE]
    score_priority = score_sites or [Website.DMM]
    config.fixed_scraping_type = FixedScrapingType.SUREN
    config.website_suren = actor_sites
    for field in CrawlerResultFields:
        config.field_configs[field] = FieldConfig(site_prority=[actor_sites[0]])
    config.field_configs[CrawlerResultFields.ACTORS] = FieldConfig(site_prority=actor_sites)
    config.field_configs[CrawlerResultFields.ALL_ACTORS] = FieldConfig(site_prority=actor_sites)
    config.field_configs[CrawlerResultFields.SCORE] = FieldConfig(site_prority=score_priority)
    config.type_field_configs[FixedScrapingType.SUREN.value] = {
        CrawlerResultFields.ACTORS.value: FieldPriorityConfig(site_prority=actor_sites),
        CrawlerResultFields.ALL_ACTORS.value: FieldPriorityConfig(site_prority=actor_sites),
        CrawlerResultFields.SCORE.value: FieldPriorityConfig(site_prority=score_priority),
    }
    return config


def test_suren_pure_actor_validation_rules():
    assert is_pure_suren_actor("白石ゆい") is True
    assert is_pure_suren_actor("桜庭テスト") is True
    assert is_pure_suren_actor("千歳テスト") is True
    assert is_pure_suren_actor("ちゃんテスト") is True
    assert is_pure_suren_actor("レイナ・サンプル") is True
    assert is_pure_suren_actor("Sample Name") is True
    assert is_pure_suren_actor("SAMPLEOL") is True
    assert is_pure_suren_actor("TESTCA") is True

    # Age, honorifics, occupations/identities, brackets, and extra symbols are rejected.
    assert is_pure_suren_actor("桜庭テスト25歳会社員") is False
    assert is_pure_suren_actor("桜庭テストさん27歳AV女優") is False
    assert is_pure_suren_actor("桜庭テスト28歳食品メーカー勤務Webデザイナー") is False
    assert is_pure_suren_actor("桜庭テスト32歳ショークラブダンサー") is False
    assert is_pure_suren_actor("桜庭テスト19歳大学生") is False
    assert is_pure_suren_actor("桜庭テスト22歳セラピスト") is False
    assert is_pure_suren_actor("桜庭テスト25歳歯科助手") is False
    assert is_pure_suren_actor("桜庭テストさん") is False
    assert is_pure_suren_actor("桜庭テストちゃん") is False
    assert is_pure_suren_actor("桜庭テストくん") is False
    assert is_pure_suren_actor("桜庭テスト様") is False
    assert is_pure_suren_actor("桜庭テストサン") is False
    assert is_pure_suren_actor("桜庭テスト会社員") is False
    assert is_pure_suren_actor("桜庭テスト（仮）") is False
    assert is_pure_suren_actor("桜庭テスト(25)") is False
    assert is_pure_suren_actor("桜庭テスト★") is False
    assert is_pure_suren_actor("桜庭テスト×") is False

    # Contaminated multi-entry lists are rejected without trimming/cutting.
    assert valid_suren_actor_names(["桜庭テスト", "25歳会社員"]) == []
    assert valid_suren_actor_names(["桜庭テスト", "白石ゆいさん"]) == []
    assert valid_suren_actor_names(["桜庭テスト", "未知演员"]) == ["桜庭テスト"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "impure_actor",
    ["桜庭テスト25歳会社員", "桜庭テストさん", "桜庭テスト大学生", "桜庭テスト（仮）"],
)
async def test_suren_impure_primary_actor_uses_subsequent_fetched_site_without_new_requests(impure_actor: str):
    config = _make_suren_config()
    records: list[Website] = []
    # mgstage has impure actor and no score; dmm is fetched for score and has pure actor;
    # avbase is never needed by any field and must NOT be requested.
    provider = _RecordingProvider(
        {
            Website.MGSTAGE: _RecordingCrawler(
                Website.MGSTAGE,
                records,
                _make_result(
                    Website.MGSTAGE,
                    title="テスト作品",
                    actors=[impure_actor],
                    all_actors=[impure_actor],
                    thumb="https://example.test/thumb.jpg",
                ),
            ),
            Website.DMM: _RecordingCrawler(
                Website.DMM,
                records,
                _make_result(
                    Website.DMM,
                    actors=["桜庭テスト"],
                    all_actors=["桜庭テスト"],
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
    assert res.actors == ["桜庭テスト"]
    assert res.all_actors == ["桜庭テスト"]
    assert res.field_sources[CrawlerResultFields.ACTORS] == Website.DMM.value
    assert res.field_sources[CrawlerResultFields.ALL_ACTORS] == Website.DMM.value
    assert res.actor_amazon == ["桜庭テスト"]
    assert Website.AVBASE not in records
    assert "跳过非纯演员名站点 (mgstage)，改取已抓站点 dmm" in res.field_log


@pytest.mark.asyncio
async def test_suren_skips_multiple_impure_sites_regardless_of_site_name():
    sites = [Website.MGSTAGE, Website.MMTV, Website.JAVDB]
    config = _make_suren_config(sites=sites, score_sites=[Website.MMTV, Website.JAVDB])
    config.field_configs[CrawlerResultFields.DIRECTORS] = FieldConfig(site_prority=sites)
    config.type_field_configs[FixedScrapingType.SUREN.value][CrawlerResultFields.DIRECTORS.value] = FieldPriorityConfig(
        site_prority=sites
    )
    records: list[Website] = []
    # mgstage has age+job, 7mmtv has honorific, javdb (fetched via directors chain) has pure name.
    provider = _RecordingProvider(
        {
            Website.MGSTAGE: _RecordingCrawler(
                Website.MGSTAGE,
                records,
                _make_result(
                    Website.MGSTAGE,
                    title="テスト作品",
                    actors=["桜庭テスト25歳会社員"],
                    all_actors=["桜庭テスト25歳会社員"],
                    thumb="https://example.test/thumb.jpg",
                ),
            ),
            Website.MMTV: _RecordingCrawler(
                Website.MMTV,
                records,
                _make_result(
                    Website.MMTV,
                    actors=["桜庭テストさん"],
                    all_actors=["桜庭テストさん"],
                ),
            ),
            Website.JAVDB: _RecordingCrawler(
                Website.JAVDB,
                records,
                _make_result(
                    Website.JAVDB,
                    actors=["桜庭テスト"],
                    all_actors=["桜庭テスト"],
                    score="4.2",
                    score_max="5",
                ),
            ),
        }
    )

    scraper = FileScraper(config, provider)
    classification = ScrapeClassification(FixedScrapingType.SUREN, "auto", sites=sites)
    res = await scraper._call_crawlers(_make_input("999TEST-002"), classification)

    assert res is not None
    assert res.actors == ["桜庭テスト"]
    assert res.all_actors == ["桜庭テスト"]
    assert res.field_sources[CrawlerResultFields.ACTORS] == Website.JAVDB.value
    assert res.field_sources[CrawlerResultFields.ALL_ACTORS] == Website.JAVDB.value
    assert "跳过非纯演员名站点 (mgstage -> 7mmtv)，改取已抓站点 javdb" in res.field_log
    assert not any(report.has_error for report in scraper.reports)


@pytest.mark.asyncio
async def test_suren_non_mgstage_impure_actor_is_also_skipped():
    sites = [Website.MMTV, Website.JAVDB]
    config = _make_suren_config(sites=sites, score_sites=[Website.JAVDB])
    records: list[Website] = []
    provider = _RecordingProvider(
        {
            Website.MMTV: _RecordingCrawler(
                Website.MMTV,
                records,
                _make_result(
                    Website.MMTV,
                    title="テスト作品",
                    actors=["白石ゆいさん"],
                    all_actors=["白石ゆいさん"],
                    thumb="https://example.test/thumb.jpg",
                ),
            ),
            Website.JAVDB: _RecordingCrawler(
                Website.JAVDB,
                records,
                _make_result(
                    Website.JAVDB,
                    actors=["白石ゆい"],
                    all_actors=["白石ゆい"],
                    score="4.0",
                    score_max="5",
                ),
            ),
        }
    )

    scraper = FileScraper(config, provider)
    classification = ScrapeClassification(FixedScrapingType.SUREN, "auto", sites=sites)
    res = await scraper._call_crawlers(_make_input("999TEST-003"), classification)

    assert res is not None
    assert res.actors == ["白石ゆい"]
    assert res.all_actors == ["白石ゆい"]
    assert res.field_sources[CrawlerResultFields.ACTORS] == Website.JAVDB.value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "primary_actors,secondary_actors",
    [
        (["桜庭テスト25歳会社員"], ["桜庭テストさん"]),
        ([], []),
    ],
)
async def test_suren_no_pure_actor_defers_once_then_holds_without_ban_counting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    primary_actors: list[str],
    secondary_actors: list[str],
):
    from mdcx.core import scraper as scraper_module

    sites = [Website.MGSTAGE, Website.MMTV]
    config = _make_suren_config(sites=sites, score_sites=[Website.MMTV])
    monkeypatch.setattr(scraper_module, "manager", SimpleNamespace(config=config))
    Flags.reset()
    scraper_module.signal.stop = False

    movie_path = tmp_path / "999TEST-004.mp4"
    movie_path.write_bytes(b"original")
    info = FileInfo.empty()
    info.number = "999TEST-004"
    info.file_path = movie_path
    info.folder_path = tmp_path

    async def check(*_args):
        return True

    monkeypatch.setattr(scraper_module, "check_file", check)
    monkeypatch.setattr(
        scraper_module,
        "get_movie_path_setting",
        lambda *_args: SimpleNamespace(success_folder=tmp_path / "output", movie_path=tmp_path),
    )

    def forbidden(*_args, **_kwargs):
        pytest.fail("suren actor quality gate allowed output")

    for name in [
        "show_result",
        "translate_title_outline",
        "translate_actor",
        "get_output_name",
        "creat_folder",
        "write_nfo",
        "poster_download",
        "thumb_download",
        "fanart_download",
        "move_movie",
    ]:
        monkeypatch.setattr(scraper_module, name, forbidden)

    records: list[Website] = []
    client = AsyncWebClient(timeout=10, cf_bypass_url="", log_fn=lambda _: None)

    async def transport(**kwargs):
        return FakeResponse(status_code=200, content=b"ok", url=str(kwargs["url"]))

    client._curl_request = transport
    provider = _RecordingProvider(
        {
            Website.MGSTAGE: _RecordingCrawler(
                Website.MGSTAGE,
                records,
                _make_result(
                    Website.MGSTAGE,
                    title="テスト作品",
                    actors=primary_actors,
                    all_actors=primary_actors,
                    thumb="https://example.test/thumb.jpg",
                ),
            ),
            Website.MMTV: _RecordingCrawler(
                Website.MMTV,
                records,
                _make_result(
                    Website.MMTV,
                    actors=secondary_actors,
                    all_actors=secondary_actors,
                    score="4.0",
                    score_max="5",
                ),
            ),
        }
    )

    batch = BatchDiagnostics()
    token = batch_diagnostics.set(batch)
    try:
        scraper = scraper_module.Scraper(provider)
        with pytest.raises(QualityDeferred):
            await scraper._process_one_file(info, FileMode.Default)
        assert missing_required(scraper._quality_pending[movie_path].raw_result, FixedScrapingType.SUREN) == ["actors"]
        assert not any(batch.service_streaks.values())
        assert not batch.stop_reason
        assert all(state.failure_count == 0 for state in client._site_ban_states.values())

        scraper._quality_retrying = True
        with pytest.raises(QualityHeld, match="留原地：actors"):
            await scraper._process_one_file(info, FileMode.Default)

        assert all(
            issue.status != CrawlStatus.REQUEST_ERROR
            for report in scraper._quality_pending[movie_path].reports
            for issue in report.issues
        )
        assert list(tmp_path.iterdir()) == [movie_path]
        assert movie_path.read_bytes() == b"original"
    finally:
        batch_diagnostics.reset(token)
        await client.close()


@pytest.mark.asyncio
async def test_suren_pure_primary_actor_behavior_is_unchanged():
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
                    thumb="https://example.test/thumb.jpg",
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
    res = await scraper._call_crawlers(_make_input("999TEST-005"), classification)

    assert res is not None
    assert res.actors == ["白石ゆい"]
    assert res.all_actors == ["白石ゆい"]
    assert res.field_sources[CrawlerResultFields.ACTORS] == Website.MGSTAGE.value
    assert res.field_sources[CrawlerResultFields.ALL_ACTORS] == Website.MGSTAGE.value
    assert not any(report.has_error for report in scraper.reports)


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
                        actors=["桜庭テスト25歳会社員"],
                        all_actors=["桜庭テスト25歳会社員"],
                    ),
                ),
                Website.DMM: _RecordingCrawler(
                    Website.DMM,
                    records,
                    _make_result(
                        Website.DMM,
                        actors=["桜庭テスト"],
                        all_actors=["桜庭テスト"],
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
        res = await scraper._call_crawlers(_make_input("999TEST-006"), classification)
        assert res is not None
        assert res.actors == ["桜庭テスト25歳会社員"]
        assert res.all_actors == ["桜庭テスト25歳会社員"]
