import json

import pytest
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget

from mdcx.base import file as files
from mdcx.config.models import Config
from mdcx.controllers.main_window import file_cleanup_settings as ui
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
    cfg.clean_name = ["明确指定的广告.txt"]
    cfg.clean_contains = ["新广告词"]
    monkeypatch.setattr(ui.manager, "config", cfg)
    monkeypatch.setattr(ui.manager, "_path", tmp_path / "config.json")

    def save():
        ui.save_file_cleanup_settings(window)
        ui.manager.save()

    window.pushButton_save_config_clicked = save
    ui.setup_file_cleanup_settings(window)
    yield window
    window.close()


def test_inline_editor_saves_mode_and_preserves_existing_rules(window, tmp_path):
    controls = window.Ui
    assert "演练" in controls.label_271.text()
    controls.checkBox_clean_dry_run.setChecked(False)
    controls.checkBox_clean_domain.setChecked(False)
    controls.doubleSpinBox_clean_video_size.setValue(123.5)
    controls.lineEdit_clean_directory.setText(str(tmp_path / "_待删"))
    controls.pushButton_save_cleanup.click()
    saved = Config.model_validate(json.loads(ui.manager.path.read_text(encoding="utf-8")))
    assert not saved.garbage_dry_run and not saved.garbage_domain_rule
    assert saved.file_size == 123.5 and float(controls.lineEdit_escape_size.text()) == 123.5
    assert saved.clean_name == ["明确指定的广告.txt"]
    assert saved.clean_contains == ["新广告词"]
    assert "garbage_keywords" not in saved.model_dump()
    assert saved.translate_config.llm_model == "keep-existing-model"
    assert "真实处理" in controls.label_271.text()
    path = tmp_path / "新 广 告 词.txt"
    path.write_bytes(b"ad")
    assert files._garbage_file_rules(path) == ["清理关键词:新广告词"]


def test_size_is_shared_in_both_directions(window):
    controls = window.Ui
    controls.lineEdit_escape_size.setText("250.5")
    assert controls.doubleSpinBox_clean_video_size.value() == 250.5
    controls.doubleSpinBox_clean_video_size.setValue(45)
    assert float(controls.lineEdit_escape_size.text()) == 45


def test_manual_clean_available_with_auto_disabled_and_delete_visible(window):
    controls = window.Ui
    controls.checkBox_auto_clean.setChecked(False)
    controls.comboBox_clean_action.setCurrentIndex(1)
    controls.checkBox_clean_dry_run.setChecked(False)
    controls.pushButton_save_cleanup.click()
    assert not ui.manager.config.garbage_enabled
    assert ui.manager.config.garbage_permanent_delete
    assert "永久删除" in controls.label_271.text()
    assert controls.pushButton_check_and_clean_files.isEnabled()


def test_options_are_inside_existing_group_and_next_group_is_clear(window):
    controls = window.Ui
    assert not hasattr(controls, "pushButton_garbage_settings")
    panel = controls.groupBox_61.findChild(QWidget, "fileCleanupOptions")
    assert panel is not None and controls.groupBox_61.rect().contains(panel.geometry())
    for child in (controls.pushButton_save_cleanup, controls.pushButton_check_and_clean_files, controls.label_271):
        assert controls.groupBox_61.rect().contains(child.geometry())
    assert controls.groupBox_9.y() > controls.groupBox_61.geometry().bottom()
    assert controls.scrollAreaWidgetContents_guaxiaomulu.height() > controls.groupBox_9.geometry().bottom()
    assert controls.checkBox_i_agree_clean.isHidden()
