from collections import deque
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PyQt6.QtWidgets import QApplication, QMainWindow

from mdcx.config.models import Config
from mdcx.controllers.main_window import main_window as module
from mdcx.controllers.main_window.main_window import MyMAinWindow
from mdcx.models.flags import Flags
from mdcx.signals import signal_qt
from mdcx.views.MDCx import Ui_MDCx


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, monkeypatch, tmp_path):
    # Use the real controller methods and real widgets without startup/network/config loading.
    monkeypatch.setattr(MyMAinWindow, "__init__", lambda self: QMainWindow.__init__(self))
    window = MyMAinWindow()
    window.window_radius = 0
    window.Ui = Ui_MDCx()
    window.Ui.setupUi(window)
    window.main_log_queue = deque()
    window.main_log_batch_size = 80
    window.main_log_max_count = 10000
    window.logs_counts = window.req_logs_counts = 0
    window._request_log_file = None
    window._taskbar_progress_active = False
    window._taskbar_progress = Mock()
    config = Config(save_log=True, show_web_log=True)
    monkeypatch.setattr(module.manager, "config", config)
    monkeypatch.setattr(module.manager, "data_folder", tmp_path)
    monkeypatch.setattr(Flags, "log_txt", None)
    monkeypatch.setattr(signal_qt, "stop", False)
    signal_qt.get_log()
    yield window, config, tmp_path
    for handle in (Flags.log_txt, window._request_log_file):
        if handle is not None:
            handle.close()
    signal_qt.get_log()
    window.deleteLater()
    app.processEvents()


@pytest.mark.parametrize("request_first", [False, True])
def test_request_panel_paired_files_are_written_without_close(window, request_first):
    win, _, root = window
    displayed = []
    win.main_req_logs_show.connect(displayed.append)
    text = "思考内容：有（123 字符）\n翻译失败诊断：合成异常\n被拒片段：合成文本\n人名对照获取失败\n<test> & 原样"
    if not request_first:
        win._write_main_logs_to_file(["主日志"])
    signal_qt.add_log(text)
    win.show_detail_log()
    if request_first:
        win._write_main_logs_to_file(["主日志"])
    main = next(p for p in (root / "Log").glob("*.txt") if not p.stem.endswith("-请求"))
    request = main.with_stem(main.stem + "-请求")
    # Read while unbuffered handles are still open, as after an interrupted process.
    assert "主日志" in main.read_text(encoding="utf-8")
    assert text in request.read_text(encoding="utf-8")
    assert "思考内容" in displayed[0]
    assert "&lt;test&gt;" in displayed[0]
    before = request.read_text(encoding="utf-8")
    win._request_log_file.close()
    win._write_request_log_to_file("下一行")
    assert request.read_text(encoding="utf-8") == before + "下一行\n"


def test_save_disabled_writes_neither_file_but_still_displays(window):
    win, config, root = window
    config.save_log = False
    displayed = []
    win.main_req_logs_show.connect(displayed.append)
    win.show_log_text("主日志")
    win._flush_main_log_queue()
    signal_qt.add_log("思考内容：无")
    win.show_detail_log()
    assert displayed
    assert not (root / "Log").exists()


def test_save_toggle_does_not_append_while_disabled_and_hidden_panel_still_saved(window):
    win, config, root = window
    win._write_request_log_to_file("before")
    config.save_log = False
    win._write_request_log_to_file("disabled")
    win._write_main_logs_to_file(["disabled"])
    config.save_log = True
    config.show_web_log = False
    signal_qt.add_log("hidden")
    win.show_detail_log()
    request = next((root / "Log").glob("*-请求.txt"))
    assert "before" in request.read_text(encoding="utf-8") and "hidden" in request.read_text(encoding="utf-8")
    assert all("disabled" not in p.read_text(encoding="utf-8") for p in (root / "Log").glob("*.txt"))


def test_request_credentials_redacted_without_losing_other_diagnostics(window):
    win, _, root = window
    win._write_request_log_to_file(
        "GET https://user:pass@example.test/path?token=secret-value&cookie=synthetic-query-cookie&id=123\n"
        "Authorization: Bearer synthetic-key\nCookie: session=synthetic-cookie\n"
        "api_key=synthetic-api-key\nKey: synthetic-plain-key\ntoken=synthetic-token\nsecret='synthetic quoted secret'\n思考内容：有（8 字符）"
    )
    text = next((root / "Log").glob("*-请求.txt")).read_text(encoding="utf-8")
    for secret in (
        "user:pass",
        "secret-value",
        "synthetic-key",
        "synthetic-cookie",
        "synthetic-api-key",
        "synthetic-plain-key",
        "synthetic-token",
        "synthetic-query-cookie",
        "synthetic quoted secret",
    ):
        assert secret not in text
    assert "example.test/path?token=[已隐藏]&cookie=[已隐藏]&id=123" in text
    assert "思考内容：有（8 字符）" in text


def test_taskbar_counts_completed_success_and_failure_and_clears_on_end(window, monkeypatch):
    win, _, _ = window
    monkeypatch.setattr(module, "IS_WINDOWS", True)
    monkeypatch.setattr(Flags, "stop_requested", False)
    monkeypatch.setattr(Flags, "total_count", 23)
    monkeypatch.setattr(Flags, "scrape_done", 5)
    monkeypatch.setattr(Flags, "succ_count", 3)
    monkeypatch.setattr(Flags, "fail_count", 2)
    win.set_processbar(90)  # Existing UI percentage uses started tasks; taskbar uses completed.
    win._taskbar_progress.update.assert_called_with(int(win.winId()), 5, 23)
    win.set_processbar(0)
    win._taskbar_progress.clear.assert_called_with(int(win.winId()))
    assert not win._taskbar_progress_active


def test_confirmed_stop_clears_immediately_and_ignores_late_progress(window, monkeypatch):
    win, config, _ = window
    config.switch_on = []
    win.Ui.pushButton_start_cap.setText("■ 停止")
    win._taskbar_progress_active = True
    win.threads_list = []
    win.show_stop_info_thread = Mock()
    monkeypatch.setattr(module, "IS_WINDOWS", True)
    monkeypatch.setattr(Flags, "stop_requested", False)
    monkeypatch.setattr(
        module, "executor", SimpleNamespace(run=Mock(side_effect=lambda coro: coro.close()), cancel_async=Mock())
    )
    win.pushButton_stop_scrape_clicked()
    assert Flags.stop_requested
    win._taskbar_progress.clear.assert_called_once()
    win.set_processbar(70)
    win._update_taskbar_progress()
    win._taskbar_progress.update.assert_not_called()


def test_switching_log_folder_keeps_existing_pair_and_non_windows_skips_progress(window, monkeypatch):
    win, _, root = window
    win._write_request_log_to_file("original")
    old_pair = {p.name: p.read_bytes() for p in (root / "Log").glob("*.txt")}
    monkeypatch.setattr(module.manager, "data_folder", root / "other")
    win._write_request_log_to_file("new folder")
    assert old_pair == {p.name: p.read_bytes() for p in (root / "Log").glob("*.txt")}
    assert "new folder" in next((root / "other" / "Log").glob("*-请求.txt")).read_text(encoding="utf-8")
    monkeypatch.setattr(module, "IS_WINDOWS", False)
    win.set_processbar(70)
    win._update_taskbar_progress()
    win._taskbar_progress.update.assert_not_called()
