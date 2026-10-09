from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from pydantic import HttpUrl

from mdcx.base import translate as translation
from mdcx.config.enums import Language, Translator
from mdcx.config.models import Config, TranslateConfig
from mdcx.core import translate as core_translation
from mdcx.gen.field_enums import CrawlerResultFields
from mdcx.models.types import CrawlersResult

REFUSAL = "  「抱歉，我不能协助……」"
SOURCE_TITLE = "日本語の題名"
SOURCE_OUTLINE = "これは日本語の物語です。"


@pytest.fixture
def llm(monkeypatch):
    cfg = Config(translate_config=TranslateConfig(translate_by=[Translator.LLM], llm_refusal_retries=1))
    for field in (CrawlerResultFields.TITLE, CrawlerResultFields.OUTLINE):
        cfg.get_field_config(field).language = Language.ZH_CN
        cfg.get_field_config(field).translate = True
    monkeypatch.setattr(translation.manager, "config", cfg)
    monkeypatch.setattr(core_translation, "get_translator_skip_reason", lambda engine: None)
    logs = []
    calls = []
    answers = {SOURCE_TITLE: ["译后的标题"], SOURCE_OUTLINE: [REFUSAL, REFUSAL]}
    backup = [REFUSAL]
    closed = []

    def record(message):
        logs.append(message)
        print(message)

    monkeypatch.setattr(translation.signal, "add_log", record)

    async def ask(**kwargs):
        calls.append(("primary", kwargs))
        source = SOURCE_TITLE if SOURCE_TITLE in kwargs["user_prompt"] else SOURCE_OUTLINE
        return answers[source].pop(0)

    @asynccontextmanager
    async def lease():
        yield SimpleNamespace(llm_client=SimpleNamespace(ask=ask))

    monkeypatch.setattr(translation.manager, "acquire_computed", lease)

    class Backup:
        def __init__(self, **kwargs):
            calls.append(("construct", kwargs))

        async def ask(self, **kwargs):
            calls.append(("fallback", kwargs))
            return backup.pop(0)

        async def close(self):
            closed.append(True)

    monkeypatch.setattr(translation, "LLMClient", Backup)
    return cfg, answers, backup, calls, logs, closed


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["retry_success", "fallback_success", "all_refused", "normal", "no_fallback"])
async def test_required_paths(llm, path):
    cfg, answers, backup, calls, logs, closed = llm
    if path != "no_fallback":
        tc = cfg.translate_config
        tc.llm_fallback_url = HttpUrl("https://api.deepseek.com")
        cfg.translate_config = TranslateConfig.model_validate(tc.model_dump())
        cfg.translate_config.llm_fallback_key = "mock-key"
        cfg.translate_config.llm_fallback_model = "deepseek-flash"
    expected = SOURCE_OUTLINE
    if path == "retry_success":
        answers[SOURCE_OUTLINE] = [REFUSAL, "重试译文"]
        expected = "重试译文"
    elif path == "fallback_success":
        backup[:] = ["备用译文"]
        expected = "备用译文"
    elif path == "normal":
        answers[SOURCE_OUTLINE] = ["这是一段正常译文，中间含抱歉。"]
        expected = answers[SOURCE_OUTLINE][0]
    data = CrawlersResult.empty()
    data.title, data.outline = SOURCE_TITLE, SOURCE_OUTLINE
    await core_translation.translate_title_outline(data, "", "ABC-123")
    print(f"{path}: title={data.title}; outline={data.outline}")
    assert data.title == "译后的标题"
    assert data.outline == expected
    assert not translation._is_llm_refusal(data.outline, cfg.translate_config.llm_refusal_prefixes)
    primary = [kwargs for kind, kwargs in calls if kind == "primary" and SOURCE_OUTLINE in kwargs["user_prompt"]]
    fallback = [kwargs for kind, kwargs in calls if kind == "fallback"]
    assert len(primary) == (1 if path == "normal" else 2)
    assert len(fallback) == (1 if path in ["fallback_success", "all_refused"] else 0)
    assert len(closed) == len(fallback)
    # Same prompt and settings: detection and fallback only.
    assert all(item["user_prompt"] == primary[0]["user_prompt"] for item in primary + fallback)
    assert all(item["system_prompt"] == primary[0]["system_prompt"] for item in primary + fallback)
    assert ("📝 保留原文" in logs) == (path in ["all_refused", "no_fallback"])
    if path == "all_refused":
        assert (
            logs.index("⚠️ 翻译被拒")
            < logs.index("🔁 翻译被拒：重试第 1 次")
            < logs.index("🔄 换备用模型")
            < logs.index("📝 保留原文")
        )


