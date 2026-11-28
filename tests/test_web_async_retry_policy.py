"""请求层重试策略：curl 47（TooManyRedirects）不重试，Timeout 仍按 retry 次数重试。"""

import pytest
from curl_cffi.requests.exceptions import Timeout, TooManyRedirects

from mdcx.web_async import AsyncWebClient


def _install_failing_sessions(client: AsyncWebClient, error: Exception, attempts: list[dict]) -> None:
    class FailingSession:
        closed = False

        def __init__(self, _fingerprint=None):
            pass

        async def close(self):
            self.closed = True

        async def request(self, **kwargs):
            attempts.append(kwargs)
            raise error

    client._pool_manager._session_factory = FailingSession  # type: ignore[assignment]


def _record_only(client: AsyncWebClient, records: list[str]):
    async def fake_record(error_msg: str, *, pool_key: str) -> None:
        records.append(error_msg)

    client._record_transport_failure = fake_record  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_too_many_redirects_returns_after_single_attempt():
    client = AsyncWebClient(timeout=1, retry=3)
    attempts: list[dict] = []
    transport_records: list[str] = []
    _install_failing_sessions(client, TooManyRedirects("Maximum (50) redirects followed"), attempts)
    _record_only(client, transport_records)

    text, error = await client.get_text("https://example.test/detail")

    assert text is None
    assert "失败" in error and "请求异常" in error
    assert len(attempts) == 1
    assert len(transport_records) == 1
    await client.close()


@pytest.mark.asyncio
async def test_timeout_still_retries_with_configured_retry_count(monkeypatch: pytest.MonkeyPatch):
    client = AsyncWebClient(timeout=1, retry=3)
    attempts: list[dict] = []
    transport_records: list[str] = []
    _install_failing_sessions(client, Timeout("timed out"), attempts)
    _record_only(client, transport_records)
    monkeypatch.setattr(client, "_calc_retry_sleep_seconds", lambda *args, **kwargs: 0)

    text, error = await client.get_text("https://example.test/detail")

    assert text is None
    assert "失败" in error and "连接超时" in error
    assert len(attempts) == 3
    assert len(transport_records) == 3
    await client.close()
