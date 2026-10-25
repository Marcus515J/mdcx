import asyncio
import json
import threading
import time
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import httpx
import pytest

from mdcx.base import translate as translation
from mdcx.config.enums import Translator
from mdcx.config.models import Config, TranslateConfig
from mdcx.llm import LLMClient, is_loopback_url


@pytest.fixture
def server():
    calls = []
    replies = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append((self.path, body))
            reply = replies.pop(0)
            status = 200
            if reply == "timeout":
                time.sleep(0.15)
                reply = "迟来的译文"
            elif reply == "error":
                status = 503
                reply = "unavailable"
            choices = (
                []
                if reply == "no_choices"
                else [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}]
            )
            payload = json.dumps(
                {"id": "mock", "object": "chat.completion", "created": 1, "model": body["model"], "choices": choices}
            ).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

    instance = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{instance.server_port}", replies, calls
    instance.shutdown()
    instance.server_close()
    thread.join()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "normal",
        "retry",
        "fallback",
        "all_refused",
        "error",
        "timeout",
        "empty",
        "no_choices",
        "think_only",
        "fallback_error",
        "fallback_empty",
        "fallback_linebreaks",
        "disabled_backup",
    ],
)
async def test_real_openai_requests_and_order(server, monkeypatch, path):
    url, replies, calls = server
    refusal = "抱歉，我无法完成翻译。"
    source = "日本語の題名"
    expected = "测试译文"
    if path == "normal":
        replies[:] = [expected]
    elif path == "retry":
        replies[:] = [refusal, expected]
    elif path in {
        "fallback",
        "all_refused",
        "fallback_error",
        "fallback_empty",
        "fallback_linebreaks",
        "disabled_backup",
    }:
        replies[:] = [refusal, refusal, expected]
        if path == "all_refused":
            replies[-1] = refusal
            expected = source
        elif path == "fallback_error":
            replies[-1] = "error"
            replies.append("error")
            expected = source
        elif path == "fallback_empty":
            replies[-1] = " "
            replies.append(" ")
            expected = source
        elif path == "fallback_linebreaks":
            replies[-1] = "<br />"
            replies.append("<br />")
            expected = source
        elif path == "disabled_backup":
            replies.pop()
            expected = source
    else:
        unavailable = {
            "error": "error",
            "timeout": "timeout",
            "empty": " \n",
            "no_choices": "no_choices",
            "think_only": "<think>analysis</think>",
        }[path]
        replies[:] = [unavailable, unavailable, expected]
    cfg = Config(
        use_proxy=True,
        proxy="http://127.0.0.1:1",
        translate_config=TranslateConfig(
            llm_url=url + "/primary/v1",
            llm_model="HY-MT2-7B-Q8_0",
            llm_key="",
            llm_fallback_url=None if path == "disabled_backup" else url + "/backup/v1",
            llm_fallback_model="backup",
            llm_fallback_key="",
            llm_max_req_sec=100,
        ),
    )
    monkeypatch.setattr(translation.manager, "config", cfg)
    logs = []
    monkeypatch.setattr(translation.signal, "add_log", logs.append)
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://127.0.0.1:1")
    monkeypatch.delenv("NO_PROXY", raising=False)
    primary = LLMClient(
        api_key="",
        base_url=str(cfg.translate_config.llm_url),
        proxy=cfg.proxy,
        timeout=httpx.Timeout(0.05 if path == "timeout" else 2),
        rate=(100, 1),
    )

    @asynccontextmanager
    async def lease():
        yield SimpleNamespace(llm_client=primary)

    monkeypatch.setattr(translation.manager, "acquire_computed", lease)
    try:
        assert primary.client.max_retries == 0
        assert translation.get_translator_skip_reason(Translator.LLM) is None
        assert await translation._llm_translate(source, "Translate to {lang}: {content}") == expected
        assert primary._active_requests == 0
    finally:
        await primary.close()
    assert not replies
    if path in {"fallback_error", "fallback_empty", "fallback_linebreaks"}:
        expected_count = 4
    elif path == "normal":
        expected_count = 1
    elif path in {"retry", "disabled_backup"}:
        expected_count = 2
    else:
        expected_count = 3
    assert len(calls) == expected_count
    backup_count = expected_count - min(2, expected_count)
    assert [body["model"] for _, body in calls] == ["HY-MT2-7B-Q8_0"] * min(2, expected_count) + (
        ["backup"] * backup_count
    )
    assert all(body["messages"] == calls[0][1]["messages"] for _, body in calls)
    assert calls[0][0] == "/primary/v1/chat/completions"
    if expected_count == 3:
        assert calls[-1][0] == "/backup/v1/chat/completions"
    assert ("📝 保留原文" in logs) == (expected == source)
    if path == "fallback_linebreaks":
        assert "⚠️ 备用模型不可用（空返回）" in logs


