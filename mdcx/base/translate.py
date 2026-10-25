import asyncio
import re
import threading
from dataclasses import dataclass

from httpx import Timeout

from ..config.enums import Language
from ..config.manager import manager
from ..config.models import Translator
from ..llm import LLMClient, is_loopback_url
from ..signals import signal


def format_translator_label(
    translator: Translator | str = Translator.LLM,
    interface: str = "",
    model: str = "",
) -> str:
    if not interface:
        tc = manager.config.translate_config
        interface = "本机主模型" if is_loopback_url(str(tc.llm_url)) else "云端主模型"
        model = model or tc.llm_model
    model_str = model.strip() if model else ""
    return f"LLM·{interface} {model_str}".rstrip()


@dataclass(slots=True)
class TranslateResult:
    title: str
    outline: str
    error: str | None
    engine: Translator
    translated_title: bool = False
    translated_outline: bool = False
    interface: str = ""
    model: str = ""
    fallback_used: bool = False
    title_interface: str = ""
    title_model: str = ""
    title_fallback: bool = False
    outline_interface: str = ""
    outline_model: str = ""
    outline_fallback: bool = False
    requested_title: bool = False
    requested_outline: bool = False
    title_field_name: str = "标题"
    outline_field_name: str = "简介"

    @property
    def label(self) -> str:
        t_label = (
            format_translator_label(self.engine, self.title_interface, self.title_model)
            if self.requested_title and self.title_interface
            else ""
        )
        o_label = (
            format_translator_label(self.engine, self.outline_interface, self.outline_model)
            if self.requested_outline and self.outline_interface
            else ""
        )

        if self.requested_title and self.requested_outline:
            if t_label == o_label:
                return t_label
            t_name = self.title_field_name or "标题"
            o_name = self.outline_field_name or "简介"
            return f"{t_name} {t_label}；{o_name} {o_label}"
        if self.requested_title and not self.requested_outline:
            return t_label
        if self.requested_outline and not self.requested_title:
            return o_label
        return format_translator_label(self.engine, self.interface, self.model)

    @property
    def success(self) -> bool:
        return self.error is None and (self.translated_title or self.translated_outline)


def _has_effective_translation(source: str, translated: str) -> bool:
    return bool(source and translated and translated.strip() != source.strip())


def _build_translate_result(
    engine: Translator,
    source_title: str,
    source_outline: str,
    title: str,
    outline: str,
    error: str | None,
    interface: str = "",
    model: str = "",
    fallback_used: bool = False,
    title_interface: str = "",
    title_model: str = "",
    title_fallback: bool = False,
    outline_interface: str = "",
    outline_model: str = "",
    outline_fallback: bool = False,
    requested_title: bool = False,
    requested_outline: bool = False,
    title_field_name: str = "标题",
    outline_field_name: str = "简介",
) -> TranslateResult:
    translated_title = _has_effective_translation(source_title, title)
    translated_outline = _has_effective_translation(source_outline, outline)
    if error is None and not translated_title and not translated_outline:
        error = "未获得有效翻译结果"
    return TranslateResult(
        title=title or source_title,
        outline=outline or source_outline,
        error=error,
        engine=engine,
        translated_title=translated_title,
        translated_outline=translated_outline,
        interface=interface,
        model=model,
        fallback_used=fallback_used,
        title_interface=title_interface,
        title_model=title_model,
        title_fallback=title_fallback,
        outline_interface=outline_interface,
        outline_model=outline_model,
        outline_fallback=outline_fallback,
        requested_title=requested_title,
        requested_outline=requested_outline,
        title_field_name=title_field_name,
        outline_field_name=outline_field_name,
    )


def get_llm_target_language(language: Language | str) -> str:
    if language == Language.ZH_CN or language == Language.ZH_CN.value:
        return "简体中文"
    if language == Language.ZH_TW or language == Language.ZH_TW.value:
        return "繁体中文"
    if language == Language.EN or language == Language.EN.value:
        return "English"
    if language == Language.JP or language == Language.JP.value:
        return "日本語"
    return "简体中文"


def _normalize_translated_linebreaks(text: str) -> str:
    text = (
        text.replace("\r\n", "\n").replace("\r", "\n").replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    )
    text = re.sub(r"(?i)&lt;\s*br\s*/?\s*&gt;", "\n", text)
    return re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)


