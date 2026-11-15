from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from mdcx.config.enums import FixedScrapingType, Language, Website
from mdcx.config.models import Config, FieldConfig, FieldPriorityConfig
from mdcx.core.actor_quality import is_pure_suren_actor, valid_suren_actor_names
from mdcx.core.file_crawler import FileScraper, ScrapeClassification
from mdcx.core.scrape_quality import QualityDeferred, QualityHeld, missing_required
from mdcx.gen.field_enums import CrawlerResultFields
from mdcx.models.crawl_status import BatchDiagnostics, CrawlStatus, batch_diagnostics
from mdcx.models.enums import FileMode
from mdcx.models.flags import Flags
from mdcx.models.log_buffer import LogBuffer
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
    from mdcx.core import translate as translate_module

    sites = [Website.MGSTAGE, Website.MMTV]
    config = _make_suren_config(sites=sites, score_sites=[Website.MMTV])
    monkeypatch.setattr(scraper_module, "manager", SimpleNamespace(config=config))
    monkeypatch.setattr(translate_module, "manager", SimpleNamespace(config=config))
    avwiki_mock = AsyncMock(return_value=(False, "No Result!"))
    monkeypatch.setattr(translate_module, "get_actorname", avwiki_mock)
    Flags.reset()
    LogBuffer.clear_task()
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
        with pytest.raises(QualityDeferred) as deferred_exc:
            await scraper._process_one_file(info, FileMode.Default)
        assert "没有合格的纯演员名" in str(deferred_exc.value)
        assert missing_required(scraper._quality_pending[movie_path].raw_result, FixedScrapingType.SUREN) == ["actors"]
        assert not any(batch.service_streaks.values())
        assert not batch.stop_reason
        assert all(state.failure_count == 0 for state in client._site_ban_states.values())

        scraper._quality_retrying = True
        with pytest.raises(QualityHeld, match="留原地：actors") as held_exc:
            await scraper._process_one_file(info, FileMode.Default)

        assert avwiki_mock.await_count == 1
        assert len(records) == 4
        assert "没有合格的纯演员名" in str(held_exc.value)
        assert "解析异常" not in str(held_exc.value)
        assert "没有合格的纯演员名" in scraper._quality_summaries[0]
        assert "解析异常" not in scraper._quality_summaries[0]
        if primary_actors:
            assert "mgstage -> 7mmtv" in str(held_exc.value)
            assert "mgstage -> 7mmtv" in LogBuffer.log().get()
        assert not any(batch.parse_errors.values())
        assert not any("页面没有被程序正常识别" in line for line in batch.lines())
        assert all(
            issue.status not in {CrawlStatus.REQUEST_ERROR, CrawlStatus.PARSE_ERROR}
            for report in scraper._quality_pending[movie_path].reports
            for issue in report.issues
        )
        assert list(tmp_path.iterdir()) == [movie_path]
        assert movie_path.read_bytes() == b"original"
    finally:
        LogBuffer.clear_task()
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


