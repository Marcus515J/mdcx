import pytest

from mdcx.base.translate import TranslateResult
from mdcx.config.enums import Language, Translator
from mdcx.config.models import Config
from mdcx.models.types import CrawlersResult


def test_config_update_migrate_legacy_llm_prompt_in_translate_config():
    data = {
        "translate_config": {
            "llm_prompt": "legacy {content}",
        }
    }

    Config.update(data)

    tc = data["translate_config"]
    assert "llm_prompt" not in tc
    assert tc["llm_prompt_title"] == "legacy {content}"
    assert tc["llm_prompt_outline"] == "legacy {content}"


def test_config_update_migrate_legacy_llm_prompt_top_level():
    data = {
        "llm_prompt": "legacy-top {content}",
    }

    Config.update(data)

    tc = data["translate_config"]
    assert tc["llm_prompt_title"] == "legacy-top {content}"
    assert tc["llm_prompt_outline"] == "legacy-top {content}"


@pytest.mark.parametrize(
    ("sample_name", "legacy_translate_config"),
    [
        (
            "sample_1_only_google",
            {"translate_by": ["google"]},
        ),
        (
            "sample_2_all_five_engines",
            {"translate_by": ["google", "baidu", "deepl", "deeplx", "llm"]},
        ),
        (
            "sample_3_legacy_keys_and_engines",
            {
                "translate_by": ["google", "baidu", "deepl", "deeplx"],
                "deepl_key": "xxx",
                "baidu_appid": "123",
                "baidu_key": "abc",
                "deeplx_url": "http://127.0.0.1:1188/translate",
            },
        ),
    ],
)
def test_legacy_translate_config_migration_and_save_reload(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    sample_name: str,
    legacy_translate_config: dict,
):
    import json

    from mdcx.config.manager import ConfigManager

    cfg_file = tmp_path / f"{sample_name}.json"
    mark_file = tmp_path / "MARK_FILE"
    monkeypatch.setattr("mdcx.config.manager.MARK_FILE", mark_file)

    raw_data = Config().model_dump(mode="json")
    raw_data["translate_config"].update(legacy_translate_config)
    cfg_file.write_text(json.dumps(raw_data, ensure_ascii=False, indent=2), encoding="UTF-8")
    mark_file.write_text(str(cfg_file), encoding="UTF-8")

    mgr = ConfigManager()
    errors = mgr.load()

    # 不抛异常、不产生验证失败错误（不会触发 load_config 的 _failed.json 分支）
    assert not any("验证失败" in err for err in errors), f"Unexpected errors: {errors}"
    assert mgr.path == cfg_file
    assert not (tmp_path / f"{sample_name}_failed.json").exists()
    assert mgr.config.translate_config.translate_by == [Translator.LLM]

    # 保存再加载后仍为 [Translator.LLM]，且已删字段不再出现在保存文件中
    mgr.save()
    saved_raw = json.loads(cfg_file.read_text(encoding="UTF-8"))
    saved_tc = saved_raw["translate_config"]
    for removed_key in ("baidu_appid", "baidu_key", "deepl_key", "deeplx_url"):
        assert removed_key not in saved_tc

    reload_errors = mgr.load()
    assert not any("验证失败" in err for err in reload_errors)
    assert mgr.config.translate_config.translate_by == [Translator.LLM]


@pytest.mark.asyncio
async def test_llm_translate_uses_separate_prompts(monkeypatch: pytest.MonkeyPatch):
    from mdcx.base import translate as base_translate

    cfg = base_translate.manager.config.translate_config
    monkeypatch.setattr(cfg, "llm_prompt_title", "TITLE::{content}::{lang}")
    monkeypatch.setattr(cfg, "llm_prompt_outline", "OUTLINE::{content}::{lang}")

    async def fake_ask(*, user_prompt: str, **kwargs):
        return user_prompt

    monkeypatch.setattr(base_translate.manager.computed.llm_client, "ask", fake_ask)

    title, outline, error = await base_translate.llm_translate("Hello", "World")

    assert error is None
    assert title == "TITLE::Hello::简体中文"
    assert outline == "OUTLINE::World::简体中文"


@pytest.mark.asyncio
async def test_llm_translate_normalizes_literal_linebreaks(monkeypatch: pytest.MonkeyPatch):
    from mdcx.base import translate as base_translate

    cfg = base_translate.manager.config.translate_config
    monkeypatch.setattr(cfg, "llm_prompt_title", "TITLE::{content}")
    monkeypatch.setattr(cfg, "llm_prompt_outline", "OUTLINE::{content}")

    async def fake_ask(*, user_prompt: str, **kwargs):
        if user_prompt.startswith("TITLE::"):
            return "标题第1行\\n标题第2行\\r\\n标题第3行"
        return "简介第1行\\n简介第2行"

    monkeypatch.setattr(base_translate.manager.computed.llm_client, "ask", fake_ask)

    title, outline, error = await base_translate.llm_translate("Hello", "World")

    assert error is None
    assert title == "标题第1行\n标题第2行\n标题第3行"
    assert outline == "简介第1行\n简介第2行"


