from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from mdcx.config.enums import CDChar
from mdcx.config.manager import manager
from mdcx.config.models import Config
from mdcx.core.file import (
    _generate_file_name,
    _get_folder_path,
    get_file_info_v2,
    get_output_name,
    parse_evaluation_suffix,
)
from mdcx.core.naming import NameRenderOptions, NamingTarget, render_name
from mdcx.models.enums import FileMode
from mdcx.models.flags import Flags
from mdcx.models.types import CrawlersResult, FileInfo


@pytest.fixture(scope="session", autouse=True)
def qt_application():
    # Keep Qt alive while UI and scraper tests share the application's signals.
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def config(monkeypatch):
    values = {
        "evaluation_suffix_words": "  good   nice good YES ",
        "cd_char": [CDChar.DIGITAL, CDChar.MIDDLE_NUMBER],
        "cd_name": 0,
        "prevent_char": "",
        "main_mode": 1,
        "success_file_rename": True,
        "success_file_move": True,
        "soft_link": 0,
        "naming_file": "{{ number }} {{ title }}",
        "update_c_filetemplate": "{{ number }} {{ title }}",
        "folder_name": "{{ number }}/{{ title }}",
        "file_name_max": 60,
        "folder_name_max": 60,
        "file_hd": False,
        "file_cnword": False,
        "file_moword": False,
        "folder_hd": False,
        "folder_cnword": False,
        "folder_moword": False,
        "subtitle_add": False,
        "string": [],
        "no_escape": [],
        "sub_type": [],
    }
    for key, value in values.items():
        monkeypatch.setattr(manager.config, key, value)
    monkeypatch.setattr(Flags, "file_mode", FileMode.Default)


@pytest.mark.parametrize(
    "stem,suffix,unknown",
    [
        ("ABC-123 title-good", "-good", ()),
        ("ABC-123-good nice", "-good nice", ()),
        ("ABC-123 title-good-YES nice", "-good-YES nice", ()),
        ("ABC-123-good nice-cd2", "-good nice", ()),
        ("ABC-123-good nice-2", "-good nice", ()),
        ("ABC-123-good", "", ()),
        ("good nice", "", ()),
        ("ABC-123 title-goodness", "", ()),
        ("ABC-123 title-Good", "", ()),
        ("ABC-123-good nice-unknown", "", ()),
        ("ABC-123-good odd odd", "", ("odd",)),
        ("ABC-123-good odd-nice YES", "-nice YES", ()),
    ],
)
def test_recognition(stem, suffix, unknown):
    base, actual, bad = parse_evaluation_suffix(stem)
    assert actual == suffix
    assert bad == unknown
    if suffix:
        assert "good nice" not in base


@pytest.mark.asyncio
async def test_stage_number_cd_and_roundtrip(tmp_path):
    path = tmp_path / "TEST-123-UCLTX-good nice-cd2.mp4"
    info = await get_file_info_v2(path, copy_sub=False)
    assert (info.number, info.cd_part, info.umr_stage) == ("TEST-123", "-cd2", "LTX")
    assert info.evaluation_suffix == "-good nice"
    data = CrawlersResult.empty()
    data.number, data.title = info.number, "title"
    output = get_output_name(info, data, tmp_path / "output", ".mp4")
    assert output[1].name == "TEST-123 title-good nice-cd2.mp4"
    assert output[2].stem == output[1].stem
    assert output[3].name == "TEST-123 title-good nice-cd2-poster.jpg"
    again = await get_file_info_v2(output[1], copy_sub=False)
    assert get_output_name(again, data, tmp_path / "output", ".mp4") == output
    assert (
        render_name("{{ filename }}", info, data, NameRenderOptions(target=NamingTarget.NFO_TITLE)).text
        == "TEST-123-UCLTX-cd2"
    )
    assert data.title == "title"
    assert "good" not in str(data.tag)


def build():
    info = FileInfo.empty()
    info.number = "ABC-123"
    info.file_path = Path("input/ABC-123 title-good nice.mp4")
    info.file_name = "ABC-123 title"
    info.evaluation_suffix = "-good nice"
    data = CrawlersResult.empty()
    data.number, data.title = info.number, "title" * 50
    return info, data


@pytest.mark.parametrize("mode", [1, 2, 3, 4])
@pytest.mark.parametrize("prevent", ["", "·"])
def test_length_and_modes(monkeypatch, mode, prevent):
    info, data = build()
    monkeypatch.setattr(manager.config, "main_mode", mode)
    monkeypatch.setattr(manager.config, "prevent_char", prevent)
    name = _generate_file_name("-cd2", info, data)
    assert name.endswith("-good nice-cd2")
    assert len(name + ".mp4") <= 60
    assert prevent not in name[-len("-good nice-cd2") :] if prevent else True