@pytest.mark.asyncio
async def test_suren_all_impure_sites_rescued_by_pure_avwiki_actor_enters_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    from mdcx.core import scraper as scraper_module
    from mdcx.core import translate as translate_module
    from mdcx.core import utils as utils_module

    sites = [Website.MGSTAGE, Website.MMTV]
    config = _make_suren_config(sites=sites, score_sites=[Website.MMTV])
    config.actor_realname = True
    config.get_field_config(CrawlerResultFields.ACTORS).translate = False
    monkeypatch.setattr(scraper_module, "manager", SimpleNamespace(config=config))
    monkeypatch.setattr(translate_module, "manager", SimpleNamespace(config=config))
    monkeypatch.setattr(utils_module, "manager", SimpleNamespace(config=config))
    avwiki_mock = AsyncMock(return_value=(True, "白石ゆい"))
    monkeypatch.setattr(translate_module, "get_actorname", avwiki_mock)
    Flags.reset()
    LogBuffer.clear_task()
    scraper_module.signal.stop = False

    movie_path = tmp_path / "999TEST-007.mp4"
    movie_path.write_bytes(b"original")
    info = FileInfo.empty()
    info.number = "999TEST-007"
    info.file_path = movie_path
    info.folder_path = tmp_path

    async def check(*_args):
        return True

    async def noop_async(*_args, **_kwargs):
        return None

    async def fake_video_size(*_args, **_kwargs):
        return "", ""

    captured: dict[str, object] = {}

    class StopAfterOutputName(Exception):
        pass

    def fake_get_output_name(file_info, result, success_folder, file_ex):
        captured["result"] = result
        captured["folder_name"] = result.actor
        raise StopAfterOutputName

    monkeypatch.setattr(scraper_module, "check_file", check)
    monkeypatch.setattr(
        scraper_module,
        "get_movie_path_setting",
        lambda *_args: SimpleNamespace(success_folder=tmp_path / "output", movie_path=tmp_path),
    )
    monkeypatch.setattr(scraper_module, "translate_title_outline", noop_async)
    monkeypatch.setattr(scraper_module, "translate_info", lambda res, *_args: res)
    monkeypatch.setattr(scraper_module, "replace_word", lambda res: res)
    monkeypatch.setattr(scraper_module, "get_video_size", fake_video_size)
    monkeypatch.setattr(scraper_module, "get_output_name", fake_get_output_name)

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
        with pytest.raises(StopAfterOutputName):
            await scraper._process_one_file(info, FileMode.Default)

        res = captured["result"]
        assert isinstance(res, CrawlerResult) or hasattr(res, "actors")
        assert res.actors == ["白石ゆい"]
        assert res.all_actors == ["白石ゆい"]
        assert res.field_sources[CrawlerResultFields.ACTORS] == "av-wiki"
        assert captured["folder_name"] == "白石ゆい"
        assert avwiki_mock.await_count == 1
        assert "跳过非纯演员名站点 (mgstage -> 7mmtv)，改取 Av-wiki" in res.field_log
        log_text = LogBuffer.log().get()
        assert "Av-wiki done! Actor's real Japanese name is '白石ゆい'" in log_text
        assert not any(batch.parse_errors.values())
        assert not any("页面没有被程序正常识别" in line for line in batch.lines())
    finally:
        LogBuffer.clear_task()
        batch_diagnostics.reset(token)


@pytest.mark.asyncio
async def test_suren_all_impure_sites_and_impure_avwiki_defers_once_then_holds_with_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    from mdcx.core import scraper as scraper_module
    from mdcx.core import translate as translate_module

    sites = [Website.MGSTAGE, Website.MMTV]
    config = _make_suren_config(sites=sites, score_sites=[Website.MMTV])
    config.actor_realname = True
    monkeypatch.setattr(scraper_module, "manager", SimpleNamespace(config=config))
    monkeypatch.setattr(translate_module, "manager", SimpleNamespace(config=config))
    avwiki_mock = AsyncMock(return_value=(True, "白石ゆいさん"))
    monkeypatch.setattr(translate_module, "get_actorname", avwiki_mock)
    Flags.reset()
    LogBuffer.clear_task()
    scraper_module.signal.stop = False

    movie_path = tmp_path / "999TEST-008.mp4"
    movie_path.write_bytes(b"original")
    info = FileInfo.empty()
    info.number = "999TEST-008"
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

        scraper._quality_retrying = True
        with pytest.raises(QualityHeld, match="留原地：actors") as held_exc:
            await scraper._process_one_file(info, FileMode.Default)

        assert avwiki_mock.await_count == 1
        assert len(records) == 4
        assert "没有合格的纯演员名（已跳过: mgstage -> 7mmtv -> av-wiki）" in str(held_exc.value)
        assert "解析异常" not in str(held_exc.value)
        assert "没有合格的纯演员名（已跳过: mgstage -> 7mmtv -> av-wiki）" in scraper._quality_summaries[0]
        assert "Av-wiki: 没有合格的纯演员名" in LogBuffer.log().get()
        assert not any(batch.parse_errors.values())
        assert not any("页面没有被程序正常识别" in line for line in batch.lines())
        assert list(tmp_path.iterdir()) == [movie_path]
        assert movie_path.read_bytes() == b"original"
    finally:
        LogBuffer.clear_task()
        batch_diagnostics.reset(token)


