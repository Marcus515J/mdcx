"""Synthetic service failures: no live sites, containers or user files."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from curl_cffi.requests.exceptions import ConnectionError

from mdcx.models.crawl_status import BatchDiagnostics, ServiceStopped, batch_diagnostics, check_service_stop
from mdcx.models.flags import Flags
from mdcx.web_async import AsyncWebClient


@pytest.fixture
def batch(monkeypatch):
    value = BatchDiagnostics()
    token = batch_diagnostics.set(value)
    monkeypatch.setattr(Flags, "stop_requested", False)
    monkeypatch.setattr(Flags, "service_stop_reason", "")
    try:
        yield value
    finally:
        batch_diagnostics.reset(token)


@pytest.mark.parametrize("category", ["mirror", "/html", "代理"])
def test_independent_streak_reset_and_stop(batch, category):
    notify = Mock()
    batch.on_service_stop = notify
    for other in {"mirror", "/html", "代理"} - {category}:
        batch.record_service(other, False)
    batch.record_service(category, False)
    batch.record_service(category, False)
    batch.record_service(category, True)
    assert batch.service_streaks[category] == 0
    for index in range(3):
        batch.record_service(category, False)
        assert bool(batch.stop_reason) is (index == 2)
    assert category in batch.stop_reason
    notify.assert_called_once_with(batch.stop_reason)
    assert any(batch.stop_reason in line for line in batch.lines(incomplete=True))
    assert all(any(other in line for line in batch.lines()) for other in ("mirror", "/html", "代理"))


def bypass_kwargs(host, method="GET"):
    return {
        "host": host,
        "method": method,
        "target_url": f"https://{host}/",
        "headers": {},
        "cookies": None,
        "data": None,
        "json_data": None,
        "timeout": None,
        "allow_redirects": True,
        "use_proxy": False,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("category", ["mirror", "/html"])
async def test_bypass_final_outcomes_cross_sites_and_no_more_requests(monkeypatch, batch, category):
    client = AsyncWebClient(timeout=1, cf_bypass_url="http://bypass.test")
    client._cf_bypass_min_interval = 0
    client._cf_bypass_retries = 2
    client._calc_retry_sleep_seconds = lambda *a, **k: 0
    response = SimpleNamespace(headers={}, status_code=200)
    mirror = AsyncMock(return_value=(None, "mirror 请求超时"))
    html = AsyncMock(return_value=(None, "/html 等待超时"))
    monkeypatch.setattr(client, "_call_bypass_mirror", mirror)
    monkeypatch.setattr(client, "_call_bypass_html", html)
    try:
        for index in range(3):
            kwargs = bypass_kwargs(f"site{index}.test", "POST" if category == "mirror" else "GET")
            if index == 2:
                with pytest.raises(ServiceStopped):
                    await client._try_bypass_cloudflare(**kwargs)
            else:
                assert (await client._try_bypass_cloudflare(**kwargs))[0] is None
                assert batch.service_streaks[category] == index + 1
                if category == "/html":
                    # Successful mirror traffic resets only mirror, so /html can trip independently.
                    mirror.return_value = (response, "")
                    await client._try_bypass_cloudflare(**bypass_kwargs(f"reset{index}.test"))
                    mirror.return_value = (None, "mirror 请求超时")
        assert category in batch.stop_reason
        assert mirror.await_count == (6 if category == "mirror" else 5)
        calls = mirror.await_count
        with pytest.raises(ServiceStopped):
            await client.request("GET", "https://another.test/")
        with pytest.raises(ServiceStopped):
            await client._curl_request(url="https://another.test/")
        assert mirror.await_count == calls
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_proxy_counts_exhausted_request_once_and_resets_on_success(monkeypatch, batch):
    client = AsyncWebClient(timeout=1, retry=3, proxy="http://proxy.test", cf_bypass_url="")
    request = AsyncMock(side_effect=ConnectionError("synthetic connection failure"))
    monkeypatch.setattr(client, "_curl_request", request)
    monkeypatch.setattr(client, "_calc_retry_sleep_seconds", lambda *a, **k: 0)
    try:
        for index in range(2):
            assert (await client.request("GET", f"https://site{index}.test/"))[0] is None
            assert batch.service_streaks["代理"] == index + 1
        assert request.await_count == 6
        request.side_effect = None
        request.return_value = SimpleNamespace(status_code=200, headers={})
        assert (await client.request("GET", "https://success.test/"))[0] is not None
        assert batch.service_streaks["代理"] == 0
        request.side_effect = ConnectionError("synthetic connection failure")
        for index in range(2):
            await client.request("GET", f"https://retry{index}.test/")
        with pytest.raises(ServiceStopped):
            await client.request("GET", "https://final.test/")
        assert batch.service_failures["代理"] == 5
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_scheduler_cancels_inflight_and_keeps_unfinished_files(monkeypatch, tmp_path, batch):
    from mdcx.core import scraper as module
    from mdcx.models.types import FileInfo

    Flags.reset()
    monkeypatch.setattr(module.signal, "stop", False)
    for name, value in {"garbage_enabled": False, "thread_time": 0, "switch_on": []}.items():
        monkeypatch.setattr(module.manager.config, name, value)
    files = [tmp_path / f"synthetic-{i}.mp4" for i in range(4)]
    for path in files:
        path.write_bytes(b"unchanged")
    Flags.remain_list = files.copy()
    Flags.total_count = len(files)
    scraper = module.Scraper(object())
    batch.on_service_stop = scraper._stop_service
    logs, reasons = [], []
    monkeypatch.setattr(module.signal, "show_log_text", logs.append)
    module.signal.service_stopped.connect(reasons.append)
    started, cancelled = [], []
    second_started = asyncio.Event()

    async def info(path):
        result = FileInfo.empty()
        result.file_path, result.folder_path = path, path.parent
        result.number, result.file_show_name = path.stem, path.name
        return result

    async def process(info, mode):
        started.append(info.file_path)
        if info.file_path == files[0]:
            await second_started.wait()
            for _ in range(3):
                batch.record_service("mirror", False)
            check_service_stop()
        second_started.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.append(info.file_path)

    monkeypatch.setattr(module, "get_file_info_v2", info)
    monkeypatch.setattr(scraper, "_process_one_file", process)
    try:
        await scraper._run_tasks_with_limit(files, len(files), 2)
        assert started == files[:2]
        assert cancelled == [files[1]]
        assert Flags.remain_list == files
        assert Flags.scrape_done == 0
        assert reasons == [batch.stop_reason]
        assert any('color="red"' in text and batch.stop_reason in text for text in logs)
        assert all(path.read_bytes() == b"unchanged" for path in files)
    finally:
        module.signal.service_stopped.disconnect(reasons.append)


def test_window_service_popup_is_nonblocking_and_keeps_taskbar_red(monkeypatch):
    from mdcx.controllers.main_window import main_window as module

    monkeypatch.setattr(module, "IS_WINDOWS", True)
    monkeypatch.setattr(Flags, "service_stop_reason", "synthetic service stop")
    box = Mock()
    monkeypatch.setattr(module, "QMessageBox", Mock(return_value=box))
    window = SimpleNamespace(_taskbar_progress=Mock(), winId=lambda: 123)
    window._update_taskbar_progress = lambda: module.MyMAinWindow._update_taskbar_progress(window)
    module.MyMAinWindow._show_service_stop(window, Flags.service_stop_reason)
    box.open.assert_called_once()
    box.exec.assert_not_called()
    module.MyMAinWindow._clear_taskbar_progress(window)
    window._taskbar_progress.show_error.assert_called_with(123, Flags.scrape_processed, Flags.total_count)
    window._taskbar_progress.clear.assert_not_called()
