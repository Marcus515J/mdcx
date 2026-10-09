import json

import pytest
from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow

from mdcx.base import file as files
from mdcx.config.models import Config
from mdcx.controllers.main_window import garbage_settings_dialog as ui
from mdcx.views.MDCx import Ui_MDCx


@pytest.fixture(scope="session")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture
def window(app, monkeypatch, tmp_path):
    window = QMainWindow()
    window.Ui = Ui_MDCx()
    window.Ui.setupUi(window)
    cfg = Config(garbage_enabled=True, garbage_dry_run=True)
    cfg.translate_config.llm_model = "keep-existing-model"
    monkeypatch.setattr(ui.manager, "config", cfg)
    monkeypatch.setattr(ui.manager, "_path", tmp_path / "config.json")
    window.Ui.lineEdit_escape_size.setText("100.0")
    window.pushButton_save_config_clicked = ui.manager.save
    ui.setup_garbage_settings_ui(window)
    yield window
    window.close()


def test_rule_editor_saves_custom_values_and_preserves_other_settings(window, monkeypatch, tmp_path):
    def accepted(dialog):
        assert dialog.mode_label.text().startswith("当前状态：演练")
        dialog.keywords.setPlainText(" 台湾uu\n新广告词\n新广告词\n\n")
        dialog.domain_rule.setChecked(False)
        dialog.dry_run.setChecked(False)
        assert "真实处理" in dialog.mode_label.text()
        dialog.size.setValue(123.5)
        dialog.directory.setText(str(tmp_path / "_待删"))
        dialog.action.setCurrentIndex(0)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ui.GarbageSettingsDialog, "exec", accepted)
    ui.open_garbage_settings(window)
    saved = Config.model_validate(json.loads(ui.manager.path.read_text()))
    assert saved.garbage_keywords == ["台湾uu", "新广告词"]
    assert saved.file_size == 123.5
    assert window.Ui.lineEdit_escape_size.text() == "123.5"
    assert not saved.garbage_dry_run and not saved.garbage_domain_rule
    assert saved.garbage_directory == str(tmp_path / "_待删")
    assert saved.translate_config.llm_model == "keep-existing-model"
    # The newly entered rule is consumed by the real scanner's classifier.
    path = tmp_path / "新广告词.mp4"
    with path.open("wb") as file:
        file.truncate(200 * 1024**2)
    assert files._garbage_video_rules(path) == ["黑名单:新广告词"]


def test_cancel_keeps_configuration_and_pending_size(window, monkeypatch):
    before = ui.manager.config.model_dump()
    window.Ui.lineEdit_escape_size.setText("250.5")

    def cancelled(dialog):
        assert dialog.size.value() == 250.5
        dialog.keywords.setPlainText("不要保存")
        dialog.enabled.setChecked(False)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(ui.GarbageSettingsDialog, "exec", cancelled)
    ui.open_garbage_settings(window)
    assert ui.manager.config.model_dump() == before
    assert window.Ui.lineEdit_escape_size.text() == "250.5"
    assert not ui.manager.path.exists()


def test_keywords_can_be_removed_and_permanent_mode_is_independent(app):
    cfg = Config()
    dialog = ui.GarbageSettingsDialog(cfg)
    dialog.keywords.setPlainText("")
    dialog.enabled.setChecked(True)
    dialog.dry_run.setChecked(True)
    dialog.domain_rule.setChecked(False)
    dialog.action.setCurrentIndex(1)
    dialog.apply_to_config(cfg)
    assert cfg.garbage_keywords == []
    assert cfg.garbage_enabled and cfg.garbage_dry_run and cfg.garbage_permanent_delete
    assert not cfg.garbage_domain_rule
    dialog.close()


def test_entry_is_visible_and_does_not_cover_existing_warning(window):
    button = window.Ui.pushButton_garbage_settings
    assert button.parent() is window.Ui.groupBox_61
    assert not button.geometry().intersects(window.Ui.label_271.geometry())
    assert window.Ui.groupBox_61.rect().contains(button.geometry())