@pytest.mark.asyncio
async def test_suren_pure_site_actor_rejects_impure_avwiki_and_keeps_single_request(
    monkeypatch: pytest.MonkeyPatch,
):
    from mdcx.core import translate as translate_module

    config = _make_suren_config()
    config.actor_realname = True
    config.get_field_config(CrawlerResultFields.ACTORS).translate = False
    monkeypatch.setattr(translate_module, "manager", SimpleNamespace(config=config))
    avwiki_mock = AsyncMock(return_value=(True, "白石ゆいさん"))
    monkeypatch.setattr(translate_module, "get_actorname", avwiki_mock)
    LogBuffer.clear_task()

    from mdcx.models.types import CrawlersResult

    real_res = CrawlersResult.empty()
    real_res.number = "999TEST-009"
    real_res.scraping_type = FixedScrapingType.SUREN
    real_res.actors = ["白石ゆい"]
    real_res.all_actors = ["白石ゆい"]

    try:
        await translate_module.translate_actor(real_res)
        assert avwiki_mock.await_count == 1
        assert real_res.actors == ["白石ゆい"]
        assert real_res.all_actors == ["白石ゆい"]
        assert "Av-wiki: 没有合格的纯演员名" in LogBuffer.log().get()
    finally:
        LogBuffer.clear_task()


def _install_mock_actor_mapping(monkeypatch: pytest.MonkeyPatch, xml_body: str) -> None:
    from lxml import etree

    from mdcx.config.resources import resources

    parser = etree.HTMLParser(encoding="utf-8")
    monkeypatch.setattr(resources, "actor_mapping_data", etree.HTML(xml_body.encode("utf-8"), parser=parser))


@pytest.mark.asyncio
async def test_suren_actor_mapping_reintroducing_honorific_keeps_pre_mapping_pure_name(
    monkeypatch: pytest.MonkeyPatch,
):
    from mdcx.core import translate as translate_module
    from mdcx.models.types import CrawlersResult

    _install_mock_actor_mapping(
        monkeypatch,
        """
        <actor>
          <a zh_cn="桜庭祐奈" zh_tw="桜庭祐奈" jp="桜庭さん" keyword=",桜庭舞美,桜庭さん,桜庭祐奈," />
          <a zh_cn="白石别" zh_tw="白石別" jp="は別人" keyword=",白石別名,は別人," />
        </actor>
        """,
    )
    config = _make_suren_config()
    config.actor_realname = True
    config.get_field_config(CrawlerResultFields.ACTORS).translate = True
    config.get_field_config(CrawlerResultFields.ACTORS).language = Language.JP
    config.get_field_config(CrawlerResultFields.ALL_ACTORS).translate = True
    config.get_field_config(CrawlerResultFields.ALL_ACTORS).language = Language.JP
    monkeypatch.setattr(translate_module, "manager", SimpleNamespace(config=config))
    avwiki_mock = AsyncMock(return_value=(False, "No Result!"))
    monkeypatch.setattr(translate_module, "get_actorname", avwiki_mock)
    LogBuffer.clear_task()

    res = CrawlersResult.empty()
    res.number = "999TEST-010"
    res.scraping_type = FixedScrapingType.SUREN
    res.actors = ["桜庭舞美", "白石別名"]
    res.all_actors = ["桜庭舞美", "白石別名"]

    try:
        await translate_module.translate_actor(res)
        assert res.actors == ["桜庭舞美", "白石別名"]
        assert res.all_actors == ["桜庭舞美", "白石別名"]
        log_text = LogBuffer.log().get()
        assert "保留映射前名字" in log_text
    finally:
        LogBuffer.clear_task()


