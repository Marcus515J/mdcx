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

    from pydantic import HttpUrl

    from mdcx.base import translate as base_translate
    from mdcx.models.log_buffer import LogBuffer

    # 1. 测试主模型失败转本机备用
    cfg = base_translate.manager.config
    tc = cfg.translate_config
    monkeypatch.setattr(tc, "llm_url", "https://api.deepseek.com/v1")
    monkeypatch.setattr(tc, "llm_model", "deepseek-flash")
    monkeypatch.setattr(tc, "llm_key", "synthetic-key")
    monkeypatch.setattr(tc, "llm_fallback_url", HttpUrl("http://127.0.0.1:8080/v1"))
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
    data.outline = "日本語の概要"

    await core_translate.translate_title_outline(data, cd_part="", movie_number="TEST-002")

    assert "标题：主模型失败，转本机备用" in signal_logs
    assert "简介：主模型失败，转本机备用" in signal_logs
    logs = LogBuffer.log().get()
    assert "标题：主模型失败，转本机备用" in logs
    assert "简介：主模型失败，转本机备用" in logs
    assert "📝 翻译成功(LLM·本机备用 Hy-MT2)" in logs

    # 2. 测试主模型失败转备用接口（非本机）
    monkeypatch.setattr(tc, "llm_fallback_url", HttpUrl("https://api.backup.com/v1"))
    monkeypatch.setattr(tc, "llm_fallback_model", "backup-chat")
    monkeypatch.setattr(tc, "llm_fallback_key", "backup-key")
    signal_logs.clear()
    LogBuffer.log().clear()

    data2 = CrawlersResult.empty()
    data2.title = "日本語タイトル2"
    data2.outline = "日本語の概要2"

    await core_translate.translate_title_outline(data2, cd_part="", movie_number="TEST-003")

    assert "标题：主模型失败，转备用接口" in signal_logs
    assert "简介：主模型失败，转备用接口" in signal_logs
    logs2 = LogBuffer.log().get()
    assert "标题：主模型失败，转备用接口" in logs2
    assert "简介：主模型失败，转备用接口" in logs2
    assert "📝 翻译成功(LLM·备用接口 backup-chat)" in logs2