@pytest.mark.asyncio
async def test_llm_translate_normalizes_br_tags(monkeypatch: pytest.MonkeyPatch):
    from mdcx.base import translate as base_translate

    cfg = base_translate.manager.config.translate_config
    monkeypatch.setattr(cfg, "llm_prompt_title", "TITLE::{content}")
    monkeypatch.setattr(cfg, "llm_prompt_outline", "OUTLINE::{content}")

    async def fake_ask(*, user_prompt: str, **kwargs):
        if user_prompt.startswith("TITLE::"):
            return "第一行<br>第二行<BR />第三行"
        return "甲行&lt;br&gt;乙行"

    monkeypatch.setattr(base_translate.manager.computed.llm_client, "ask", fake_ask)

    title, outline, error = await base_translate.llm_translate("Hello", "World")

    assert error is None
    assert title == "第一行\n第二行\n第三行"
    assert outline == "甲行\n乙行"


@pytest.mark.asyncio
async def test_translate_title_outline_supports_english(monkeypatch: pytest.MonkeyPatch):
    from mdcx.core import translate as core_translate

    class _FieldCfg:
        def __init__(self, language: Language, translate: bool):
            self.language = language
            self.translate = translate

    class _TranslateCfg:
        def __init__(self):
            self.translate_by = [Translator.LLM]

    class _Cfg:
        def __init__(self):
            self.translate_config = _TranslateCfg()

        def get_field_config(self, _field):
            return _FieldCfg(Language.ZH_CN, True)

    class _Manager:
        def __init__(self):
            self.config = _Cfg()

    async def fake_translate_with_engine(*args, **kwargs):
        title = args[1]
        outline = args[2]
        return TranslateResult(
            title=f"CN::{title}",
            outline=f"CN::{outline}",
            error=None,
            engine=Translator.LLM,
            translated_title=True,
            translated_outline=True,
        )

    monkeypatch.setattr(core_translate, "manager", _Manager())
    monkeypatch.setattr(core_translate, "translate_with_engine", fake_translate_with_engine)
    monkeypatch.setattr(core_translate, "get_translator_skip_reason", lambda _translator: None)

    data = CrawlersResult.empty()
    data.title = "A western movie title"
    data.outline = "An English overview."

    await core_translate.translate_title_outline(data, cd_part="-CD1", movie_number="ABC-123")

    assert data.title == "CN::A western movie title"
    assert data.outline == "CN::An English overview."


@pytest.mark.asyncio
async def test_translate_title_outline_supports_long_english_outline(monkeypatch: pytest.MonkeyPatch):
    from mdcx.core import translate as core_translate

    class _FieldCfg:
        def __init__(self, language: Language, translate: bool):
            self.language = language
            self.translate = translate

    class _TranslateCfg:
        def __init__(self):
            self.translate_by = [Translator.LLM]

    class _Cfg:
        def __init__(self):
            self.translate_config = _TranslateCfg()

        def get_field_config(self, _field):
            return _FieldCfg(Language.ZH_CN, True)

    class _Manager:
        def __init__(self):
            self.config = _Cfg()

    async def fake_translate_with_engine(*args, **kwargs):
        title = args[1]
        outline = args[2]
        return TranslateResult(
            title=f"CN::{title}",
            outline=f"CN::{outline}",
            error=None,
            engine=Translator.LLM,
            translated_title=True,
            translated_outline=True,
        )

    monkeypatch.setattr(core_translate, "manager", _Manager())
    monkeypatch.setattr(core_translate, "translate_with_engine", fake_translate_with_engine)
    monkeypatch.setattr(core_translate, "get_translator_skip_reason", lambda _translator: None)

    data = CrawlersResult.empty()
    data.title = "Youngermommy.24.11.09"
    data.outline = (
        "Ricky Spanish is on the phone with his friend when his stepmom, Scarlett Mae tells him "
        "it's time to go shopping."
    )

    await core_translate.translate_title_outline(data, cd_part="-CD1", movie_number="Youngermommy.24.11.09")

    assert data.outline.startswith("CN::Ricky Spanish is on the phone")