def test_suren_mapping_trusted_stage_names_accepted_unless_age_or_honorific(
    monkeypatch: pytest.MonkeyPatch,
):
    _install_mock_actor_mapping(
        monkeypatch,
        """
        <actor>
          <a zh_cn="@SAMPLE" zh_tw="@SAMPLE" jp="@SAMPLE" keyword=",@SAMPLE," />
          <a zh_cn="M@TEST" zh_tw="M@TEST" jp="M@TEST" keyword=",M@TEST," />
          <a zh_cn="Sample." zh_tw="Sample." jp="Sample." keyword=",Sample.," />
          <a zh_cn="テスト." zh_tw="テスト." jp="テスト." keyword=",テスト.," />
          <a zh_cn="sample19" zh_tw="sample19" jp="sample19" keyword=",sample19," />
          <a zh_cn="素人测试" zh_tw="素人測試" jp="素人テスト" keyword=",素人テスト,素人测试," />
          <a zh_cn="桜庭テスト★" zh_tw="桜庭テスト★" jp="桜庭テスト★" keyword=",桜庭テスト★," />
          <a zh_cn="テスト＠ハム" zh_tw="テスト＠ハム" jp="テスト＠ハム" keyword=",テスト＠ハム," />
          <a zh_cn="テスト" zh_tw="テスト" jp="テストちゃん" keyword=",テストちゃん," />
          <a zh_cn="桜庭" zh_tw="桜庭" jp="桜庭さん" keyword=",桜庭さん," />
          <a zh_cn="桜庭くん" zh_tw="桜庭くん" jp="桜庭くん" keyword=",桜庭くん," />
          <a zh_cn="桜庭様" zh_tw="桜庭様" jp="桜庭様" keyword=",桜庭様," />
          <a zh_cn="桜庭25歳" zh_tw="桜庭25歳" jp="桜庭25歳" keyword=",桜庭25歳," />
          <a zh_cn="桜庭19才" zh_tw="桜庭19才" jp="桜庭19才" keyword=",桜庭19才," />
          <a zh_cn="桜庭二十歳" zh_tw="桜庭二十歳" jp="桜庭二十歳" keyword=",桜庭二十歳," />
          <a zh_cn="テスト(仮)" zh_tw="テスト(仮)" jp="テスト(仮)" keyword=",テスト(仮)," />
          <a zh_cn="Sample [TS]" zh_tw="Sample [TS]" jp="Sample [TS]" keyword=",Sample [TS]," />
          <a zh_cn="卖家样本" zh_tw="賣家樣本" jp="テスト企画" keyword=",テスト企画,【FC卖家】," />
        </actor>
        """,
    )

    # Stage names present in mapping table without age/honorific/brackets are accepted.
    for trusted_name in (
        "@SAMPLE",
        "M@TEST",
        "Sample.",
        "テスト.",
        "sample19",
        "素人テスト",
        "桜庭テスト★",
        "テスト＠ハム",
    ):
        assert is_pure_suren_actor(trusted_name) is True

    # Honorifics, ages, brackets, and FC sellers remain rejected even if in mapping table.
    for rejected_mapped in (
        "テストちゃん",
        "桜庭さん",
        "桜庭くん",
        "桜庭様",
        "桜庭25歳",
        "桜庭19才",
        "桜庭二十歳",
        "テスト(仮)",
        "Sample [TS]",
        "テスト企画",
    ):
        assert is_pure_suren_actor(rejected_mapped) is False

    # Unmapped special-symbol/digit/keyword variants remain rejected.
    for unmapped_name in ("@UNMAPPED", "Unmapped.", "unmapped19", "素人未登録", "未登録★"):
        assert is_pure_suren_actor(unmapped_name) is False


