from types import SimpleNamespace

import httpx
import pytest

import mdcx.base.web as web
from mdcx.version import is_newer_version, normalize_version, parse_version


@pytest.mark.parametrize("version", ["v1.1.0", "1.1.0", " v1.1.0 "])
def test_normalize_stable_version(version):
    assert normalize_version(version) == "v1.1.0"


@pytest.mark.parametrize("version", ["220261012", "v1.0", "v01.1.0", "v1.1.0-rc.1", "test-20261011", ""])
def test_reject_mixed_release_numbering(version):
    with pytest.raises(ValueError):
        parse_version(version)


@pytest.mark.parametrize(
    "latest,current,newer",
    [
        ("v1.1.0", "v1.0.2", True),
        ("v1.10.0", "v1.9.9", True),
        ("v1.1.10", "v1.1.9", True),
        ("v2.0.0", "v1.99.99", True),
        ("v1.1.0", "v1.1.0", False),
        ("v1.0.2", "v1.1.0", False),
    ],
)
def test_compare_version_components(latest, current, newer):
    assert is_newer_version(latest, current) is newer


@pytest.fixture
def update_client(monkeypatch):
    calls, logs = [], []
    monkeypatch.setattr(web.manager.config, "update_check", True)
    monkeypatch.setattr(web.manager.config, "use_proxy", False)
    monkeypatch.setattr(web.signal, "add_log", logs.append)

    def install(response, *, fail_proxy=False):
        class Client:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def get(self, url, **kwargs):
                calls.append((url, self.kwargs))
                if fail_proxy and "proxy" in self.kwargs:
                    raise httpx.ConnectError("synthetic proxy failure")
                return response

        monkeypatch.setattr(web.httpx, "Client", Client)

    return SimpleNamespace(install=install, calls=calls, logs=logs)


def test_update_check_accepts_users_semantic_tag(update_client):
    update_client.install(httpx.Response(200, json={"tag_name": "v1.10.0", "prerelease": False, "draft": False}))
    assert web.check_version() == "v1.10.0"
    assert update_client.calls[0][0] == "https://api.github.com/repos/Marcus515J/mdcx/releases/latest"
    assert not update_client.logs


@pytest.mark.parametrize(
    "payload",
    [
        {"tag_name": "220261012"},
        {"tag_name": "test-20261011-local"},
        {"tag_name": "v1.2.0", "prerelease": True},
        {"tag_name": "v1.2.0", "draft": True},
        {},
    ],
)
def test_update_check_does_not_offer_date_test_or_invalid_releases(update_client, payload):
    update_client.install(httpx.Response(200, json=payload))
    assert web.check_version() is None


def test_update_check_keeps_direct_retry_after_proxy_failure(update_client, monkeypatch):
    monkeypatch.setattr(web.manager.config, "use_proxy", True)
    monkeypatch.setattr(web.manager.config, "proxy", "http://127.0.0.1:8999")
    update_client.install(httpx.Response(200, json={"tag_name": "v1.1.0"}), fail_proxy=True)
    assert web.check_version() == "v1.1.0"
    assert len(update_client.calls) == 2
    assert "proxy" in update_client.calls[0][1] and "proxy" not in update_client.calls[1][1]


def test_update_check_disabled_does_not_request(update_client, monkeypatch):
    monkeypatch.setattr(web.manager.config, "update_check", False)
    assert web.check_version() is None
    assert not update_client.calls


def test_update_check_preserves_rate_limit_diagnostic(update_client):
    update_client.install(httpx.Response(403, headers={"x-ratelimit-remaining": "0"}))
    assert web.check_version() is None
    assert "GitHub API 限流" in update_client.logs[-1]


@pytest.mark.parametrize("latest,newer", [("v1.1.0", False), ("v1.10.0", True), (None, False)])
def test_window_reports_semantic_version_and_update_link(monkeypatch, latest, newer):
    from mdcx.controllers.main_window import main_window as window_module

    messages, links, cursors = [], [], []
    monkeypatch.setattr(window_module, "check_version", lambda: latest)
    monkeypatch.setattr(window_module.signal_qt, "show_log_text", messages.append)
    monkeypatch.setattr(window_module.signal_qt, "show_scrape_info", lambda: None)
    monkeypatch.setattr(window_module.manager.config, "use_database", False)
    monkeypatch.setattr(
        window_module, "threading", SimpleNamespace(Thread=lambda **_kwargs: SimpleNamespace(start=lambda: None))
    )
    window = SimpleNamespace(
        localversion="v1.1.0",
        new_version="",
        Ui=SimpleNamespace(label_show_version=SimpleNamespace(setCursor=cursors.append)),
        main_logs_show=SimpleNamespace(emit=links.append),
        pushButton_check_javdb_cookie_clicked=lambda: None,
        pushButton_check_javbus_cookie_clicked=lambda: None,
    )
    window_module.MyMAinWindow._show_version_thread(window)
    assert "当前版本: v1.1.0" in messages[0]
    assert ("有新版本" in window.new_version) is newer
    assert any("下载新版本" in link for link in links) is newer
    assert all("问题反馈" not in text and "GitHub Issues" not in text for text in messages + links)
    if not newer:
        assert not links
    if newer:
        assert "v1.10.0" in messages[0] and cursors
    elif latest:
        assert "最新版本" in messages[0]