@pytest.mark.asyncio
async def test_translate_title_outline_skip_does_not_fake_translate_via_zhconv(monkeypatch: pytest.MonkeyPatch):
    from mdcx.core import translate as core_translate

    class _FieldCfg:
        def __init__(self, language: Language, translate: bool):
            self.language = language
            self.translate = translate

    class _TranslateCfg:
        def __init__(self):
            self.translate_by = [Translator.LLM]
            self.llm_model = ""
            self.llm_key = ""

    class _Cfg:
        def __init__(self):
            self.translate_config = _TranslateCfg()

        def get_field_config(self, _field):
            return _FieldCfg(Language.ZH_CN, True)

    class _Manager:
        def __init__(self):
            self.config = _Cfg()

    monkeypatch.setattr(core_translate, "manager", _Manager())
    monkeypatch.setattr(
        core_translate,
        "get_translator_skip_reason",
        lambda translator: "LLM 模型、API Key 未配置" if translator == Translator.LLM else None,
    )

    data = CrawlersResult.empty()
    data.title = "乳首快楽"
    data.outline = "女優の物語"

    await core_translate.translate_title_outline(data, cd_part="", movie_number="ABC-123")

    assert data.title == "乳首快楽"
    assert data.outline == "女優の物語"


def test_cookie_help_path_and_resource_constants():
    from mdcx.config.resources import resources
    from mdcx.consts import GITHUB_RESOURCES_RELEASES_URL, GITHUB_RESOURCES_REPO

    assert GITHUB_RESOURCES_REPO == "Marcus515J/mdcx-resources"
    assert GITHUB_RESOURCES_RELEASES_URL == "https://github.com/Marcus515J/mdcx-resources/releases"
    assert resources.cookie_help_path.is_file()
    assert resources.cookie_help_path.resolve().as_uri().startswith("file:///")
    html_text = resources.cookie_help_path.read_text(encoding="utf-8")
    assert "javdb" in html_text
    assert "javbus" in html_text
    assert "fc2ppvdb" in html_text


def test_r3_legacy_config_only_google_migrates_to_llm(tmp_path, monkeypatch: pytest.MonkeyPatch):
    import json

    from mdcx.config.manager import ConfigManager

    cfg_file = tmp_path / "only_google.json"
    mark_file = tmp_path / "MARK_FILE"
    monkeypatch.setattr("mdcx.config.manager.MARK_FILE", mark_file)

    raw_data = Config().model_dump(mode="json")
    raw_data["translate_config"]["translate_by"] = ["google"]
    cfg_file.write_text(json.dumps(raw_data, ensure_ascii=False, indent=2), encoding="UTF-8")
    mark_file.write_text(str(cfg_file), encoding="UTF-8")

    mgr = ConfigManager()
    errors = mgr.load()
    assert not any("验证失败" in err for err in errors)
    assert mgr.config.translate_config.translate_by == [Translator.LLM]

    mgr.save()
    saved_raw = json.loads(cfg_file.read_text(encoding="UTF-8"))
    assert saved_raw["translate_config"]["translate_by"] == ["llm"]

    reload_errors = mgr.load()
    assert not any("验证失败" in err for err in reload_errors)
    assert mgr.config.translate_config.translate_by == [Translator.LLM]


def test_r3_config_empty_list_becomes_llm(tmp_path, monkeypatch: pytest.MonkeyPatch):
    import json

    from mdcx.config.manager import ConfigManager

    cfg_file = tmp_path / "empty_translate_by.json"
    mark_file = tmp_path / "MARK_FILE"
    monkeypatch.setattr("mdcx.config.manager.MARK_FILE", mark_file)

    raw_data = Config().model_dump(mode="json")
    raw_data["translate_config"]["translate_by"] = []
    cfg_file.write_text(json.dumps(raw_data, ensure_ascii=False, indent=2), encoding="UTF-8")
    mark_file.write_text(str(cfg_file), encoding="UTF-8")

    mgr = ConfigManager()
    errors = mgr.load()
    assert not any("验证失败" in err for err in errors)
    assert mgr.config.translate_config.translate_by == [Translator.LLM]

    mgr.save()
    saved_raw = json.loads(cfg_file.read_text(encoding="UTF-8"))
    assert saved_raw["translate_config"]["translate_by"] == ["llm"]

    reload_errors = mgr.load()
    assert not any("验证失败" in err for err in reload_errors)
    assert mgr.config.translate_config.translate_by == [Translator.LLM]


def test_empty_translate_by_model_and_migration():
    from mdcx.config.migrations import migrate_config_data
    from mdcx.config.models import TranslateConfig

    tc = TranslateConfig.model_validate({"translate_by": []})
    assert tc.translate_by == [Translator.LLM]

    data = {"translate_config": {"translate_by": []}}
    migrate_config_data(data)
    assert data["translate_config"]["translate_by"] == [Translator.LLM.value]