@pytest.mark.asyncio
async def test_suren_non_name_phrases_rejected_even_in_mapping_table(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    from mdcx.core import scraper as scraper_module
    from mdcx.core import translate as translate_module

    _install_mock_actor_mapping(
        monkeypatch,
        """
        <actor>
          <a zh_cn="别人" zh_tw="は別人" jp="は別人" keyword=",は別人,别人,同名別人,数据错误,【同名異人】," />
          <a zh_cn="错误" zh_tw="錯誤" jp="錯誤" keyword=",酸素,錯誤,错误,【誤認注意】," />
          <a zh_cn="再生不能" zh_tw="再生不能" jp="再生不能" keyword=",再生不能,編集不可," />
          <a zh_cn="复数" zh_tw="複數" jp="複数" keyword=",复数,複数,複數," />
          <a zh_cn="素人" zh_tw="素人" jp="素人" keyword=",B級素人初撮り,人物不明,素人,素人不明,素人１," />
          <a zh_cn="素人(多人)" zh_tw="素人(多人)" jp="素人(多人)" keyword=",多数,素人(多人),複数の素人娘," />
          <a zh_cn="素人妻" zh_tw="素人妻" jp="素人妻" keyword=",人妻,素人妻," />
          <a zh_cn="素人娘" zh_tw="素人娘" jp="素人娘" keyword=",素人娘,素人少女," />
          <a zh_cn="S级素人" zh_tw="S級素人" jp="S級素人" keyword=",S級素人,S级素人," />
          <a zh_cn="SOD" zh_tw="SOD" jp="SOD" keyword=",SOD,SOD女子社員," />
          <a zh_cn="名誉毁损" zh_tw="名譽毀損" jp="名誉毀損" keyword=",名誉毀損,名誉毁损," />
          <a zh_cn="未知男优" zh_tw="未知男優" jp="未知男優" keyword=",未知男優,未知男优," />
          <a zh_cn="女优" zh_tw="女優" jp="女優" keyword=",AV女優,女優,女优," />
          <a zh_cn="元読者モデル" zh_tw="元読者モデル" jp="元読者モデル" keyword=",元読者モデル," />
          <a zh_cn="貧乳美女" zh_tw="貧乳美女" jp="貧乳美女" keyword=",貧乳美女," />
          <a zh_cn="ギャル２人組" zh_tw="ギャル２人組" jp="ギャル２人組" keyword=",ギャル２人組," />
        </actor>
        """,
    )

    non_names = (
        "は別人",
        "別人",
        "别人",
        "同名別人",
        "数据错误",
        "酸素",
        "錯誤",
        "错误",
        "再生不能",
        "編集不可",
        "複数",
        "复数",
        "複數",
        "多数",
        "素人",
        "素人(多人)",
        "素人妻",
        "素人娘",
        "S級素人",
        "SOD",
        "名誉毀損",
        "未知男優",
        "女優",
        "AV女優",
        "元読者モデル",
        "貧乳美女",
        "ギャル２人組",
    )
    for phrase in non_names:
        assert is_pure_suren_actor(phrase) is False, f"non-name phrase should be rejected: {phrase}"

    # Replay end-to-end: a site returning "は別人" must defer once and hold instead of entering output.
    sites = [Website.MGSTAGE]
    config = _make_suren_config(sites=sites, score_sites=sites)
    config.actor_realname = True
    monkeypatch.setattr(scraper_module, "manager", SimpleNamespace(config=config))
    monkeypatch.setattr(translate_module, "manager", SimpleNamespace(config=config))
    monkeypatch.setattr(translate_module, "get_actorname", AsyncMock(return_value=(False, "No Result!")))
    Flags.reset()
    LogBuffer.clear_task()
    scraper_module.signal.stop = False

    movie_path = tmp_path / "999TEST-011.mp4"
    movie_path.write_bytes(b"original")
    info = FileInfo.empty()
    info.number = "999TEST-011"
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
        pytest.fail("non-name phrase must not enter output")

    for name in ("get_output_name", "creat_folder", "write_nfo", "move_movie"):
        monkeypatch.setattr(scraper_module, name, forbidden)

    records: list[Website] = []
    provider = _RecordingProvider(
        {
            Website.MGSTAGE: _RecordingCrawler(
                Website.MGSTAGE,
                records,
                _make_result(
                    Website.MGSTAGE,
                    title="テスト作品",
                    actors=["は別人"],
                    all_actors=["は別人"],
                    thumb="https://example.test/thumb.jpg",
                ),
            )
        }
    )

    try:
        scraper = scraper_module.Scraper(provider)
        with pytest.raises(QualityDeferred):
            await scraper._process_one_file(info, FileMode.Default)
        scraper._quality_retrying = True
        with pytest.raises(QualityHeld, match="留原地：actors"):
            await scraper._process_one_file(info, FileMode.Default)
    finally:
        LogBuffer.clear_task()


@pytest.mark.asyncio
async def test_non_suren_avwiki_actor_update_matches_master_behavior(
    monkeypatch: pytest.MonkeyPatch,
):
    from mdcx.core import translate as translate_module
    from mdcx.models.types import CrawlersResult

    config = _make_suren_config()
    config.actor_realname = True
    config.get_field_config(CrawlerResultFields.ACTORS).translate = False
    monkeypatch.setattr(translate_module, "manager", SimpleNamespace(config=config))
    avwiki_mock = AsyncMock(return_value=(True, "山田テスト,佐藤テスト"))
    monkeypatch.setattr(translate_module, "get_actorname", avwiki_mock)
    LogBuffer.clear_task()

    try:
        # YOUMA with unknown actor + unrelated all_actors keeps all_actors unchanged (same as master).
        youma = CrawlersResult.empty()
        youma.number = "999YOUMA-001"
        youma.scraping_type = FixedScrapingType.YOUMA
        youma.actors = ["未知演员"]
        youma.all_actors = ["別名テスト"]
        await translate_module.translate_actor(youma)
        assert youma.actors == ["山田テスト", "佐藤テスト"]
        assert youma.all_actors == ["別名テスト"]

        # FC2 multi-actor replacement in all_actors keeps exact master single-string replacement.
        fc2_match = CrawlersResult.empty()
        fc2_match.number = "999FC2-001"
        fc2_match.scraping_type = FixedScrapingType.FC2
        fc2_match.actors = ["桜庭テスト"]
        fc2_match.all_actors = ["桜庭テスト"]
        await translate_module.translate_actor(fc2_match)
        assert fc2_match.actors == ["山田テスト", "佐藤テスト"]
        assert fc2_match.all_actors == ["山田テスト,佐藤テスト"]

        # FC2 with unrelated all_actors keeps all_actors unchanged (same as master).
        fc2_other = CrawlersResult.empty()
        fc2_other.number = "999FC2-002"
        fc2_other.scraping_type = FixedScrapingType.FC2
        fc2_other.actors = ["桜庭テスト"]
        fc2_other.all_actors = ["別名テスト"]
        await translate_module.translate_actor(fc2_other)
        assert fc2_other.actors == ["山田テスト", "佐藤テスト"]
        assert fc2_other.all_actors == ["別名テスト"]

        # WUMA does not query Av-wiki and stays untouched.
        calls_before = avwiki_mock.await_count
        wuma = CrawlersResult.empty()
        wuma.number = "999WUMA-001"
        wuma.scraping_type = FixedScrapingType.WUMA
        wuma.actors = ["未知演员"]
        wuma.all_actors = ["別名テスト"]
        await translate_module.translate_actor(wuma)
        assert avwiki_mock.await_count == calls_before
        assert wuma.actors == ["未知演员"]
        assert wuma.all_actors == ["別名テスト"]
    finally:
        LogBuffer.clear_task()


@pytest.mark.asyncio
async def test_suren_avwiki_cache_reused_when_batch_retry_recovers_pure_site_actor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    from mdcx.core import scraper as scraper_module
    from mdcx.core import translate as translate_module
    from mdcx.core import utils as utils_module

    sites = [Website.MGSTAGE, Website.MMTV]
    config = _make_suren_config(sites=sites, score_sites=[Website.MMTV])
    config.actor_realname = True
    config.get_field_config(CrawlerResultFields.ACTORS).translate = False
    monkeypatch.setattr(scraper_module, "manager", SimpleNamespace(config=config))
    monkeypatch.setattr(translate_module, "manager", SimpleNamespace(config=config))
    monkeypatch.setattr(utils_module, "manager", SimpleNamespace(config=config))
    avwiki_mock = AsyncMock(return_value=(False, "No Result!"))
    monkeypatch.setattr(translate_module, "get_actorname", avwiki_mock)
    Flags.reset()
    LogBuffer.clear_task()
    scraper_module.signal.stop = False

    movie_path = tmp_path / "999TEST-012.mp4"
    movie_path.write_bytes(b"original")
    info = FileInfo.empty()
    info.number = "999TEST-012"
    info.file_path = movie_path
    info.folder_path = tmp_path

    async def check(*_args):
        return True

    async def noop_async(*_args, **_kwargs):
        return None

    async def fake_video_size(*_args, **_kwargs):
        return "", ""

    captured: dict[str, object] = {}

    class StopAfterOutputName(Exception):
        pass

    def fake_get_output_name(file_info, result, success_folder, file_ex):
        captured["result"] = result
        raise StopAfterOutputName

    monkeypatch.setattr(scraper_module, "check_file", check)
    monkeypatch.setattr(
        scraper_module,
        "get_movie_path_setting",
        lambda *_args: SimpleNamespace(success_folder=tmp_path / "output", movie_path=tmp_path),
    )
    monkeypatch.setattr(scraper_module, "translate_title_outline", noop_async)
    monkeypatch.setattr(scraper_module, "translate_info", lambda res, *_args: res)
    monkeypatch.setattr(scraper_module, "replace_word", lambda res: res)
    monkeypatch.setattr(scraper_module, "get_video_size", fake_video_size)
    monkeypatch.setattr(scraper_module, "get_output_name", fake_get_output_name)

    round_state = {"attempt": 0}

    class _RecoveringMmtvCrawler:
        def __init__(self):
            self._records: list[Website] = []

        def is_stopped(self) -> bool:
            return False

        def reset_wall_timeout(self, _number: str) -> None:
            return None

        async def run(self, _task_input: CrawlerInput) -> CrawlerResponse:
            round_state["attempt"] += 1
            actors = ["桜庭テストさん"] if round_state["attempt"] == 1 else ["白石ゆい"]
            return CrawlerResponse(
                debug_info=CrawlerDebugInfo(execution_time=0.01),
                data=_make_result(
                    Website.MMTV,
                    actors=actors,
                    all_actors=actors,
                    score="4.0",
                    score_max="5",
                ),
            )

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
                    thumb="https://example.test/thumb.jpg",
                ),
            ),
            Website.MMTV: _RecoveringMmtvCrawler(),
        }
    )

    try:
        scraper = scraper_module.Scraper(provider)
        with pytest.raises(QualityDeferred):
            await scraper._process_one_file(info, FileMode.Default)
        assert avwiki_mock.await_count == 1

        scraper._quality_retrying = True
        with pytest.raises(StopAfterOutputName):
            await scraper._process_one_file(info, FileMode.Default)

        res = captured["result"]
        assert res.actors == ["白石ゆい"]
        assert res.all_actors == ["白石ゆい"]
        assert avwiki_mock.await_count == 1
    finally:
        LogBuffer.clear_task()


