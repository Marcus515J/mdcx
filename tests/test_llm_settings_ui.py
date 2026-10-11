import json
import threading
import time

import pytest
from pydantic import HttpUrl
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication, QLineEdit, QMainWindow

from mdcx.config.models import Config, TranslateConfig
from mdcx.controllers.main_window import llm_settings as settings
from mdcx.controllers.main_window import style
from mdcx.views.MDCx import Ui_MDCx


def wait_ui(app, condition, timeout=5):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert condition()


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, monkeypatch, tmp_path):
    window = QMainWindow()
    window.Ui = Ui_MDCx()
    window.Ui.setupUi(window)
    cfg = Config(
        translate_config=TranslateConfig(
            llm_url="https://api.example.com/v1",
            llm_model="existing-model",
            llm_key="synthetic-key",
            llm_fallback_url="https://api.deepseek.com/v1",
            llm_fallback_model="deepseek-chat",
            llm_fallback_key="synthetic-backup",
            llm_refusal_retries=2,
            llm_fallback_read_timeout=90,
            llm_prompt_title="private synthetic title {content}",
            llm_prompt_outline="private synthetic outline {content}",
            llm_temperature=0.90,
        )
    )
    monkeypatch.setattr(settings.manager, "config", cfg)
    monkeypatch.setattr(settings.manager, "_path", tmp_path / "config.json")
    settings.setup_llm_settings(window)
    window.Ui.lineEdit_llm_url.setText(str(cfg.translate_config.llm_url))
    window.Ui.lineEdit_llm_model.setText(cfg.translate_config.llm_model)
    window.Ui.lineEdit_llm_key.setText(cfg.translate_config.llm_key)

    def save():
        settings.save_llm_settings(window)
        cfg.translate_config.llm_url = HttpUrl(window.Ui.lineEdit_llm_url.text())
        cfg.translate_config.llm_model = window.Ui.lineEdit_llm_model.text()
        cfg.translate_config.llm_key = window.Ui.lineEdit_llm_key.text()
        settings.manager.save()

    window.Ui.pushButton_save_config.clicked.connect(save)
    window.Ui.stackedWidget.setCurrentWidget(window.Ui.page_setting)
    window.Ui.tabWidget.setCurrentWidget(window.Ui.tab_6)
    window.show()
    app.processEvents()
    yield window, app
    window.local_model_controller.shutdown()
    window.close()