@pytest.mark.asyncio
async def test_translation_log_shows_primary_cloud_model(monkeypatch: pytest.MonkeyPatch):
    from mdcx.core import translate as core_translate
    from mdcx.models.log_buffer import LogBuffer

    class _FieldCfg:
        def __init__(self, language: Language, translate: bool):
            self.language = language
            self.translate = translate

    class _TranslateCfg:
        def __init__(self):
            self.translate_by = [Translator.LLM]
            self.llm_url = "https://api.deepseek.com/v1"
            self.llm_model = "deepseek-flash"
            self.llm_key = "test-key"
            self.llm_prompt_title = "TITLE::{content}"
            self.llm_prompt_outline = "OUTLINE::{content}"

    class _Cfg:
        def __init__(self):
            self.translate_config = _TranslateCfg()

        def get_field_config(self, _field):
            return _FieldCfg(Language.ZH_CN, True)

    class _Manager:
        def __init__(self):
            self.config = _Cfg()

    async def fake_translate_with_engine(*args, **kwargs):
        title = args[1]
        outline = args[2]
        return TranslateResult(
            title=f"CN::{title}",
            outline=f"CN::{outline}",
            error=None,
            engine=Translator.LLM,
            translated_title=True,
            translated_outline=True,
            interface="云端主模型",
            model="deepseek-flash",
        )

    monkeypatch.setattr(core_translate, "manager", _Manager())
    monkeypatch.setattr(core_translate, "translate_with_engine", fake_translate_with_engine)
    monkeypatch.setattr(core_translate, "get_translator_skip_reason", lambda _translator: None)

    LogBuffer.log().clear()
    data = CrawlersResult.empty()
    data.title = "日本語のタイトル"
    data.outline = "日本語のあらすじ"

    await core_translate.translate_title_outline(data, cd_part="", movie_number="TEST-001")

    logs = LogBuffer.log().get()
    assert "📝 翻译成功(LLM·云端主模型 deepseek-flash)" in logs
    assert "Llm" not in logs


@pytest.mark.asyncio
async def test_translation_log_shows_fallback_local_and_remote(monkeypatch: pytest.MonkeyPatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from mdcx.base import translate as base_translate
    from mdcx.models.log_buffer import LogBuffer

    # 1. 测试主模型失败转本机备用
    cfg = base_translate.manager.config
    tc = cfg.translate_config
    monkeypatch.setattr(tc, "llm_url", "https://api.deepseek.com/v1")
    monkeypatch.setattr(tc, "llm_model", "deepseek-flash")
    monkeypatch.setattr(tc, "llm_key", "synthetic-key")
    monkeypatch.setattr(tc, "llm_fallback_url", "http://127.0.0.1:8080/v1")
    monkeypatch.setattr(tc, "llm_fallback_model", "Hy-MT2")
    monkeypatch.setattr(tc, "llm_fallback_key", "")
    monkeypatch.setattr(tc, "llm_refusal_retries", 0)

    signal_logs = []
    monkeypatch.setattr(base_translate.signal, "add_log", signal_logs.append)
    LogBuffer.log().clear()

    class MockPrimary:
        async def ask(self, **kwargs):
            return None

    @asynccontextmanager
    async def fake_acquire():
        yield SimpleNamespace(llm_client=MockPrimary())

    monkeypatch.setattr(base_translate.manager, "acquire_computed", fake_acquire)

    async def fake_fallback_ask(self, **kwargs):
        return "本机备用翻译成功"

    from mdcx.llm import LLMClient

    monkeypatch.setattr(LLMClient, "ask", fake_fallback_ask)

    from mdcx.core import translate as core_translate

    data = CrawlersResult.empty()
    data.title = "日本語タイトル"
    data.outline = "日本語概要"

    await core_translate.translate_title_outline(data, cd_part="", movie_number="TEST-002")

    assert "主模型失败，转本机备用" in signal_logs
    assert "主模型失败，转本机备用" in LogBuffer.log().get()
    assert "📝 翻译成功(LLM·本机备用 Hy-MT2)" in LogBuffer.log().get()

    # 2. 测试主模型失败转备用接口（非本机）
    monkeypatch.setattr(tc, "llm_fallback_url", "https://api.backup.com/v1")
    monkeypatch.setattr(tc, "llm_fallback_model", "backup-chat")
    monkeypatch.setattr(tc, "llm_fallback_key", "backup-key")
    signal_logs.clear()
    LogBuffer.log().clear()

    data2 = CrawlersResult.empty()
    data2.title = "日本語タイトル2"
    data2.outline = "日本語概要2"

    await core_translate.translate_title_outline(data2, cd_part="", movie_number="TEST-003")

    assert "主模型失败，转备用接口" in signal_logs
    assert "主模型失败，转备用接口" in LogBuffer.log().get()
    assert "📝 翻译成功(LLM·备用接口 backup-chat)" in LogBuffer.log().get()
