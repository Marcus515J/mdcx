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
        ("ABC-123-good", "-good", ()),
        ("ABC-123-good-cd2", "-good", ()),
        ("ABC-123-good-2", "-good", ()),
        ("good", "", ()),
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


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [1, 2, 3, 4])
async def test_no_space_single_word_roundtrip(tmp_path, monkeypatch, mode):
    monkeypatch.setattr(manager.config, "main_mode", mode)
    monkeypatch.setattr(manager.config, "naming_file", "{{ number }}")
    monkeypatch.setattr(manager.config, "update_c_filetemplate", "{{ number }}")
    monkeypatch.setattr(manager.config, "folder_name", "{{ number }}")
    info = await get_file_info_v2(tmp_path / "TEST-123 title-good.mp4", copy_sub=False)
    data = CrawlersResult.empty()
    data.number, data.title = info.number, "title"
    output = get_output_name(info, data, tmp_path / "output", ".mp4")
    assert output[1].name == "TEST-123-good.mp4"
    if mode in (1, 2):
        assert output[0].name == "TEST-123"
    else:
        assert output[0] == info.file_path.parent
    again = await get_file_info_v2(output[1], copy_sub=False)
    assert again.number == "TEST-123"
    assert again.evaluation_suffix == "-good"
    assert get_output_name(again, data, tmp_path / "output", ".mp4") == output


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [1, 3])
async def test_written_nfo_title_and_tags_exclude_suffix(tmp_path, monkeypatch, mode):
    from xml.etree import ElementTree as ET

    from mdcx.config.enums import NfoInclude
    from mdcx.core.nfo import write_nfo

    for key, value in {
        "main_mode": mode,
        "naming_media": "{{ filename }} {{ title }}",
        "update_titletemplate": "{{ filename }} {{ title }}",
        "download_files": [],
        "keep_files": [],
        "outline_format": [],
        "nfo_include_new": [NfoInclude.TAG, NfoInclude.GENRE],
    }.items():
        monkeypatch.setattr(manager.config, key, value)
    info = await get_file_info_v2(tmp_path / "TEST-123-good.mp4", copy_sub=False)
    data = CrawlersResult.empty()
    data.number, data.title, data.tags = info.number, "title", ["ordinary"]
    path = tmp_path / "TEST-123-good.nfo"
    assert await write_nfo(info, data, path, tmp_path, update=True)
    root = ET.parse(path).getroot()
    assert root.findtext("title") == "TEST-123 title"
    assert [node.text for node in root.findall("tag")] == ["ordinary"]
    assert [node.text for node in root.findall("genre")] == ["ordinary"]


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


