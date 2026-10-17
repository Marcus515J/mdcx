"""Capture SDK request bodies without making any HTTP connections."""

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest

from mdcx.base import translate as translation
from mdcx.config.manager import ConfigManager
from mdcx.config.models import Config, TranslateConfig
from mdcx.llm import LLMClient


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_temperature,fallback_temperature", [(0.35, 1.25), (2.0, 0.0)])
async def test_primary_and_fallback_send_independent_temperatures(
    monkeypatch, primary_temperature, fallback_temperature
):
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append((request.url.host, body))
        content = "抱歉，无法翻译" if request.url.host == "primary.example.com" else "测试译文"
        return httpx.Response(
            200,
            json={
                "id": "mock",
                "object": "chat.completion",
                "created": 1,
                "model": body["model"],
                "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
            },
        )

    def mock_client(**kwargs):
        client = LLMClient(**kwargs)
        # Inject the transport at the HTTP boundary; still exercise SDK serialization.
        client.client._client._transport = httpx.MockTransport(respond)
        client.client._client._mounts = {}
        return client

    cfg = Config(
        translate_config=TranslateConfig(
            llm_url="https://primary.example.com/v1",
            llm_key="synthetic-primary",
            llm_model="primary",
            llm_temperature=primary_temperature,
            llm_fallback_url="https://backup.example.com/v1",
            llm_fallback_key="synthetic-backup",
            llm_fallback_model="backup",
            llm_fallback_temperature=fallback_temperature,
            llm_max_req_sec=100,
        )
    )
    primary = mock_client(
        api_key="synthetic-primary", base_url=str(cfg.translate_config.llm_url), timeout=httpx.Timeout(1), rate=(100, 1)
    )

    @asynccontextmanager
    async def lease():
        yield SimpleNamespace(llm_client=primary)

    monkeypatch.setattr(translation.manager, "config", cfg)
    monkeypatch.setattr(translation.manager, "acquire_computed", lease)
    monkeypatch.setattr(translation, "LLMClient", mock_client)
    try:
        assert await translation._llm_translate("日本語", "{content}") == "测试译文"
    finally:
        await primary.close()
    assert [(host, body["model"], body["temperature"]) for host, body in calls] == [
        ("primary.example.com", "primary", primary_temperature),
        ("primary.example.com", "primary", primary_temperature),
        ("backup.example.com", "backup", fallback_temperature),
    ]


@pytest.mark.parametrize("primary_temperature", [0.0, 0.37, 2.0])
def test_old_config_inherits_temperature_and_roundtrips(tmp_path, monkeypatch, primary_temperature):
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"translate_config": {"llm_temperature": primary_temperature}}), encoding="utf-8")
    manager = ConfigManager.__new__(ConfigManager)
    manager._path = path
    # Exercise actual file load/save without constructing unrelated network clients.
    monkeypatch.setattr(manager, "_replace_config", lambda config: setattr(manager, "config", config))
    assert manager.load() == []
    assert manager.config.translate_config.llm_fallback_temperature == primary_temperature
    manager.config.translate_config.llm_fallback_temperature = 1.23
    manager.save()
    assert json.loads(path.read_text(encoding="utf-8"))["translate_config"]["llm_fallback_temperature"] == 1.23
    assert manager.load() == []
    assert manager.config.translate_config.llm_temperature == primary_temperature
    assert manager.config.translate_config.llm_fallback_temperature == 1.23