@pytest.mark.asyncio
async def test_translate_llm_field_independence_case_a_title_refused(monkeypatch: pytest.MonkeyPatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from pydantic import HttpUrl

    from mdcx.base import translate as base_translate
    from mdcx.llm import LLMClient

    tc = base_translate.manager.config.translate_config
    monkeypatch.setattr(tc, "llm_url", "https://api.deepseek.com/v1")
    monkeypatch.setattr(tc, "llm_model", "deepseek-flash")
    monkeypatch.setattr(tc, "llm_key", "primary-key")
    monkeypatch.setattr(tc, "llm_fallback_url", HttpUrl("http://127.0.0.1:8080/v1"))
    monkeypatch.setattr(tc, "llm_fallback_model", "Hy-MT2")
    monkeypatch.setattr(tc, "llm_fallback_key", "")
    monkeypatch.setattr(tc, "llm_refusal_retries", 0)
    monkeypatch.setattr(tc, "llm_refusal_prefixes", ["我无法", "抱歉", "I cannot"])
    monkeypatch.setattr(tc, "llm_prompt_title", "TITLE::{content}")
    monkeypatch.setattr(tc, "llm_prompt_outline", "OUTLINE::{content}")

    class MockPrimary:
        async def ask(self, **kwargs):
            prompt = kwargs.get("user_prompt", "")
            if "TITLE" in prompt:
                return "抱歉，我无法翻译该标题"
            return "主模型翻译简介"

    @asynccontextmanager
    async def fake_acquire():
        yield SimpleNamespace(llm_client=MockPrimary())

    monkeypatch.setattr(base_translate.manager, "acquire_computed", fake_acquire)

    fallback_calls = []

    async def fake_fallback_ask(self, **kwargs):
        prompt = kwargs.get("user_prompt", "")
        fallback_calls.append(prompt)
        return "备用模型翻译标题"

    monkeypatch.setattr(LLMClient, "ask", fake_fallback_ask)

    result = await base_translate.translate_with_engine(
        Translator.LLM,
        "日本語タイトル",
        "日本語概要",
        title_language=Language.ZH_CN,
        outline_language=Language.ZH_CN,
    )

    # 情况 A：主接口对标题返回拒绝，对简介正常返回译文。
    # 断言：备用接口正好被调用 1 次，调用的 prompt 是标题的 prompt；最终简介的结果来自主接口，标题的结果来自备用接口。
    assert len(fallback_calls) == 1
    assert fallback_calls[0] == "TITLE::日本語タイトル"
    assert result.title == "备用模型翻译标题"
    assert result.outline == "主模型翻译简介"


@pytest.mark.asyncio
async def test_translate_llm_field_independence_case_b_outline_refused(monkeypatch: pytest.MonkeyPatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from pydantic import HttpUrl

    from mdcx.base import translate as base_translate
    from mdcx.llm import LLMClient

    tc = base_translate.manager.config.translate_config
    monkeypatch.setattr(tc, "llm_url", "https://api.deepseek.com/v1")
    monkeypatch.setattr(tc, "llm_model", "deepseek-flash")
    monkeypatch.setattr(tc, "llm_key", "primary-key")
    monkeypatch.setattr(tc, "llm_fallback_url", HttpUrl("http://127.0.0.1:8080/v1"))
    monkeypatch.setattr(tc, "llm_fallback_model", "Hy-MT2")
    monkeypatch.setattr(tc, "llm_fallback_key", "")
    monkeypatch.setattr(tc, "llm_refusal_retries", 0)
    monkeypatch.setattr(tc, "llm_refusal_prefixes", ["我无法", "抱歉", "I cannot"])
    monkeypatch.setattr(tc, "llm_prompt_title", "TITLE::{content}")
    monkeypatch.setattr(tc, "llm_prompt_outline", "OUTLINE::{content}")

    class MockPrimary:
        async def ask(self, **kwargs):
            prompt = kwargs.get("user_prompt", "")
            if "OUTLINE" in prompt:
                return "抱歉，我无法翻译该简介"
            return "主模型翻译标题"

    @asynccontextmanager
    async def fake_acquire():
        yield SimpleNamespace(llm_client=MockPrimary())

    monkeypatch.setattr(base_translate.manager, "acquire_computed", fake_acquire)

    fallback_calls = []

    async def fake_fallback_ask(self, **kwargs):
        prompt = kwargs.get("user_prompt", "")
        fallback_calls.append(prompt)
        return "备用模型翻译简介"

    monkeypatch.setattr(LLMClient, "ask", fake_fallback_ask)

    result = await base_translate.translate_with_engine(
        Translator.LLM,
        "日本語タイトル",
        "日本語概要",
        title_language=Language.ZH_CN,
        outline_language=Language.ZH_CN,
    )

    # 情况 B：标题正常，简介被拒。断言方式和情况 A 对称。
    assert len(fallback_calls) == 1
    assert fallback_calls[0] == "OUTLINE::日本語概要"
    assert result.title == "主模型翻译标题"
    assert result.outline == "备用模型翻译简介"


@pytest.mark.asyncio
async def test_translate_llm_field_independence_case_c_both_refused(monkeypatch: pytest.MonkeyPatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from pydantic import HttpUrl

    from mdcx.base import translate as base_translate
    from mdcx.llm import LLMClient

    tc = base_translate.manager.config.translate_config
    monkeypatch.setattr(tc, "llm_url", "https://api.deepseek.com/v1")
    monkeypatch.setattr(tc, "llm_model", "deepseek-flash")
    monkeypatch.setattr(tc, "llm_key", "primary-key")
    monkeypatch.setattr(tc, "llm_fallback_url", HttpUrl("http://127.0.0.1:8080/v1"))
    monkeypatch.setattr(tc, "llm_fallback_model", "Hy-MT2")
    monkeypatch.setattr(tc, "llm_fallback_key", "")
    monkeypatch.setattr(tc, "llm_refusal_retries", 0)
    monkeypatch.setattr(tc, "llm_refusal_prefixes", ["我无法", "抱歉", "I cannot"])
    monkeypatch.setattr(tc, "llm_prompt_title", "TITLE::{content}")
    monkeypatch.setattr(tc, "llm_prompt_outline", "OUTLINE::{content}")

    class MockPrimary:
        async def ask(self, **kwargs):
            return "抱歉，我无法翻译该内容"

    @asynccontextmanager
    async def fake_acquire():
        yield SimpleNamespace(llm_client=MockPrimary())

    monkeypatch.setattr(base_translate.manager, "acquire_computed", fake_acquire)

    fallback_calls = []

    async def fake_fallback_ask(self, **kwargs):
        prompt = kwargs.get("user_prompt", "")
        fallback_calls.append(prompt)
        if "TITLE" in prompt:
            return "备用模型翻译标题"
        return "备用模型翻译简介"

    monkeypatch.setattr(LLMClient, "ask", fake_fallback_ask)

    result = await base_translate.translate_with_engine(
        Translator.LLM,
        "日本語タイトル",
        "日本語概要",
        title_language=Language.ZH_CN,
        outline_language=Language.ZH_CN,
    )

    # 情况 C：两个字段都被拒。断言：备用接口被调用 2 次。
    assert len(fallback_calls) == 2
    assert "TITLE::日本語タイトル" in fallback_calls
    assert "OUTLINE::日本語概要" in fallback_calls
    assert result.title == "备用模型翻译标题"
    assert result.outline == "备用模型翻译简介"


@pytest.mark.asyncio
async def test_translate_llm_field_independence_case_d_neither_refused(monkeypatch: pytest.MonkeyPatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from pydantic import HttpUrl

    from mdcx.base import translate as base_translate
    from mdcx.llm import LLMClient

    tc = base_translate.manager.config.translate_config
    monkeypatch.setattr(tc, "llm_url", "https://api.deepseek.com/v1")
    monkeypatch.setattr(tc, "llm_model", "deepseek-flash")
    monkeypatch.setattr(tc, "llm_key", "primary-key")
    monkeypatch.setattr(tc, "llm_fallback_url", HttpUrl("http://127.0.0.1:8080/v1"))
    monkeypatch.setattr(tc, "llm_fallback_model", "Hy-MT2")
    monkeypatch.setattr(tc, "llm_fallback_key", "")
    monkeypatch.setattr(tc, "llm_refusal_retries", 0)
    monkeypatch.setattr(tc, "llm_refusal_prefixes", ["我无法", "抱歉", "I cannot"])
    monkeypatch.setattr(tc, "llm_prompt_title", "TITLE::{content}")
    monkeypatch.setattr(tc, "llm_prompt_outline", "OUTLINE::{content}")

    class MockPrimary:
        async def ask(self, **kwargs):
            prompt = kwargs.get("user_prompt", "")
            if "TITLE" in prompt:
                return "主模型翻译标题"
            return "主模型翻译简介"

    @asynccontextmanager
    async def fake_acquire():
        yield SimpleNamespace(llm_client=MockPrimary())

    monkeypatch.setattr(base_translate.manager, "acquire_computed", fake_acquire)

    fallback_calls = []

    async def fake_fallback_ask(self, **kwargs):
        prompt = kwargs.get("user_prompt", "")
        fallback_calls.append(prompt)
        return "备用模型翻译"

    monkeypatch.setattr(LLMClient, "ask", fake_fallback_ask)

    result = await base_translate.translate_with_engine(
        Translator.LLM,
        "日本語タイトル",
        "日本語概要",
        title_language=Language.ZH_CN,
        outline_language=Language.ZH_CN,
    )

    # 情况 D：两个字段都正常。断言：备用接口被调用 0 次。
    assert len(fallback_calls) == 0
    assert result.title == "主模型翻译标题"
    assert result.outline == "主模型翻译简介"


@pytest.mark.asyncio
async def test_translate_llm_situation_a_logs_and_summary_with_different_sources(monkeypatch: pytest.MonkeyPatch):
    """
    G3.5: 给第 2、3 条补测试：情况 A 的日志里出现 标题：主模型失败，转本机备用，不出现 简介：主模型失败；汇总行包含两个不同的来源。
    """
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from pydantic import HttpUrl

    from mdcx.base import translate as base_translate
    from mdcx.core import translate as core_translate
    from mdcx.llm import LLMClient
    from mdcx.models.log_buffer import LogBuffer

    cfg = base_translate.manager.config
    tc = cfg.translate_config
    monkeypatch.setattr(tc, "llm_url", "https://api.deepseek.com/v1")
    monkeypatch.setattr(tc, "llm_model", "deepseek-flash")
    monkeypatch.setattr(tc, "llm_key", "primary-key")
    monkeypatch.setattr(tc, "llm_fallback_url", HttpUrl("http://127.0.0.1:8080/v1"))
    monkeypatch.setattr(tc, "llm_fallback_model", "Hy-MT2")
    monkeypatch.setattr(tc, "llm_fallback_key", "")
    monkeypatch.setattr(tc, "llm_refusal_retries", 0)
    monkeypatch.setattr(tc, "llm_refusal_prefixes", ["我无法", "抱歉", "I cannot"])
    monkeypatch.setattr(tc, "llm_prompt_title", "TITLE::{content}")
    monkeypatch.setattr(tc, "llm_prompt_outline", "OUTLINE::{content}")

    signal_logs = []
    monkeypatch.setattr(base_translate.signal, "add_log", signal_logs.append)
    LogBuffer.log().clear()

    class MockPrimary:
        async def ask(self, **kwargs):
            prompt = kwargs.get("user_prompt", "")
            if "TITLE" in prompt:
                return "抱歉，我无法翻译该标题"
            return "主模型翻译简介成功"

    @asynccontextmanager
    async def fake_acquire():
        yield SimpleNamespace(llm_client=MockPrimary())

    monkeypatch.setattr(base_translate.manager, "acquire_computed", fake_acquire)

    async def fake_fallback_ask(self, **kwargs):
        return "备用模型翻译标题成功"

    monkeypatch.setattr(LLMClient, "ask", fake_fallback_ask)

    data = CrawlersResult.empty()
    data.title = "日本語タイトル"
    data.outline = "日本語の概要"

    await core_translate.translate_title_outline(data, cd_part="", movie_number="TEST-SIT-A")

    # 1. signal_logs (detail log stream)
    assert "标题：主模型失败，转本机备用" in signal_logs
    assert not any("简介：主模型失败" in item for item in signal_logs)
    assert signal_logs.count("标题：主模型失败，转本机备用") == 1

    # 2. LogBuffer logs (main scraping log stream)
    main_logs = LogBuffer.log().get()
    assert "标题：主模型失败，转本机备用" in main_logs
    assert "简介：主模型失败" not in main_logs

    # 3. 汇总行包含两个不同的来源
    assert "📝 翻译成功(标题 LLM·本机备用 Hy-MT2；简介 LLM·云端主模型 deepseek-flash)" in main_logs

    # 4. 译文正确更新
    assert data.title == "备用模型翻译标题成功"
    assert data.outline == "主模型翻译简介成功"


@pytest.mark.asyncio
async def test_translate_llm_single_field_summary_does_not_show_empty_field(monkeypatch: pytest.MonkeyPatch):
    """
    G3.3: 某个字段为空、没有发请求时，不显示这个字段。
    """
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from mdcx.base import translate as base_translate
    from mdcx.core import translate as core_translate
    from mdcx.models.log_buffer import LogBuffer

    cfg = base_translate.manager.config
    tc = cfg.translate_config
    monkeypatch.setattr(tc, "llm_url", "https://api.deepseek.com/v1")
    monkeypatch.setattr(tc, "llm_model", "deepseek-flash")
    monkeypatch.setattr(tc, "llm_key", "primary-key")
    monkeypatch.setattr(tc, "llm_prompt_title", "TITLE::{content}")
    monkeypatch.setattr(tc, "llm_prompt_outline", "OUTLINE::{content}")

    LogBuffer.log().clear()

    class MockPrimary:
        async def ask(self, **kwargs):
            return "标题翻译成功"

    @asynccontextmanager
    async def fake_acquire():
        yield SimpleNamespace(llm_client=MockPrimary())

    monkeypatch.setattr(base_translate.manager, "acquire_computed", fake_acquire)
    tc = base_translate.manager.config.translate_config
    monkeypatch.setattr(tc, "llm_key", "test-key")

    data = CrawlersResult.empty()
    data.title = "日本語タイトル"
    data.outline = ""  # 简介为空，不发请求

    await core_translate.translate_title_outline(data, cd_part="", movie_number="TEST-SINGLE")

    main_logs = LogBuffer.log().get()
    assert "📝 翻译成功(LLM·云端主模型 deepseek-flash)" in main_logs
    assert "简介" not in main_logs


# ==============================================================================
# Issue #35 / 第六步测试套件
# ==============================================================================


@pytest.mark.asyncio
async def test_chinese_source_title_enters_llm_queue_and_respects_switch(monkeypatch: pytest.MonkeyPatch):
    """
    1. 中文源标题会进入大模型调用（中文标题入队、翻译开关关闭时不入队）。
    """
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from mdcx.base import translate as base_translate
    from mdcx.core import translate as core_translate
    from mdcx.gen.field_enums import CrawlerResultFields

    captured_requests = []

    class MockPrimary:
        async def ask(self, **kwargs):
            captured_requests.append(kwargs)
            return "精简后的最终中文标题"

    @asynccontextmanager
    async def fake_acquire():
        yield SimpleNamespace(llm_client=MockPrimary())

    monkeypatch.setattr(base_translate.manager, "acquire_computed", fake_acquire)

    tc = base_translate.manager.config.translate_config
    monkeypatch.setattr(tc, "llm_url", "https://api.deepseek.com/v1")
    monkeypatch.setattr(tc, "llm_model", "deepseek-flash")
    monkeypatch.setattr(tc, "llm_key", "key")

    # 1. 翻译开启：中文标题入队
    data = CrawlersResult.empty()
    data.title = "这是一个超过三十五个汉字而且本来就是中文的源标题内容用来测试大模型精简调用"
    data.outline = ""
    captured_requests.clear()

    await core_translate.translate_title_outline(data, cd_part="", movie_number="ZH-TEST-01")
    assert len(captured_requests) == 1
    assert "这是一个超过三十五个汉字" in captured_requests[0]["user_prompt"]
    assert data.title == "精简后的最终中文标题"

    # 2. 翻译开关关闭：不入队
    captured_requests.clear()
    monkeypatch.setattr(base_translate.manager.config.get_field_config(CrawlerResultFields.TITLE), "translate", False)
    data_off = CrawlersResult.empty()
    data_off.title = "原本的中文标题保持不变"
    data_off.outline = ""

    await core_translate.translate_title_outline(data_off, cd_part="", movie_number="ZH-TEST-02")
    assert len(captured_requests) == 0
    assert data_off.title == "原本的中文标题保持不变"


@pytest.mark.asyncio
async def test_title_length_exceed_35_han_characters_logs_warning(monkeypatch: pytest.MonkeyPatch):
    """
    标题汉字数超过 35 时写一条日志（番号、汉字数），代码不硬截断。
    """
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from mdcx.base import translate as base_translate
    from mdcx.core import translate as core_translate
    from mdcx.models.log_buffer import LogBuffer
    from mdcx.signals import signal

    signal_logs = []
    monkeypatch.setattr(signal, "add_log", lambda text: signal_logs.append(text))
    LogBuffer.log().clear()

    # 36 个汉字
    long_title = "一二三四五六七八九十一二三四五六七八九十一二三四五六七八九十一二三四五六"

    class MockPrimary:
        async def ask(self, **kwargs):
            return long_title

    @asynccontextmanager
    async def fake_acquire():
        yield SimpleNamespace(llm_client=MockPrimary())

    monkeypatch.setattr(base_translate.manager, "acquire_computed", fake_acquire)
    tc = base_translate.manager.config.translate_config
    monkeypatch.setattr(tc, "llm_key", "test-key")

    data = CrawlersResult.empty()
    data.title = "短标题"
    data.outline = ""

    await core_translate.translate_title_outline(data, cd_part="", movie_number="TEST-LEN-35")

    # 代码不硬截断
    assert data.title == long_title
    # 写日志包含番号和汉字数
    main_logs = LogBuffer.log().get()
    assert "⚠️ 标题超过 35 个汉字（番号：TEST-LEN-35，汉字数：36）" in main_logs
    assert any("⚠️ 标题超过 35 个汉字（番号：TEST-LEN-35，汉字数：36）" in log for log in signal_logs)


@pytest.mark.asyncio
async def test_actor_mapping_constraints_and_unification(monkeypatch: pytest.MonkeyPatch):
    """
    2. 人名约束：查表命中的译名同时传给标题、简介，主、备两条请求都带；zh_cn 含假名的条目不当作约束用。
    3. 片内统一：未命中或含假名的保证单片内标题与简介使用同一个中文译名。
    """
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from mdcx.base import translate as base_translate
    from mdcx.core import translate as core_translate
    from mdcx.llm import LLMClient

    prompts_captured = []

    class MockPrimary:
        async def ask(self, **kwargs):
            prompts_captured.append(("primary", kwargs["user_prompt"]))
            return None  # 模拟主模型失败以触发备用模型

    @asynccontextmanager
    async def fake_acquire():
        yield SimpleNamespace(llm_client=MockPrimary())

    monkeypatch.setattr(base_translate.manager, "acquire_computed", fake_acquire)

    fallback_prompts = []

    async def fake_fallback_ask(self, **kwargs):
        fallback_prompts.append(("fallback", kwargs["user_prompt"]))
        return "备用译文"

    monkeypatch.setattr(LLMClient, "ask", fake_fallback_ask)

    # 模拟演员映射资源
    mock_actor_table = {
        "三上悠亜": {"zh_cn": "三上悠亚", "has_name": True},
        "宮西ひかる": {"zh_cn": "宫西ひかる", "has_name": True},  # zh_cn 含假名，不能直接当作约束
    }
    monkeypatch.setattr(
        core_translate.resources,
        "get_actor_data",
        lambda name: mock_actor_table.get(name, {"zh_cn": name, "has_name": False}),
    )

    tc = base_translate.manager.config.translate_config
    monkeypatch.setattr(tc, "llm_key", "synthetic-key")
    monkeypatch.setattr(tc, "llm_fallback_url", "http://127.0.0.1:8080/v1")
    monkeypatch.setattr(tc, "llm_fallback_model", "HY-MT2")
    monkeypatch.setattr(tc, "llm_fallback_key", "local")

    data = CrawlersResult.empty()
    data.title = "タイトル"
    data.outline = "アウトライン"
    data.actors = ["三上悠亜", "宮西ひかる", "Q太郎"]

    await core_translate.translate_title_outline(data, cd_part="", movie_number="TEST-ACTOR-01")

    # 查表命中且不含假名的三上悠亜：同时传给标题、简介，主备都带
    for source, prompt in prompts_captured + fallback_prompts:
        assert "三上悠亜 -> 三上悠亚" in prompt
        # 带拉丁字母的网名 Q太郎 原样保留
        assert "Q太郎 -> Q太郎" in prompt
        # zh_cn 含假名的宫西ひかる不直接作为查表结果约束，而统一转换为了无假名的约束（希卡露）
        assert "宫西ひかる" not in prompt
        assert "ひかる -> 希卡露" in prompt


@pytest.mark.asyncio
async def test_fallback_retry_diagnosis_and_batch_failure_summary(monkeypatch: pytest.MonkeyPatch):
    """
    4. 兜底：备用遇到异常或空返回重试 1 次，被拒不重试；仍失败保留原文，并写出 c 项日志与批次清单。
    5. 诊断日志字段齐全（番号、字段、主/备、尝试次数；被拒附回复前 30 字）。
    """
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    from mdcx.base import translate as base_translate
    from mdcx.base.translate import TranslationBatchTracker
    from mdcx.core import translate as core_translate
    from mdcx.llm import LLMClient
    from mdcx.signals import signal

    signal_logs = []
    monkeypatch.setattr(signal, "add_log", lambda text: signal_logs.append(text))
    TranslationBatchTracker.clear()

    # Case A: 备用模型遇到空返回/异常，重试 1 次（共 2 次），仍失败保留原文
    class MockPrimaryFail:
        def __init__(self):
            self.last_error_type = "APIConnectionError"

        async def ask(self, **kwargs):
            return None

    @asynccontextmanager
    async def fake_acquire():
        yield SimpleNamespace(llm_client=MockPrimaryFail())

    monkeypatch.setattr(base_translate.manager, "acquire_computed", fake_acquire)

    fallback_attempts = []

    async def fake_fallback_ask_fail(self, **kwargs):
        fallback_attempts.append(1)
        self.last_error_type = "InternalServerError"
        return ""

    monkeypatch.setattr(LLMClient, "ask", fake_fallback_ask_fail)

    tc = base_translate.manager.config.translate_config
    monkeypatch.setattr(tc, "llm_key", "synthetic-key")
    monkeypatch.setattr(tc, "llm_fallback_url", "http://127.0.0.1:8080/v1")
    monkeypatch.setattr(tc, "llm_fallback_model", "HY-MT2")
    monkeypatch.setattr(tc, "llm_fallback_key", "local")

    data = CrawlersResult.empty()
    data.title = "原文标题A"
    data.outline = ""

    await core_translate.translate_title_outline(data, cd_part="", movie_number="FAIL-NUM-A")

    # 备用模型重试了 1 次（总共 2 次调用）
    assert len(fallback_attempts) == 2
    # 原文保留
    assert data.title == "原文标题A"

    # 诊断日志：番号、字段、主/备、尝试次数、失败类型
    assert any("⚠️ [FAIL-NUM-A] 标题 主模型 第 1 次尝试失败（APIConnectionError）" in log for log in signal_logs)
    assert any("⚠️ [FAIL-NUM-A] 标题 备用模型 第 1 次尝试失败（InternalServerError）" in log for log in signal_logs)
    assert any("🔁 [FAIL-NUM-A] 标题 备用模型 重试第 2 次" in log for log in signal_logs)
    assert any("⚠️ [FAIL-NUM-A] 标题 备用模型 第 2 次尝试失败（InternalServerError）" in log for log in signal_logs)
    assert any("📝 [FAIL-NUM-A] 标题 保留原文（失败类型：InternalServerError）" in log for log in signal_logs)

    # Case B: 备用模型被拒不重试，且记录前 30 字
    fallback_refusal_attempts = []

    async def fake_fallback_ask_refusal(self, **kwargs):
        fallback_refusal_attempts.append(1)
        return "抱歉，由于模型安全策略限制，我无法为您提供该内容的翻译服务。"

    monkeypatch.setattr(LLMClient, "ask", fake_fallback_ask_refusal)

    data_b = CrawlersResult.empty()
    data_b.title = ""
    data_b.outline = "あらすじB 日本語の概要"

    await core_translate.translate_title_outline(data_b, cd_part="", movie_number="FAIL-NUM-B")

    # 被判「拒绝」的不重试：只有 1 次
    assert len(fallback_refusal_attempts) == 1
    assert data_b.outline == "あらすじB 日本語の概要"
    assert any(
        "⚠️ [FAIL-NUM-B] 简介 备用模型 第 1 次尝试被拒（回复前30字：抱歉，由于模型安全策略限制，我无法为您提供该内容的翻译服务。）"
        in log
        for log in signal_logs
    )

    # 批次清单验证
    summary = TranslationBatchTracker.format_summary()
    assert "FAIL-NUM-A（标题）" in summary
    assert "FAIL-NUM-B（简介）" in summary
    assert summary.startswith("翻译失败、保留原文清单：")


def test_thinking_mode_config_and_payload():
    """
    6. 思考开关：单元测试证明三个取值分别对应「不发送 / thinking.type=enabled / thinking.type=disabled」；默认值为 default。
    """
    from mdcx.config.models import TranslateConfig

    # 默认值
    tc_default = TranslateConfig()
    assert tc_default.llm_thinking == "default"
    assert tc_default.llm_fallback_thinking == "default"

    # 开
    tc_enabled = TranslateConfig(llm_thinking="enabled", llm_fallback_thinking="开")
    assert tc_enabled.llm_thinking == "enabled"
    assert tc_enabled.llm_fallback_thinking == "enabled"

    # 关
    tc_disabled = TranslateConfig(llm_thinking="disabled", llm_fallback_thinking="关")
    assert tc_disabled.llm_thinking == "disabled"
    assert tc_disabled.llm_fallback_thinking == "disabled"


@pytest.mark.asyncio
async def test_thinking_mode_client_payload_and_reasoning_logging(monkeypatch: pytest.MonkeyPatch):
    """
    测试 LLMClient 发送 thinking 载荷及思考日志记录。
    """
    from types import SimpleNamespace

    from mdcx.llm import LLMClient

    captured_extra_body = []
    logs = []

    client = LLMClient(
        api_key="mock",
        base_url="http://127.0.0.1:8080/v1",
        timeout=None,
        rate=(1, 1),
    )

    async def fake_create(**kwargs):
        captured_extra_body.append(kwargs.get("extra_body"))
        choice = SimpleNamespace(
            message=SimpleNamespace(
                content="<think>这里是思考过程内容</think>译文结果",
                reasoning_content=None,
            )
        )
        return SimpleNamespace(choices=[choice])

    monkeypatch.setattr(client.client.chat.completions, "create", fake_create)

    # 1. enabled
    text = await client.ask(
        model="deepseek-reasoner",
        system_prompt="sys",
        user_prompt="usr",
        max_try=1,
        log_fn=lambda msg: logs.append(msg),
        extra_body={"thinking": {"type": "enabled"}},
    )
    assert text == "译文结果"
    assert captured_extra_body[-1] == {"thinking": {"type": "enabled"}}
    assert any("🧠 思考内容：有（9 字符）" in log for log in logs)

    # 2. disabled
    logs.clear()
    await client.ask(
        model="deepseek-chat",
        system_prompt="sys",
        user_prompt="usr",
        max_try=1,
        log_fn=lambda msg: logs.append(msg),
        extra_body={"thinking": {"type": "disabled"}},
    )
    assert captured_extra_body[-1] == {"thinking": {"type": "disabled"}}

    # 3. default (不发送)
    logs.clear()

    async def fake_create_no_think(**kwargs):
        captured_extra_body.append(kwargs.get("extra_body"))
        choice = SimpleNamespace(
            message=SimpleNamespace(
                content="普通译文",
                reasoning_content=None,
            )
        )
        return SimpleNamespace(choices=[choice])

    monkeypatch.setattr(client.client.chat.completions, "create", fake_create_no_think)
    await client.ask(
        model="deepseek-chat",
        system_prompt="sys",
        user_prompt="usr",
        max_try=1,
        log_fn=lambda msg: logs.append(msg),
        extra_body=None,
    )
    assert captured_extra_body[-1] is None
    assert any("🧠 思考内容：无" in log for log in logs)
    await client.close()