def test_settings_save_close_reopen(tmp_path, monkeypatch, qt_application):
    import importlib

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QMainWindow

    from mdcx.controllers.main_window.main_window import MyMAinWindow
    from mdcx.views.MDCx import Ui_MDCx

    config_module = importlib.import_module("mdcx.config.manager")
    package = "mdcx.controllers.main_window."
    load_module = importlib.import_module(package + "load_config")
    save_module = importlib.import_module(package + "save_config")
    cleanup_module = importlib.import_module(package + "file_cleanup_settings")
    llm_module = importlib.import_module(package + "llm_settings")
    local_module = importlib.import_module(package + "local_model_settings")
    extend_module = importlib.import_module("mdcx.config.extend")
    monkeypatch.setattr(config_module, "MAIN_PATH", tmp_path)
    monkeypatch.setattr(config_module, "MARK_FILE", tmp_path / "MDCx.config")
    temporary = config_module.ConfigManager()
    # Never load the user's configuration, even in the unrelated settings panels.
    for module in (load_module, save_module, cleanup_module, llm_module, local_module, extend_module):
        monkeypatch.setattr(module, "manager", temporary)
    temporary.config.use_database = False
    temporary.save()
    tracebacks = Mock()
    monkeypatch.setattr(load_module.signal_qt, "show_traceback_log", tracebacks)

    def open_settings():
        window = QMainWindow()
        window.Ui = Ui_MDCx()
        window.Ui.setupUi(window)
        MyMAinWindow._setup_fc2ppvdb_cookie_ui(window)
        window.localversion = "test"
        window.dark_mode = False
        window.timer_scrape = QTimer(window)
        window.tray_icon = Mock()
        window.set_javdb_cookie = Mock()
        window.set_javbus_cookie = Mock()
        window.set_label_file_path = Mock()
        # These callbacks affect unrelated window chrome; persistence stays real.
        for name in (
            "update_field_priority_try_all_images_state",
            "update_amazon_strict_pic_verify_state",
            "show_hide_logs",
            "checkBox_i_agree_clean_clicked",
            "_windows_auto_adjust",
        ):
            setattr(window, name, Mock())
        cleanup_module.setup_file_cleanup_settings(window)
        llm_module.setup_llm_settings(window)
        window.local_model_controller.timer.stop()
        load_module.load_config(window)
        window.Ui.pushButton_save_config.clicked.connect(lambda: save_module.save_config(window))
        window.show()
        qt_application.processEvents()
        return window

    first = open_settings()
    try:
        assert first.Ui.lineEdit_evaluation_suffix_words.text() == ""
        first.Ui.lineEdit_evaluation_suffix_words.setText("  demo sample  ")
        first.Ui.pushButton_save_config.click()
        assert Config.model_validate_json(temporary.path.read_text()).evaluation_suffix_words == "  demo sample  "
    finally:
        first.local_model_controller.shutdown()
        first.timer_scrape.stop()
        first.close()
        first.deleteLater()
        qt_application.processEvents()
    # Reset memory so the second window must reload the persisted value.
    temporary.config.evaluation_suffix_words = ""
    second = open_settings()
    try:
        assert second.Ui.lineEdit_evaluation_suffix_words.text() == "  demo sample  "
        tracebacks.assert_not_called()
    finally:
        second.local_model_controller.shutdown()
        second.timer_scrape.stop()
        second.close()
        second.deleteLater()
        qt_application.processEvents()


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
@pytest.mark.parametrize("success_count,fail_count", [(0, 0), (0, 1), (1, 0)])
async def test_batch_diagnostic_lists_held_files(tmp_path, monkeypatch, success_count, fail_count):
    from mdcx.config.extend import MoviePathSetting
    from mdcx.core import scraper as module

    path = tmp_path / "ABC-123-good odd.mp4"
    path.write_bytes(b"temporary media")
    monkeypatch.setattr(module.signal, "stop", False)
    logs, net, status = Mock(), Mock(), Mock()
    monkeypatch.setattr(module.signal, "show_log_text", logs)
    monkeypatch.setattr(module.signal, "show_net_info", net)
    monkeypatch.setattr(module.signal, "show_scrape_info", status)
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
    run_tasks = scraper._run_tasks_with_limit

    async def finish_tasks(*args):
        await run_tasks(*args)
        Flags.succ_count = success_count
        Flags.fail_count = fail_count

    monkeypatch.setattr(scraper, "_run_tasks_with_limit", finish_tasks)
    await scraper._run(FileMode.Default, [path])
    combined = "\n".join(call.args[0] for call in logs.call_args_list)
    assert f"评价后缀待检查（留原地）\n{path}：odd" in combined
    assert 'color="red"' in combined
    summary = next(call.args[0] for call in logs.call_args_list if "Total " in call.args[0])
    assert "留原地（评价后缀待检查）1" in summary
    assert f"Success {success_count} , Failed {fail_count}" in summary
    assert net.call_args.args[0] == summary
    if success_count == 0:
        assert "🔴 批次结束" in summary
        assert "🎉" not in summary
        assert "🎉" not in status.call_args.args[0]
        assert "留原地（评价后缀待检查）1" in status.call_args.args[0]
    else:
        assert "🎉" in summary
    assert Flags.succ_count == success_count and Flags.fail_count == fail_count
    assert Flags.remain_list == [path]


@pytest.mark.parametrize(
    "template,has_suffix",
    [
        ("{{ actor }}", False),
        ("{{ first_actor }}", False),
        ("{{ all_actor }}", False),
        ("{{ number }}", False),
        ("{{ title }}/{{ actor }}", False),
        ("{{ actor }}/{{ title }}", True),
        ('{{ actor }}/{{ title | replace("/", "-") }}', True),
        ("{% if title %}{{ title }}/{{ actor }}{% endif %}", False),
        ("{{ actor }}/{{ originaltitle }}", True),
        ("{{ actor }}/{{ fields.title }}", True),
        ("{{ actor }}/{{ fields['originaltitle'] }}", True),
    ],
)
def test_folder_suffix_only_for_final_title_template(monkeypatch, template, has_suffix):
    info, data = build()
    data.actor = data.all_actor = "performer" * 15
    data.originaltitle = "original" * 30
    monkeypatch.setattr(manager.config, "folder_name", template)
    folder, name = _get_folder_path(Path("output"), info, data)
    assert folder.name.endswith(info.evaluation_suffix) is has_suffix
    assert name.endswith(info.evaluation_suffix) is has_suffix
    assert len(name) <= 60
    if not has_suffix:
        assert info.evaluation_suffix not in folder.name
