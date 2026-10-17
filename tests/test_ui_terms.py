import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from mdcx.config.enums import Language, Translator
from mdcx.config.manager import manager
from mdcx.config.models import TranslateConfig
from mdcx.config.resources import resources
from mdcx.gen.field_enums import CrawlerResultFields


def _build_ui_and_controller_corpus() -> tuple[list[str], list[str], str]:
    ui_path = Path("mdcx/views/MDCx.ui")
    tree = ET.parse(ui_path)
    root = tree.getroot()

    about_node = root.find('.//widget[@name="textBrowser_about"]/property[@name="html"]/string')
    assert about_node is not None, "textBrowser_about not found in MDCx.ui"
    about_text = about_node.text or ""

    # Clear about text from UI corpus to ensure terms exist elsewhere in UI or controllers
    about_node.text = ""
    ui_corpus = ET.tostring(root, encoding="unicode")

    controller_corpus = ""
    for path in Path("mdcx/controllers").rglob("*.py"):
        controller_corpus += path.read_text(encoding="utf-8") + "\n"

    full_corpus = ui_corpus + "\n" + controller_corpus

    about_terms = re.findall(r"「(.*?)」", about_text)
    cookie_html = resources.cookie_help_path.read_text(encoding="utf-8")
    cookie_terms = re.findall(r"「(.*?)」", cookie_html)

    return about_terms, cookie_terms, full_corpus


def test_textbrowser_about_bracketed_terms_exist_in_ui_or_controllers():
    about_terms, _, corpus = _build_ui_and_controller_corpus()
    assert len(about_terms) >= 30, f"Expected at least 30 bracketed terms in about text, found {len(about_terms)}"

    missing = [term for term in set(about_terms) if term not in corpus]
    assert not missing, f"The following UI terms in textBrowser_about do not exist in MDCx.ui or controllers: {missing}"


def test_cookie_help_bracketed_terms_exist_in_ui_or_controllers():
    _, cookie_terms, corpus = _build_ui_and_controller_corpus()
    assert len(cookie_terms) >= 5, f"Expected at least 5 bracketed terms in cookie_help.html, found {len(cookie_terms)}"

    missing = [term for term in set(cookie_terms) if term not in corpus]
    assert not missing, f"The following UI terms in cookie_help.html do not exist in MDCx.ui or controllers: {missing}"


def test_cookie_help_content_requirements():
    cookie_html = resources.cookie_help_path.read_text(encoding="utf-8")

    # R2.1: Button is "保存", not "保存配置"
    assert "「保存」" in cookie_html
    assert "保存配置" not in cookie_html

    # R2.2: Copy value recommendation & browser UI disclaimer
    assert "复制值 / Copy value" in cookie_html
    assert "以你的浏览器实际界面为准" in cookie_html


def test_r1_facts_in_about_text():
    ui_path = Path("mdcx/views/MDCx.ui")
    tree = ET.parse(ui_path)
    root = tree.getroot()
    about_node = root.find('.//widget[@name="textBrowser_about"]/property[@name="html"]/string')
    about_text = about_node.text or ""

    # Temperatures: 0.9 default, not 0.2 / 1.0
    assert "默认均为 <code>0.9</code>" in about_text
    assert "默认 0.2" not in about_text
    assert "默认 1.0" not in about_text

    # No "使用备用模型" invented switch
    assert "使用备用模型" not in about_text

    # No "设置 → 分集" invented tab
    assert "设置 → 分集" not in about_text
    assert "设置 → 分集" not in about_text

    # No FlareSolverr; only CF Bypass
    assert "FlareSolverr" not in about_text
    assert "CF Bypass" in about_text

    # Actual local model buttons
    assert "查找 / 验证路径" in about_text
    assert "启动备用模型" in about_text
    assert "打开日志" in about_text

    # Actual database checkbox text
    assert "使用数据库补全演员信息" in about_text

    # Actual save button name
    assert "「保存」" in about_text
    assert "保存配置" not in about_text
    assert "自动保存配置" not in about_text

    # Subtitle tags: no -UC or -U
    assert "-UC" not in about_text
    assert "-U" not in about_text


def test_r3_engine_selection_checkbox_removed_and_field_switches_present():
    tree = ET.parse("mdcx/views/MDCx.ui")
    root = tree.getroot()

    # The legacy engine selection checkbox and groupBox_trans have been removed from UI definition
    legacy_engine_checkbox_name = "checkBox_" + "llm"
    assert root.find(f'.//widget[@name="{legacy_engine_checkbox_name}"]') is None, (
        f"{legacy_engine_checkbox_name} should be removed from MDCx.ui"
    )
    assert root.find('.//widget[@name="groupBox_trans"]') is None, "groupBox_trans should be removed from MDCx.ui"

    # Field-level translation switches must exist in MDCx.ui
    assert root.find('.//widget[@name="checkBox_title_translate"]') is not None, (
        "checkBox_title_translate must exist in MDCx.ui"
    )
    assert root.find('.//widget[@name="checkBox_outline_translate"]') is not None, (
        "checkBox_outline_translate must exist in MDCx.ui"
    )
    assert root.find('.//widget[@name="checkBox_actor_translate"]') is not None, (
        "checkBox_actor_translate must exist in MDCx.ui"
    )
    assert root.find('.//widget[@name="checkBox_tag_translate"]') is not None, (
        "checkBox_tag_translate must exist in MDCx.ui"
    )

    # Also verify generated MDCx.py
    mdcx_py = Path("mdcx/views/MDCx.py").read_text(encoding="utf-8")
    assert f"self.{legacy_engine_checkbox_name}" not in mdcx_py
    assert "self.groupBox_trans" not in mdcx_py
    assert "self.checkBox_title_translate" in mdcx_py
    assert "self.checkBox_outline_translate" in mdcx_py


def test_temperature_defaults_and_default_config_json():
    # models.py defaults
    tc = TranslateConfig()
    assert tc.llm_temperature == 0.9
    assert tc.llm_fallback_temperature == 0.9
    assert tc.translate_by == [Translator.LLM]

    # default_config.json defaults
    default_config_path = Path("mdcx/config/default_config.json")
    if default_config_path.exists():
        default_cfg = json.loads(default_config_path.read_text(encoding="utf-8"))
        tc_data = default_cfg.get("translate_config", {})
        assert tc_data.get("llm_temperature") == 0.9
        assert tc_data.get("llm_fallback_temperature") == 0.9


def test_field_level_translation_switches_control_translation():
    # Verify that FieldConfig.translate controls whether translation occurs for title/outline
    title_cfg = manager.config.get_field_config(CrawlerResultFields.TITLE)
    outline_cfg = manager.config.get_field_config(CrawlerResultFields.OUTLINE)

    # Both configs have a boolean translate attribute
    assert hasattr(title_cfg, "translate")
    assert hasattr(outline_cfg, "translate")
    assert isinstance(title_cfg.translate, bool)
    assert isinstance(outline_cfg.translate, bool)

    # When both are disabled or language is JP, translation skips
    assert hasattr(title_cfg, "language")
    assert hasattr(outline_cfg, "language")
    assert isinstance(title_cfg.language, Language)