@pytest.mark.parametrize("prefix", TranslateConfig().llm_refusal_prefixes)
def test_all_prefixes(prefix):
    assert translation._is_llm_refusal(" \n “' " + prefix.swapcase() + "……", TranslateConfig().llm_refusal_prefixes)
    assert not translation._is_llm_refusal("这段译文中间出现" + prefix, TranslateConfig().llm_refusal_prefixes)


@pytest.mark.asyncio
async def test_title_refusal_and_empty_source(llm):
    _, answers, _, calls, logs, _ = llm
    answers[SOURCE_TITLE] = [REFUSAL, REFUSAL]
    assert await translation._llm_translate(SOURCE_TITLE, "{content}") == SOURCE_TITLE
    before = len(calls)
    assert await translation._llm_translate("", "{content}") == ""
    assert len(calls) == before
    assert "📝 保留原文" in logs


@pytest.mark.asyncio
async def test_both_fields_preserved_without_error(llm):
    _, answers, _, _, _, _ = llm
    answers[SOURCE_TITLE] = [REFUSAL, REFUSAL]
    result = await translation.translate_with_engine(
        Translator.LLM,
        SOURCE_TITLE,
        SOURCE_OUTLINE,
        title_language=Language.ZH_CN,
        outline_language=Language.ZH_CN,
    )
    assert result.error is None
    assert result.title == SOURCE_TITLE and result.outline == SOURCE_OUTLINE
    assert not result.translated_title and not result.translated_outline


@pytest.mark.asyncio
async def test_retry_count_and_custom_prefix(llm):
    cfg, answers, _, calls, _, _ = llm
    cfg.translate_config.llm_refusal_retries = 2
    cfg.translate_config.llm_refusal_prefixes = ["拒绝翻译"]
    answers[SOURCE_OUTLINE] = ["拒绝翻译", "拒绝翻译", "成功译文"]
    assert await translation._llm_translate(SOURCE_OUTLINE, "{content}") == "成功译文"
    assert len(calls) == 3


def test_empty_backup_address():
    assert TranslateConfig(llm_fallback_url="").llm_fallback_url is None
    assert str(TranslateConfig(llm_url="https://api.deepseek.com").llm_url) == "https://api.deepseek.com/"


@pytest.mark.asyncio
async def test_backup_api_failure_keeps_source_and_closes(llm):
    cfg, _, backup, _, _, closed = llm
    cfg.translate_config = TranslateConfig(
        llm_fallback_url="https://api.deepseek.com", llm_fallback_key="mock", llm_fallback_model="deepseek-flash"
    )
    backup[:] = [None]
    assert await translation._llm_translate(SOURCE_OUTLINE, "{content}") == SOURCE_OUTLINE
    assert closed == [True]


@pytest.mark.asyncio
async def test_local_model_precedes_other_enabled_engines_and_preserves_failed_field(llm, monkeypatch):
    cfg, answers, _, calls, _, _ = llm
    cfg.translate_config.llm_url = HttpUrl("http://127.0.0.1:8080/v1")
    cfg.translate_config.translate_by = [Translator.GOOGLE, Translator.LLM, Translator.BAIDU]
    answers[SOURCE_OUTLINE] = [None, None]
    monkeypatch.setattr(core_translation.random, "shuffle", lambda engines: None)
    data = CrawlersResult.empty()
    data.title, data.outline = SOURCE_TITLE, SOURCE_OUTLINE
    await core_translation.translate_title_outline(data, "", "ABC-123")
    assert data.title == "译后的标题"
    assert data.outline == SOURCE_OUTLINE
    assert len(calls) == 3
    assert all(kwargs["max_try"] == 1 for kind, kwargs in calls if kind == "primary")
