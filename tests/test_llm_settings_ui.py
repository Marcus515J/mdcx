import json

import pytest
from pydantic import HttpUrl
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication, QLineEdit, QMainWindow

from mdcx.config.models import Config, TranslateConfig
from mdcx.controllers.main_window import llm_settings as settings
from mdcx.controllers.main_window import style
from mdcx.views.MDCx import Ui_MDCx


@pytest.fixture
def window(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
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
    yield window, app
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
    assert ui.checkBox_llm.isChecked()
    assert not ui.spinBox_llm_max_try.isEnabled()
    assert ui.lineEdit_llm_key.text() == ""
    ui.pushButton_save_config.click()
    saved = Config.model_validate_json((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert str(saved.translate_config.llm_url) == "http://127.0.0.1:8080/v1"
    assert saved.translate_config.llm_model == "HY-MT2-7B-Q8_0"
    assert saved.translate_config.llm_refusal_retries == 1
    assert saved.translate_config.llm_fallback_key == "synthetic-backup"


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
    ):
        top_left = control.mapTo(ui.groupBox_llm, QPoint(0, 0))
        assert ui.groupBox_llm.rect().contains(top_left)
        assert ui.groupBox_llm.rect().contains(top_left + QPoint(control.width() - 1, control.height() - 1))
        assert control.height() >= 30
    assert ui.groupBox_82.y() > ui.groupBox_llm.geometry().bottom()
    assert ui.scrollAreaWidgetContents_fanyi.minimumHeight() > ui.groupBox_89.geometry().bottom()


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