def test_existing_settings_roundtrip_and_local_preset(window, tmp_path):
    window, _ = window
    ui = window.Ui
    assert ui.lineEdit_llm_fallback_key.echoMode() == QLineEdit.EchoMode.Password
    ui.pushButton_save_config.click()
    saved = Config.model_validate_json((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved.translate_config.llm_model == "existing-model"
    assert saved.translate_config.llm_key == "synthetic-key"
    assert saved.translate_config.llm_fallback_key == "synthetic-backup"
    assert saved.translate_config.llm_refusal_retries == 2
    assert saved.translate_config.llm_fallback_read_timeout == 90
    ui.pushButton_local_hymt2.click()
    assert ui.spinBox_llm_max_try.isEnabled()
    assert ui.lineEdit_llm_key.text() == "synthetic-key"
    ui.pushButton_save_config.click()
    saved = Config.model_validate_json((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert str(saved.translate_config.llm_url) == "https://api.example.com/v1"
    assert saved.translate_config.llm_model == "existing-model"
    assert saved.translate_config.llm_refusal_retries == 2
    assert saved.translate_config.llm_fallback_key == ""
    assert str(saved.translate_config.llm_fallback_url) == "http://127.0.0.1:8080/v1"
    assert saved.translate_config.llm_fallback_model == "HY-MT2-7B-Q8_0"
    assert saved.translate_config.llm_prompt_title == "private synthetic title {content}"
    assert saved.translate_config.llm_prompt_outline == "private synthetic outline {content}"
    assert saved.translate_config.llm_temperature == 0.90


def test_disable_backup_and_reload(window):
    window, _ = window
    window.Ui.lineEdit_llm_fallback_url.clear()
    settings.save_llm_settings(window)
    assert settings.manager.config.translate_config.llm_fallback_url is None
    settings.load_llm_settings(window)
    assert window.Ui.lineEdit_llm_fallback_url.text() == ""
    assert window.Ui.lineEdit_llm_fallback_key.text() == "synthetic-backup"


@pytest.mark.parametrize("width,height", [(850, 700), (1200, 900)])
@pytest.mark.parametrize("dark", [False, True])
def test_controls_fit_translation_group_and_following_groups(window, width, height, dark):
    window, app = window
    ui = window.Ui
    window.dark_mode, window.window_radius, window.window_border = dark, 10, 1
    window.set_dark_style = lambda: style.set_dark_style(window)
    style.set_style(window)
    window.resize(width, height)
    ui.groupBox_llm.show()
    app.processEvents()
    for control in (
        ui.spinBox_llm_read_timeout,
        ui.spinBox_llm_refusal_retries,
        ui.lineEdit_llm_fallback_url,
        ui.lineEdit_llm_fallback_model,
        ui.lineEdit_llm_fallback_key,
        ui.spinBox_llm_fallback_read_timeout,
        ui.comboBox_hymt2_server,
        ui.comboBox_hymt2_model,
        ui.pushButton_hymt2_start,
        ui.pushButton_hymt2_stop,
    ):
        top_left = control.mapTo(ui.groupBox_llm, QPoint(0, 0))
        assert ui.groupBox_llm.rect().contains(top_left)
        assert ui.groupBox_llm.rect().contains(top_left + QPoint(control.width() - 1, control.height() - 1))
        assert control.height() >= 30
    assert ui.groupBox_82.y() > ui.groupBox_llm.geometry().bottom()
    assert ui.scrollAreaWidgetContents_fanyi.minimumHeight() > ui.groupBox_89.geometry().bottom()
    expected = style.get_theme_tokens(dark)["text"].lower()
    for control in (ui.lineEdit_llm_fallback_url, ui.spinBox_llm_read_timeout, ui.comboBox_hymt2_model):
        assert control.palette().color(QPalette.ColorRole.Text).name() == expected
        assert control.styleSheet() == ""
    assert ui.spinBox_llm_read_timeout.lineEdit().palette().color(QPalette.ColorRole.Text).name() == expected
    assert ui.pushButton_save_config.isVisible()
    assert window.rect().contains(ui.pushButton_save_config.mapTo(window, ui.pushButton_save_config.rect().center()))
    ui.scrollArea_11.ensureWidgetVisible(ui.pushButton_hymt2_start)
    app.processEvents()
    viewport = ui.scrollArea_11.viewport()
    assert viewport.rect().contains(ui.pushButton_hymt2_start.mapTo(viewport, ui.pushButton_hymt2_start.rect().center()))


def test_paths_save_reload_preserves_cloud_prompts_and_temperature(window, tmp_path):
    window, app = window
    ui = window.Ui
    ui.lineEdit_hymt2_root.setText("H")
    ui.comboBox_hymt2_server.setCurrentText("H:\\中文 [安装] 空 格\\llama-server.exe")
    ui.comboBox_hymt2_model.setCurrentText("H:\\中文 [安装] 空 格\\HY-MT2-7B-Q8_0.gguf")
    before = settings.manager.config.translate_config.model_dump()
    ui.pushButton_save_config.click()
    saved = Config.model_validate_json((tmp_path / "config.json").read_text(encoding="utf-8"))
    settings.manager.config = saved
    settings.load_llm_settings(window)
    assert ui.lineEdit_hymt2_root.text() == "H"
    assert ui.comboBox_hymt2_server.currentText() == saved.translate_config.local_model_server_path
    assert ui.comboBox_hymt2_model.currentText() == saved.translate_config.local_model_path
    for key in ("llm_url", "llm_model", "llm_key", "llm_prompt_title", "llm_prompt_outline", "llm_temperature"):
        assert saved.translate_config.model_dump()[key] == before[key]


def test_background_start_repeat_cancel_and_scrape_guard(window, monkeypatch):
    window, app = window
    controller = window.local_model_controller
    controller.timer.stop()
    begun = threading.Event()
    calls = []

    def start(*args):
        calls.append(args)
        begun.set()
        assert controller.service.cancel.wait(5)
        raise InterruptedError("已取消启动。")

    monkeypatch.setattr(controller.service, "start", start)
    controller.start()
    controller.start()
    wait_ui(app, begun.is_set)
    assert len(calls) == 1 and controller.busy == "start"
    assert not window.Ui.pushButton_hymt2_start.isEnabled()
    controller._scrape_started()
    controller.stop()
    assert not controller.service.cancel.is_set()
    assert not window.Ui.pushButton_hymt2_stop.isEnabled()
    controller._scrape_finished()
    controller.stop()
    wait_ui(app, lambda: not controller.busy)
    assert "已取消" in window.Ui.label_hymt2_status.text()


def test_reused_service_sets_actual_backup_id_only(window):
    window, _ = window
    controller, ui = window.local_model_controller, window.Ui
    controller.timer.stop()
    controller.service.reused = True
    controller.service.model_id = "HY-MT2-existing-id"
    primary = (ui.lineEdit_llm_url.text(), ui.lineEdit_llm_model.text(), ui.lineEdit_llm_key.text())
    controller._finished("start", "HY-MT2-existing-id")
    assert ui.lineEdit_llm_fallback_model.text() == "HY-MT2-existing-id"
    assert (ui.lineEdit_llm_url.text(), ui.lineEdit_llm_model.text(), ui.lineEdit_llm_key.text()) == primary
    assert not ui.pushButton_hymt2_stop.isEnabled()
    assert "外部服务" in ui.label_hymt2_status.text()


def test_late_start_result_after_config_reload_does_not_overwrite_backup(window):
    window, _ = window
    controller, ui = window.local_model_controller, window.Ui
    generation = controller.config_generation
    settings.load_llm_settings(window)
    controller._finished("start", "HY-MT2-late-result", generation)
    assert ui.lineEdit_llm_fallback_model.text() == "deepseek-chat"
    assert ui.lineEdit_llm_fallback_key.text() == "synthetic-backup"
    assert "配置已切换" in ui.label_hymt2_status.text()


def test_exit_cleanup_only_after_confirmation_and_not_tray_hide(window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    from mdcx.config.enums import Switch
    from mdcx.controllers.main_window.main_window import MyMAinWindow

    window, _ = window
    controller = window.local_model_controller
    controller.timer.stop()
    calls = []
    monkeypatch.setattr(controller.service, "close", lambda: calls.append("model closed"))
    window.exit_app = lambda: MyMAinWindow.exit_app(window)
    monkeypatch.setattr(settings.manager.config, "switch_on", [Switch.SHOW_DIALOG_EXIT, Switch.HIDE_CLOSE])
    monkeypatch.setattr(QMessageBox, "exec", lambda _: QMessageBox.StandardButton.No)
    MyMAinWindow.ready_to_exit(window)
    assert calls == [] and not controller.closed
    MyMAinWindow.pushButton_close_clicked(window)
    assert calls == [] and not controller.closed
    monkeypatch.setattr(settings.manager, "save", lambda: None)
    monkeypatch.setattr("mdcx.controllers.main_window.main_window.os._exit", lambda _: calls.append("exit"))
    monkeypatch.setattr(QMessageBox, "exec", lambda _: QMessageBox.StandardButton.Yes)
    MyMAinWindow.ready_to_exit(window)
    assert calls == ["model closed", "exit"] and controller.closed


def test_synthetic_old_json_keeps_explicit_primary_and_unrelated_settings():
    old = {
        "media_path": "D:/Movies",
        "file_size": 321.5,
        "translate_config": {
            "llm_url": "https://api.example.com/v1",
            "llm_model": "old-model",
            "llm_key": "synthetic",
            "llm_prompt_title": "old prompt {content}",
        },
    }
    Config.update(old)
    cfg = Config.model_validate(old)
    again = Config.model_validate(json.loads(cfg.model_dump_json()))
    assert again.media_path == "D:/Movies" and again.file_size == 321.5
    assert again.translate_config.llm_model == "old-model"
    assert again.translate_config.llm_key == "synthetic"
    assert str(again.translate_config.llm_url) == "https://api.example.com/v1"
    assert again.translate_config.llm_prompt_title == "old prompt {content}"