def test_folder_and_duplicate(monkeypatch):
    info, data = build()
    folder, name = _get_folder_path(Path("output"), info, data)
    assert folder.parts[-2] == "ABC-123"
    assert name.endswith("-good nice")
    assert len(name) <= 60
    data.title = "title-good nice"
    assert _get_folder_path(Path("output"), info, data)[0].name == "title-good nice"
    assert _generate_file_name("", info, data) == "ABC-123 title-good nice"
    monkeypatch.setattr(manager.config, "folder_name", "")
    assert _get_folder_path(Path("output"), info, data) == (Path("output"), "")
    monkeypatch.setattr(manager.config, "success_file_move", False)
    assert _get_folder_path(Path("output"), info, data)[0] == info.file_path.parent


def test_empty_default_preserves_names(monkeypatch):
    assert Config().evaluation_suffix_words == ""
    info, data = build()
    monkeypatch.setattr(manager.config, "evaluation_suffix_words", "")
    assert parse_evaluation_suffix(info.file_path.stem) == (info.file_path.stem, "", ())
    info.evaluation_suffix = ""
    data.title = "title"
    assert _generate_file_name("-cd2", info, data) == "ABC-123 title-cd2"


@pytest.mark.asyncio
async def test_suspicious_is_held_before_any_work(monkeypatch, tmp_path):
    from mdcx.core import scraper as module
    from mdcx.models.crawl_status import BatchDiagnostics, batch_diagnostics

    Flags.reset()
    monkeypatch.setattr(module.signal, "stop", False)
    log = Mock()
    monkeypatch.setattr(module.signal, "show_log_text", log)
    work = AsyncMock(side_effect=AssertionError("must not perform work"))
    monkeypatch.setattr(module, "get_file_info_v2", work)
    monkeypatch.setattr(module, "_process_garbage_file", Mock(side_effect=AssertionError("must not clean")))
    provider = Mock()
    scraper = module.Scraper(provider)
    path = tmp_path / "ABC-123-good odd.mp4"
    path.write_bytes(b"temporary media")
    original = path.read_bytes()
    Flags.remain_list = [path]
    batch = BatchDiagnostics()
    token = batch_diagnostics.set(batch)
    try:
        await scraper.process_one_file((path, 1, 1))
        assert batch == BatchDiagnostics()
    finally:
        batch_diagnostics.reset(token)
    work.assert_not_awaited()
    assert provider.mock_calls == []
    assert list(tmp_path.iterdir()) == [path] and path.read_bytes() == original
    assert Flags.fail_count == 0 and Flags.scrape_done == 1
    assert Flags.remain_list == [path]
    assert scraper._evaluation_held == {path: ("odd",)}
    assert "🔴 评价后缀含词表外的词：odd" in log.call_args_list[0].args[0]


@pytest.mark.asyncio
async def test_original_sidecars_still_read(tmp_path, monkeypatch):
    path = tmp_path / "TEST-123-good nice.mp4"
    path.with_suffix(".srt").write_text("temporary subtitles")
    path.with_suffix(".nfo").write_text("<movie><tag>无码破解</tag></movie>")
    monkeypatch.setattr(manager.config, "sub_type", [".srt"])
    info = await get_file_info_v2(path, copy_sub=False)
    assert info.sub_list == [".srt"]
    assert info.has_sub
    assert info.mosaic == "无码破解"


@pytest.mark.asyncio
async def test_batch_diagnostic_lists_held_files(tmp_path, monkeypatch):
    from mdcx.config.extend import MoviePathSetting
    from mdcx.core import scraper as module

    path = tmp_path / "ABC-123-good odd.mp4"
    path.write_bytes(b"temporary media")
    monkeypatch.setattr(module.signal, "stop", False)
    logs = Mock()
    monkeypatch.setattr(module.signal, "show_log_text", logs)
    for key, value in {
        "garbage_enabled": False,
        "thread_number": 1,
        "thread_time": 0,
        "switch_on": [],
        "scrape_softlink_path": False,
        "emby_on": [],
        "actor_photo_kodi_auto": False,
    }.items():
        monkeypatch.setattr(manager.config, key, value)
    settings = MoviePathSetting(
        movie_path=tmp_path,
        movie_paths=[tmp_path],
        success_folder=tmp_path / "success",
        failed_folder=tmp_path / "failed",
        ignore_dirs=[],
        extrafanart_folder=tmp_path,
        softlink_path=tmp_path,
    )
    monkeypatch.setattr(module, "get_movie_path_setting", lambda *a, **kw: settings)
    monkeypatch.setattr(module, "save_success_list", AsyncMock())
    monkeypatch.setattr(module, "_clean_empty_fodlers", AsyncMock())
    scraper = module.Scraper(Mock())
    await scraper._run(FileMode.Default, [path])
    combined = "\n".join(call.args[0] for call in logs.call_args_list)
    assert f"评价后缀待检查（留原地）\n{path}：odd" in combined
    assert 'color="red"' in combined
    assert Flags.fail_count == Flags.succ_count == 0
    assert Flags.remain_list == [path]