@pytest.mark.asyncio
async def test_service_not_started_preserves_source(monkeypatch):
    cfg = Config()
    monkeypatch.setattr(translation.manager, "config", cfg)
    requests = []

    async def disconnected(request):
        requests.append(request)
        raise httpx.ConnectError("mock offline", request=request)

    primary = LLMClient(api_key="", base_url=str(cfg.translate_config.llm_url), timeout=httpx.Timeout(1), rate=(100, 1))
    await primary.client._client.aclose()
    primary.client._client = httpx.AsyncClient(transport=httpx.MockTransport(disconnected))

    @asynccontextmanager
    async def lease():
        yield SimpleNamespace(llm_client=primary)

    monkeypatch.setattr(translation.manager, "acquire_computed", lease)
    try:
        assert await translation._llm_translate("日本語", "{content}") == "日本語"
        assert len(requests) == 2
    finally:
        await primary.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    ["normal", "retry", "refusal", "error", "disconnected", "timeout", "empty", "local_error", "local_refusal"],
)
async def test_cloud_primary_with_keyless_local_fallback(server, monkeypatch, path):
    """The existing configuration can reverse the chain without changing the application."""
    url, local_replies, local_calls = server
    source, expected = "日本語の題名", "测试译文"
    refusal = "抱歉，我无法完成翻译。"
    cloud_replies = [expected] if path == "normal" else [refusal, expected] if path == "retry" else [refusal, refusal]
    if path not in {"normal", "retry"}:
        if path == "local_error":
            local_replies[:] = ["error", "error"]
        elif path == "local_refusal":
            local_replies[:] = [refusal]
        else:
            local_replies[:] = [expected]
    if path in {"local_error", "local_refusal"}:
        expected = source
    cfg = Config(
        use_proxy=True,
        proxy="http://127.0.0.1:1",
        translate_config=TranslateConfig(
            translate_by=[Translator.LLM],
            llm_url="https://cloud.example.com/v1",
            llm_model="cloud-model",
            llm_key="synthetic-cloud-key",
            llm_max_try=1,
            llm_refusal_retries=1,
            llm_fallback_url=url + "/v1",
            llm_fallback_model="HY-MT2-7B-Q8_0",
            llm_fallback_key="",
            llm_max_req_sec=100,
        ),
    )
    monkeypatch.setattr(translation.manager, "config", cfg)
    logs, cloud_calls = [], []
    monkeypatch.setattr(translation.signal, "add_log", logs.append)
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://127.0.0.1:1")
    monkeypatch.delenv("NO_PROXY", raising=False)

    async def cloud_transport(request):
        # Local inference must not start before the cloud's two attempts finish.
        assert not local_calls
        cloud_calls.append(json.loads(request.content))
        assert request.url.host == "cloud.example.com"
        assert request.headers["Authorization"] == "Bearer synthetic-cloud-key"
        if path == "disconnected":
            raise httpx.ConnectError("mock offline", request=request)
        if path == "timeout":
            raise httpx.ReadTimeout("mock timeout", request=request)
        if path == "error":
            return httpx.Response(503, json={"error": {"message": "mock unavailable"}})
        content = " " if path == "empty" else cloud_replies.pop(0)
        return httpx.Response(
            200,
            json={
                "id": "mock",
                "object": "chat.completion",
                "created": 1,
                "model": "cloud-model",
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
                ],
            },
        )

    primary = LLMClient(
        api_key=cfg.translate_config.llm_key,
        base_url=str(cfg.translate_config.llm_url),
        timeout=httpx.Timeout(2),
        rate=(100, 1),
    )
    await primary.client._client.aclose()
    primary.client._client = httpx.AsyncClient(transport=httpx.MockTransport(cloud_transport), trust_env=False)

    @asynccontextmanager
    async def lease():
        yield SimpleNamespace(llm_client=primary)

    monkeypatch.setattr(translation.manager, "acquire_computed", lease)
    try:
        assert translation.get_translator_skip_reason(Translator.LLM) is None
        assert await translation._llm_translate(source, "Translate to {lang}: {content}") == expected
    finally:
        await primary.close()
    assert len(cloud_calls) == (1 if path == "normal" else 2)
    assert all(body["model"] == "cloud-model" for body in cloud_calls)
    assert len(local_calls) == (0 if path in {"normal", "retry"} else 2 if path == "local_error" else 1)
    assert not local_replies
    if local_calls:
        endpoint, body = local_calls[0]
        assert endpoint == "/v1/chat/completions"
        assert body["model"] == "HY-MT2-7B-Q8_0"
        assert body["messages"] == cloud_calls[0]["messages"]
        assert body["temperature"] == cloud_calls[0]["temperature"]
    assert ("主模型失败，转本机备用" in logs) == bool(local_calls)
    assert ("📝 保留原文" in logs) == (expected == source)


@pytest.mark.parametrize(
    "url,local",
    [
        ("http://localhost:8080/v1", True),
        ("http://127.1.2.3/v1", True),
        ("http://[::1]:8080/v1", True),
        ("https://localhost.example/v1", False),
        ("https://api.deepseek.com/v1", False),
        ("http://192.168.1.2/v1", False),
        ("http://[", False),
    ],
)
def test_local_address_detection(url, local):
    assert is_loopback_url(url) is local


@pytest.mark.asyncio
async def test_transport_retry_does_not_sleep_after_last_request(monkeypatch):
    sleeps, calls = [], []

    async def fail(request):
        calls.append(request)
        return httpx.Response(503, json={"error": {"message": "mock"}})

    async def sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", sleep)
    client = LLMClient(api_key="mock", base_url="https://api.example.com/v1", timeout=httpx.Timeout(1), rate=(100, 1))
    await client.client._client.aclose()
    client.client._client = httpx.AsyncClient(transport=httpx.MockTransport(fail))
    try:
        assert await client.ask(model="mock", system_prompt="translate", user_prompt="text", max_try=3) is None
        assert len(calls) == 3
        assert sleeps == [1, 2]
    finally:
        await client.close()