@pytest.mark.asyncio
async def test_suren_avwiki_rescue_overwrites_all_actors_and_sources_consistently(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    from mdcx.core import scraper as scraper_module
    from mdcx.core import translate as translate_module
    from mdcx.core import utils as utils_module

    sites = [Website.MGSTAGE, Website.DMM]
    config = _make_suren_config(sites=sites, score_sites=[Website.DMM])
    config.field_configs[CrawlerResultFields.ALL_ACTORS] = FieldConfig(site_prority=[Website.DMM, Website.MGSTAGE])
    config.type_field_configs[FixedScrapingType.SUREN.value][CrawlerResultFields.ALL_ACTORS.value] = (
        FieldPriorityConfig(site_prority=[Website.DMM, Website.MGSTAGE])
    )
    config.actor_realname = True
    config.get_field_config(CrawlerResultFields.ACTORS).translate = False
    monkeypatch.setattr(scraper_module, "manager", SimpleNamespace(config=config))
    monkeypatch.setattr(translate_module, "manager", SimpleNamespace(config=config))
    monkeypatch.setattr(utils_module, "manager", SimpleNamespace(config=config))
    avwiki_mock = AsyncMock(return_value=(True, "桜庭テスト"))
    monkeypatch.setattr(translate_module, "get_actorname", avwiki_mock)
    Flags.reset()
    LogBuffer.clear_task()
    scraper_module.signal.stop = False

    movie_path = tmp_path / "999TEST-013.mp4"
    movie_path.write_bytes(b"original")
    info = FileInfo.empty()
    info.number = "999TEST-013"
    info.file_path = movie_path
    info.folder_path = tmp_path

    async def check(*_args):
        return True

    async def noop_async(*_args, **_kwargs):
        return None

    async def fake_video_size(*_args, **_kwargs):
        return "", ""

    captured: dict[str, object] = {}

    class StopAfterOutputName(Exception):
        pass

    def fake_get_output_name(file_info, result, success_folder, file_ex):
        captured["result"] = result
        raise StopAfterOutputName

    monkeypatch.setattr(scraper_module, "check_file", check)
    monkeypatch.setattr(
        scraper_module,
        "get_movie_path_setting",
        lambda *_args: SimpleNamespace(success_folder=tmp_path / "output", movie_path=tmp_path),
    )
    monkeypatch.setattr(scraper_module, "translate_title_outline", noop_async)
    monkeypatch.setattr(scraper_module, "translate_info", lambda res, *_args: res)
    monkeypatch.setattr(scraper_module, "replace_word", lambda res: res)
    monkeypatch.setattr(scraper_module, "get_video_size", fake_video_size)
    monkeypatch.setattr(scraper_module, "get_output_name", fake_get_output_name)

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
                    thumb="https://example.test/thumb.jpg",
                ),
            ),
            Website.DMM: _RecordingCrawler(
                Website.DMM,
                records,
                _make_result(
                    Website.DMM,
                    actors=[],
                    all_actors=["別名テスト"],
                    score="4.5",
                    score_max="5",
                ),
            ),
        }
    )

    try:
        scraper = scraper_module.Scraper(provider)
        with pytest.raises(StopAfterOutputName):
            await scraper._process_one_file(info, FileMode.Default)

        res = captured["result"]
        assert res.actors == ["桜庭テスト"]
        assert res.all_actors == ["桜庭テスト"]
        assert res.field_sources[CrawlerResultFields.ACTORS] == "av-wiki"
        assert res.field_sources[CrawlerResultFields.ALL_ACTORS] == "av-wiki"
    finally:
        LogBuffer.clear_task()