def _is_llm_refusal(text: str, prefixes: list[str]) -> bool:
    # Only inspect the opening, after whitespace and quotation marks.
    opening = re.sub(r"^[\s\"'“”‘’「」『』«»]+", "", text).casefold()
    return any(prefix.strip() and opening.startswith(prefix.strip().casefold()) for prefix in prefixes)


class TranslationBatchTracker:
    _failures: list[dict[str, str]] = []
    _lock = threading.Lock()

    @classmethod
    def record_failure(cls, movie_number: str, field_name: str, failure_type: str = ""):
        if not movie_number and not field_name:
            return
        with cls._lock:
            cls._failures.append(
                {
                    "number": movie_number or "未知番号",
                    "field": field_name or "未知字段",
                    "type": failure_type or "未知错误",
                }
            )

    @classmethod
    def get_failures(cls) -> list[dict[str, str]]:
        with cls._lock:
            return list(cls._failures)

    @classmethod
    def clear(cls):
        with cls._lock:
            cls._failures.clear()

    @classmethod
    def format_summary(cls) -> str:
        with cls._lock:
            if not cls._failures:
                return "翻译失败、保留原文清单：无"
            items = [f"{item['number']}（{item['field']}）" for item in cls._failures]
            return f"翻译失败、保留原文清单：{'、'.join(items)}"


def _on_batch_reset():
    summary = TranslationBatchTracker.format_summary()
    signal.show_log_text(
        f"\n================================================================================\n 📝 {summary}\n================================================================================"
    )
    signal.add_log(f"📝 {summary}")
    TranslationBatchTracker.clear()


try:
    signal.reset_buttons_status.connect(_on_batch_reset)
except Exception:
    pass


async def _llm_translate(
    text: str,
    prompt_template: str,
    target_language: str = "简体中文",
    details: dict | None = None,
    field_name: str = "",
    movie_number: str = "",
    actor_constraints: dict[str, str] | None = None,
) -> str | None:
    """Retry refusals and unavailable results, then fallback or preserve the source."""
    if not text:
        return ""
    cfg = manager.config
    tc = cfg.translate_config
    primary_is_local = is_loopback_url(str(tc.llm_url))
    primary_interface = "本机主模型" if primary_is_local else "云端主模型"
    primary_model = tc.llm_model.strip()

    if details is not None:
        details["interface"] = primary_interface
        details["model"] = primary_model
        details["fallback"] = False

    user_prompt = prompt_template.replace("{content}", text).replace("{lang}", target_language)
    if actor_constraints:
        constraint_lines = [f"- {orig} -> {trans}" for orig, trans in actor_constraints.items()]
        user_prompt += "\n\n【本片人名统一约束（必须严格使用以下指定中文译名，不得替换或改写）】\n" + "\n".join(
            constraint_lines
        )

    primary_extra_body = None
    if tc.llm_thinking == "enabled":
        primary_extra_body = {"thinking": {"type": "enabled"}}
    elif tc.llm_thinking == "disabled":
        primary_extra_body = {"thinking": {"type": "disabled"}}

    request = {
        "system_prompt": "You are a professional translator.",
        "user_prompt": user_prompt,
        "temperature": tc.llm_temperature,
        "max_try": 1 if primary_is_local else tc.llm_max_try,
        "log_fn": signal.add_log,
        "extra_body": primary_extra_body,
    }

    num_tag = f"[{movie_number}] " if movie_number else ""
    f_tag = f"{field_name} " if field_name else ""

    last_failure_type = "未知错误"
    async with manager.acquire_computed() as computed:
        primary_client = computed.llm_client
        for attempt in range(tc.llm_refusal_retries + 1):
            attempt_num = attempt + 1
            if attempt > 0:
                signal.add_log(f"🔁 翻译被拒：重试第 {attempt} 次")
                signal.add_log(f"🔁 {num_tag}{f_tag}主模型 重试第 {attempt_num} 次")

            translated = await primary_client.ask(model=tc.llm_model, **request)
            if not translated or not translated.strip():
                failure_type = getattr(primary_client, "last_error_type", None) or "空返回"
                last_failure_type = failure_type
                signal.add_log("⚠️ 翻译不可用（请求失败或空返回）")
                signal.add_log(f"⚠️ {num_tag}{f_tag}主模型 第 {attempt_num} 次尝试失败（{failure_type}）")
                continue

            translated = _normalize_translated_linebreaks(translated)
            if not translated.strip():
                last_failure_type = "空返回"
                signal.add_log("⚠️ 翻译不可用（请求失败或空返回）")
                signal.add_log(f"⚠️ {num_tag}{f_tag}主模型 第 {attempt_num} 次尝试失败（空返回）")
                continue

            if not _is_llm_refusal(translated, tc.llm_refusal_prefixes):
                return translated

            last_failure_type = "被拒"
            refusal_snippet = translated.strip()[:30].replace("\r", " ").replace("\n", " ")
            signal.add_log("⚠️ 翻译被拒")
            signal.add_log(f"⚠️ {num_tag}{f_tag}主模型 第 {attempt_num} 次尝试被拒（回复前30字：{refusal_snippet}）")

        if (
            tc.llm_fallback_url
            and tc.llm_fallback_model.strip()
            and (tc.llm_fallback_key.strip() or is_loopback_url(str(tc.llm_fallback_url)))
        ):
            fallback_is_local = is_loopback_url(str(tc.llm_fallback_url))
            fallback_interface = "本机备用" if fallback_is_local else "备用接口"
            fallback_model = tc.llm_fallback_model.strip()
            switch_dest = "转本机备用" if fallback_is_local else "转备用接口"
            field_prefix = f"{field_name}：" if field_name else ""
            switch_msg = f"{field_prefix}主模型失败，{switch_dest}"
            signal.add_log(switch_msg)

            if details is not None:
                details["interface"] = fallback_interface
                details["model"] = fallback_model
                details["fallback"] = True
                details["switch_msg"] = switch_msg

            fallback_extra_body = None
            if tc.llm_fallback_thinking == "enabled":
                fallback_extra_body = {"thinking": {"type": "enabled"}}
            elif tc.llm_fallback_thinking == "disabled":
                fallback_extra_body = {"thinking": {"type": "disabled"}}

            fallback_request = {
                **request,
                "max_try": 1,
                "temperature": tc.llm_fallback_temperature,
                "extra_body": fallback_extra_body,
            }

            fallback = LLMClient(
                api_key=tc.llm_fallback_key,
                base_url=str(tc.llm_fallback_url),
                proxy=cfg.proxy if cfg.use_proxy else None,
                timeout=Timeout(cfg.timeout, read=tc.llm_fallback_read_timeout),
                rate=(max(tc.llm_max_req_sec, 1), max(1, 1 / tc.llm_max_req_sec)),
            )
            try:
                # 备用模型遇到连接异常、服务异常或空返回时，再重试 1 次（被判「拒绝」的不重试）
                fallback_retries = 1
                for fb_attempt in range(fallback_retries + 1):
                    fb_attempt_num = fb_attempt + 1
                    if fb_attempt > 0:
                        signal.add_log(f"🔁 {num_tag}{f_tag}备用模型 重试第 {fb_attempt_num} 次")

                    translated = await fallback.ask(model=tc.llm_fallback_model, **fallback_request)
                    if not translated or not translated.strip():
                        failure_type = getattr(fallback, "last_error_type", None) or "空返回"
                        last_failure_type = failure_type
                        signal.add_log("⚠️ 备用模型不可用（请求失败或空返回）")
                        signal.add_log(f"⚠️ {num_tag}{f_tag}备用模型 第 {fb_attempt_num} 次尝试失败（{failure_type}）")
                        continue

                    translated = _normalize_translated_linebreaks(translated)
                    if not translated.strip():
                        last_failure_type = "空返回"
                        signal.add_log("⚠️ 备用模型不可用（空返回）")
                        signal.add_log(f"⚠️ {num_tag}{f_tag}备用模型 第 {fb_attempt_num} 次尝试失败（空返回）")
                        continue

                    if not _is_llm_refusal(translated, tc.llm_refusal_prefixes):
                        return translated

                    last_failure_type = "被拒"
                    refusal_snippet = translated.strip()[:30].replace("\r", " ").replace("\n", " ")
                    signal.add_log("⚠️ 备用模型翻译被拒")
                    signal.add_log(
                        f"⚠️ {num_tag}{f_tag}备用模型 第 {fb_attempt_num} 次尝试被拒（回复前30字：{refusal_snippet}）"
                    )
                    # 被判「拒绝」的不重试
                    break
            finally:
                await fallback.close()
        else:
            signal.add_log("⚠️ 备用模型未完整配置")

    signal.add_log("📝 保留原文")
    signal.add_log(f"📝 {num_tag}{f_tag}保留原文（失败类型：{last_failure_type}）")
    TranslationBatchTracker.record_failure(movie_number, field_name, last_failure_type)
    return text


async def llm_translate(title: str, outline: str, target_language: str = "简体中文"):
    translate_config = manager.config.translate_config
    r1, r2 = await asyncio.gather(
        _llm_translate(title, translate_config.llm_prompt_title, target_language, field_name="标题"),
        _llm_translate(outline, translate_config.llm_prompt_outline, target_language, field_name="简介"),
    )
    if r1 is None or r2 is None:
        return "", "", "LLM 翻译失败! 查看网络日志以获取更多信息"
    return r1, r2, None


async def translate_with_engine(
    engine: Translator,
    title: str,
    outline: str,
    *,
    title_language: Language | str,
    outline_language: Language | str,
    title_field_name: str = "标题",
    outline_field_name: str = "简介",
    movie_number: str = "",
    actor_constraints: dict[str, str] | None = None,
) -> TranslateResult:
    title_details = {}
    outline_details = {}
    has_title_req = bool(title)
    has_outline_req = bool(outline)

    t_field_name = title_field_name if (has_title_req and has_outline_req) or title_field_name == "标题" else ""
    o_field_name = outline_field_name if (has_title_req and has_outline_req) or outline_field_name == "简介" else ""

    title_result, outline_result = await asyncio.gather(
        _llm_translate(
            title,
            manager.config.translate_config.llm_prompt_title,
            get_llm_target_language(title_language),
            details=title_details,
            field_name=t_field_name,
            movie_number=movie_number,
            actor_constraints=actor_constraints,
        ),
        _llm_translate(
            outline,
            manager.config.translate_config.llm_prompt_outline,
            get_llm_target_language(outline_language),
            details=outline_details,
            field_name=o_field_name,
            movie_number=movie_number,
            actor_constraints=actor_constraints,
        ),
    )
    tc = manager.config.translate_config
    default_interface = "本机主模型" if is_loopback_url(str(tc.llm_url)) else "云端主模型"
    default_model = tc.llm_model.strip()

    title_interface = title_details.get("interface", default_interface)
    title_model = title_details.get("model", default_model)
    title_fallback = bool(title_details.get("fallback"))

    outline_interface = outline_details.get("interface", default_interface)
    outline_model = outline_details.get("model", default_model)
    outline_fallback = bool(outline_details.get("fallback"))

    fallback_used = title_fallback or outline_fallback

    if fallback_used:
        interface = outline_interface if outline_fallback else title_interface
        model = outline_model if outline_fallback else title_model
    else:
        interface = title_interface if has_title_req else outline_interface
        model = title_model if has_title_req else outline_model

    error = "LLM 翻译失败! 查看网络日志以获取更多信息" if title_result is None or outline_result is None else None
    result = _build_translate_result(
        engine,
        title,
        outline,
        title_result or "",
        outline_result or "",
        error,
        interface=interface,
        model=model,
        fallback_used=fallback_used,
        title_interface=title_interface,
        title_model=title_model,
        title_fallback=title_fallback,
        outline_interface=outline_interface,
        outline_model=outline_model,
        outline_fallback=outline_fallback,
        requested_title=has_title_req,
        requested_outline=has_outline_req,
        title_field_name=title_field_name,
        outline_field_name=outline_field_name,
    )
    if error is None:
        result.error = None
    return result


def get_translator_skip_reason(translator: Translator) -> str | None:
    translate_config = manager.config.translate_config

    def _missing_reason(fields: list[tuple[str, str]]) -> str | None:
        missing = [name for name, value in fields if not value.strip()]
        if not missing:
            return None
        return f"{'、'.join(missing)} 未配置"

    if translator == Translator.LLM:
        fields = [("LLM Model", translate_config.llm_model)]
        if not is_loopback_url(str(translate_config.llm_url)):
            fields.append(("LLM API Key", translate_config.llm_key))
        return _missing_reason(fields)
    return None
