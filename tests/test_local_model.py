import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

from mdcx import local_model as local
from mdcx.controllers.main_window.local_model_settings import search_roots


def installation(root, name="HY-MT2-7B-Q8_0.gguf"):
    root.mkdir(parents=True, exist_ok=True)
    server, model = root / "llama-server.exe", root / name
    server.write_bytes(b"MZfixture")
    model.write_bytes(b"GGUFfixture")
    return str(server), str(model)


def test_discovery_records_multiple_candidates_exclusions_and_literal_paths(tmp_path):
    a = installation(tmp_path / "海南鸡 [安装] 空格")
    b = installation(tmp_path / "另一份", "HY-MT2-7B-Q4.gguf")
    installation(tmp_path / "Windows")
    installation(tmp_path / "_待删")
    installation(tmp_path / "私人隔离")
    (tmp_path / "海南鸡 [安装] 空格" / "stage2_runtime.json").write_text(
        json.dumps({"llama_server_path": "llama-server.exe", "model_path": "HY-MT2-7B-Q8_0.gguf"}), encoding="utf-8-sig"
    )
    bad = tmp_path / "损坏"
    bad.mkdir()
    (bad / "stage2_runtime.json").write_text("invalid")
    (bad / "llama-server.exe").write_bytes(b"bad")
    result = local.discover([str(tmp_path)], excluded=(str(tmp_path / "私人隔离"),))
    assert result.servers[0] == a[0] and result.models[0] == a[1]
    assert set(result.servers) == {a[0], b[0]}
    assert set(result.models) == {a[1], b[1]}


def test_valid_cache_never_scans_and_missing_cache_rescans(tmp_path, monkeypatch):
    server, model = installation(tmp_path / "安装")
    scandir = local.os.scandir
    monkeypatch.setattr(local.os, "scandir", lambda _: pytest.fail("valid cache must not scan"))
    assert local.discover([], server, model).cached
    monkeypatch.setattr(local.os, "scandir", scandir)
    Path(model).unlink()
    replacement = installation(tmp_path / "新位置")
    result = local.discover([str(tmp_path)], server, model)
    assert not result.cached and replacement[1] in result.models
    assert server in result.servers


def test_scan_lists_hy_index_and_other_valid_gguf_with_hy_preferred(tmp_path):
    server, hy = installation(tmp_path / "安装")
    root = Path(hy).parent
    index = root / "Index-Translate-9B.Q6_K.gguf"
    other = root / "Other-Translator.gguf"
    for path in (index, other):
        path.write_bytes(b"GGUFfixture")
    (root / "bad.gguf").write_bytes(b"invalid")
    result = local.discover([str(tmp_path)], server, str(index), force=True)
    assert result.models[0] == hy
    assert set(result.models) == {hy, str(index), str(other)}
    assert local.model_alias("H:/0AI/models/Index-Translate-9B.Q6_K.gguf") == "Index-Translate-9B.Q6_K"
    assert local.model_alias(r"H:\0AI\models\Index-Translate-9B.Q6_K.gguf") == "Index-Translate-9B.Q6_K"


def test_cancel_missing_root_and_link_protection(tmp_path):
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(InterruptedError):
        local.discover([str(tmp_path)], cancel=cancel)
    with pytest.raises(ValueError):
        local.discover([])
    with pytest.raises(ValueError):
        local.discover([str(tmp_path / "missing")])
    if os.name != "nt":
        real = tmp_path / "outside"
        installation(real)
        root = tmp_path / "root"
        root.mkdir()
        (root / "linked").symlink_to(real, target_is_directory=True)
        assert not local.discover([str(root)]).servers


def test_root_parser_preserves_browsed_literal_directory():
    assert search_roots("H D，E:") == ["H:\\", "D:\\", "E:\\"]
    assert search_roots("H:\\中文 [安装] 空 格") == ["H:\\中文 [安装] 空 格"]
    assert search_roots("") == []


@pytest.mark.parametrize(
    "health,models,expected",
    [
        ((200, {"status": "ok"}), (200, {"data": [{"id": "HY-MT2-custom"}]}), "HY-MT2-custom"),
        ((200, {"status": "ok"}), (200, {"data": [{"id": "Index-Translate-9B.Q6_K"}]}), "Index-Translate-9B.Q6_K"),
        ((503, {"status": "loading"}), (200, {"data": [{"id": local.MODEL_ALIAS}]}), ""),
        ((200, {"status": "ok"}), (200, {"data": [{"id": "other-model"}]}), ""),
        ((302, {}), (200, {"data": [{"id": local.MODEL_ALIAS}]}), ""),
        ((200, {"status": "ok"}), (500, {}), ""),
    ],
)
def test_health_requires_ready_model_and_bypasses_proxy(monkeypatch, health, models, expected):
    client_class = httpx.Client
    calls = []

    def response(request):
        calls.append(str(request.url))
        status, body = health if request.url.path == "/health" else models
        return httpx.Response(status, json=body, headers={"Location": "https://should-never-follow.invalid"})

    def client(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return client_class(**kwargs, transport=httpx.MockTransport(response))

    monkeypatch.setattr(local.httpx, "Client", client)
    assert local.LocalModelService().ready_model() == expected
    assert all(url.startswith("http://127.0.0.1:8080/") for url in calls)


PYTHON_SERVER = """
import json, os, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
mode = os.environ.get("MDCX_LAUNCHER_TEST_MODE", "ready")
if mode == "fail":
    print("MOCK_DLL_FAILURE", file=sys.stderr, flush=True)
    sys.exit(42)
if mode == "hang":
    time.sleep(120)
args = sys.argv[1:]
alias = args[args.index("--alias") + 1]
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        health = self.path == "/health"
        body = {"status": "loading" if mode == "loading" else "ok"} if health else {"data": [{"id": alias}]}
        self.send_response(503 if health and mode == "loading" else 200)
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())
    def log_message(self, *args): pass
HTTPServer(("127.0.0.1", 8080), Handler).serve_forever()
"""


POWERSHELL = Path(os.environ.get("SystemRoot", "C:/Windows")) / ("System32/WindowsPowerShell/v1.0/powershell.exe")

FAKE_SERVER = r"""
using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Diagnostics;
public class FakeServer {
    public static int Main(string[] args) {
        string record = Environment.GetEnvironmentVariable("MDCX_LAUNCHER_TEST_RECORD");
        if (!String.IsNullOrEmpty(record)) {
            File.WriteAllLines(record, args, new UTF8Encoding(false));
            File.WriteAllText(record + ".pid", Process.GetCurrentProcess().Id.ToString());
        }
        string mode = Environment.GetEnvironmentVariable("MDCX_LAUNCHER_TEST_MODE");
        if (mode == "fail") { Console.Error.WriteLine("MOCK_DLL_FAILURE"); return 42; }
        if (mode == "hang") { Thread.Sleep(120000); return 0; }
        int port = Int32.Parse(args[Array.IndexOf(args, "--port") + 1]);
        string alias = args[Array.IndexOf(args, "--alias") + 1];
        var listener = new TcpListener(IPAddress.Loopback, port);
        listener.Start();
        while (true) {
            using (var client = listener.AcceptTcpClient()) {
                client.ReceiveTimeout = 2500;
                try {
                    var stream = client.GetStream();
                    var reader = new StreamReader(stream, Encoding.ASCII);
                    string first = reader.ReadLine();
                    if (first == null) continue;
                    while (!String.IsNullOrEmpty(reader.ReadLine())) {}
                    string body = "{\"data\":[{\"id\":\"" + alias + "\"}]}";
                    bool health = first.StartsWith("GET /health ");
                    if (health) body = "{\"status\":\"" + (mode == "loading" ? "loading" : "ok") + "\"}";
                    byte[] bytes = Encoding.UTF8.GetBytes(body);
                    string status = (health && mode == "loading") ? "503 Service Unavailable" : "200 OK";
                    string header = "HTTP/1.1 " + status + "\r\nContent-Type: application/json\r\nContent-Length: "
                        + bytes.Length + "\r\nConnection: close\r\n\r\n";
                    byte[] head = Encoding.ASCII.GetBytes(header);
                    stream.Write(head, 0, head.Length);
                    stream.Write(bytes, 0, bytes.Length);
                } catch (IOException) {}
            }
        }
    }
}
"""


@pytest.fixture(scope="module")
def windows_binary(tmp_path_factory):
    if os.name != "nt":
        return None
    root = tmp_path_factory.mktemp("model-compiler")
    source, target = root / "fixture.cs", root / "llama-server.exe"
    source.write_text(FAKE_SERVER, encoding="utf-8")
    script = root / "compile.ps1"
    script.write_text(
        "param($Source, $Target)\n$ErrorActionPreference='Stop'\n"
        "Add-Type -TypeDefinition ([IO.File]::ReadAllText($Source)) -OutputAssembly $Target -OutputType ConsoleApplication\n",
        encoding="utf-8-sig",
    )
    subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), str(source), str(target)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    return target


@pytest.fixture
def service(tmp_path, monkeypatch, windows_binary):
    # Real child process and real HTTP fixture; no model, GPU or cloud API is involved.
    root = tmp_path / "中文 [安装] & 空 格"
    server, model = installation(root)
    calls, children = [], []
    real_popen = subprocess.Popen
    if windows_binary:
        shutil.copyfile(windows_binary, server)
    else:
        script = root / "fixture.py"
        script.write_text(PYTHON_SERVER, encoding="utf-8")

    def popen(args, **kwargs):
        calls.append(args)
        actual = args if windows_binary else [sys.executable, "-u", str(script), *args[1:]]
        process = real_popen(actual, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(local.subprocess, "Popen", popen)
    manager = local.LocalModelService()
    yield manager, server, model, tmp_path / "logs", calls
    manager.close()
    for child in children:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)


def test_real_start_ready_literal_arguments_repeat_stop_and_logs(service):
    manager, server, model, logs, calls = service
    assert manager.start(server, model, [logs], timeout=10) == local.MODEL_ALIAS
    process = manager.process
    assert manager.owned and manager.check()[0] == "ready"
    assert calls == [
        [
            server,
            "-m",
            model,
            "-ngl",
            "999",
            "-c",
            "8192",
            "--host",
            "127.0.0.1",
            "--port",
            "8080",
            "--alias",
            local.MODEL_ALIAS,
        ]
    ]
    assert manager.start(server, model, [logs], timeout=10) == local.MODEL_ALIAS
    assert len(calls) == 1
    manager.stop()
    manager.stop()
    assert process.poll() is not None and not manager.owned
    assert manager.check()[0] == "stopped"
    assert "服务已停止" in (manager.log_directory / "manager.log").read_text(encoding="utf-8")


def test_external_ready_service_is_reused_and_never_stopped(service):
    manager, server, model, logs, calls = service
    manager.start(server, model, [logs], timeout=10)
    other = local.LocalModelService()
    assert other.start("missing", "missing", [logs]) == local.MODEL_ALIAS
    assert other.reused and not other.owned and len(calls) == 1
    other.stop()
    other.close()
    assert manager.owned and manager.ready_model() == local.MODEL_ALIAS


@pytest.mark.parametrize("name", ["Index-Translate-9B.Q6_K", "Other-Translator"])
def test_selected_gguf_uses_its_own_alias_and_reports_ready(service, name):
    manager, server, model, logs, calls = service
    selected = Path(model).with_name(name + ".gguf")
    selected.write_bytes(b"GGUFfixture")
    assert manager.start(server, str(selected), [logs], timeout=10) == name
    assert calls[0][-2:] == ["--alias", name]
    assert manager.check() == ("ready", "本软件管理：" + name)


def test_external_hy_is_not_silently_reused_for_selected_index(service):
    manager, server, model, logs, calls = service
    manager.start(server, model, [logs], timeout=10)
    selected = Path(model).with_name("Index-Translate-9B.Q6_K.gguf")
    selected.write_bytes(b"GGUFfixture")
    other = local.LocalModelService()
    with pytest.raises(RuntimeError, match="先停止已有服务"):
        other.start(server, str(selected), [logs])
    other.close()
    assert manager.owned and manager.ready_model() == local.MODEL_ALIAS


def test_occupied_port_is_not_killed(service):
    manager, server, model, logs, calls = service
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 8080))
        listener.listen()
        with pytest.raises(RuntimeError, match="端口 8080"):
            manager.start(server, model, [logs])
        assert not calls and listener.fileno() >= 0


@pytest.mark.parametrize("mode,error", [("fail", RuntimeError), ("loading", TimeoutError)])
def test_early_exit_and_load_timeout_leave_no_child(service, monkeypatch, mode, error):
    manager, server, model, logs, calls = service
    monkeypatch.setenv("MDCX_LAUNCHER_TEST_MODE", mode)
    with pytest.raises(error):
        manager.start(server, model, [logs], timeout=5 if mode == "fail" else 1)
    assert not manager.owned and manager.process is None
    if mode == "fail":
        assert "MOCK_DLL_FAILURE" in (manager.log_directory / "server-stderr.log").read_text()


def test_shutdown_during_load_cancels_and_closes_owned_child(service, monkeypatch):
    manager, server, model, logs, calls = service
    monkeypatch.setenv("MDCX_LAUNCHER_TEST_MODE", "loading")
    errors = []

    def run():
        try:
            manager.start(server, model, [logs], timeout=10)
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=run)
    worker.start()
    deadline = time.monotonic() + 5
    while not manager.owned and time.monotonic() < deadline:
        time.sleep(0.02)
    assert manager.owned
    manager.close()
    worker.join(timeout=5)
    assert not worker.is_alive() and not manager.owned and errors
    manager.cancel.clear()
    with pytest.raises(InterruptedError):
        manager.start(server, model, [logs])


def test_abnormal_exit_is_reported_and_invalid_paths_are_readable(service):
    manager, server, model, logs, calls = service
    with pytest.raises(ValueError, match="服务程序"):
        manager.start("missing", model, [logs])
    with pytest.raises(ValueError, match="模型"):
        manager.start(server, "missing", [logs])
    manager.start(server, model, [logs], timeout=10)
    manager.process.kill()
    manager.process.wait(timeout=5)
    state, message = manager.check()
    assert state == "failed" and "异常退出" in message
    assert manager.process is None and not manager.owned


def test_rescan_switches_directory_and_clears_when_empty(tmp_path):
    dir_a = tmp_path / "dir_a"
    server_a, model_a = installation(dir_a, "model_a.gguf")
    dir_b = tmp_path / "dir_b"
    server_b, model_b = installation(dir_b, "model_b.gguf")
    dir_empty = tmp_path / "dir_empty"
    dir_empty.mkdir()

    # 1. 先查 A
    res_a = local.discover([str(dir_a)])
    assert res_a.servers == [server_a]
    assert res_a.models == [model_a]

    # 2. 改成 B 后重新查找，即使传入 A 旧路径，结果也全部来自 B
    res_b = local.discover([str(dir_b)], server_a, model_a, force=True)
    assert res_b.servers == [server_b]
    assert res_b.models == [model_b]
    assert server_a not in res_b.servers
    assert model_a not in res_b.models

    # 3. B 为空时结果为空
    res_empty = local.discover([str(dir_empty)], server_b, model_b, force=True)
    assert res_empty.servers == []
    assert res_empty.models == []


def test_controller_rescan_clears_old_paths_and_handles_empty(tmp_path):
    from types import SimpleNamespace

    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout

    from mdcx.controllers.main_window.local_model_settings import (
        LocalModelController,
        setup_local_model_controls,
    )

    _app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window.Ui = SimpleNamespace()
    container = QVBoxLayout()
    setup_local_model_controls(window, container)
    controller = LocalModelController(window)

    dir_a = tmp_path / "dir_a"
    server_a, model_a = installation(dir_a, "model_a.gguf")
    dir_b = tmp_path / "dir_b"
    server_b, model_b = installation(dir_b, "model_b.gguf")
    dir_empty = tmp_path / "dir_empty"
    dir_empty.mkdir()

    # 初始查 A 得到结果并反映在下拉框
    controller._finished("find", local.Installation([server_a], [model_a]))
    assert controller.ui.comboBox_hymt2_server.currentText() == server_a
    assert controller.ui.comboBox_hymt2_model.currentText() == model_a

    # 改成 B 后重新查找，两栏路径和候选全部切换为 B
    res_b = local.discover([str(dir_b)], server_a, model_a, force=True)
    controller._finished("find", res_b)
    assert controller.ui.comboBox_hymt2_server.currentText() == server_b
    assert controller.ui.comboBox_hymt2_model.currentText() == model_b

    # 改成空目录重新查找，清空两栏并给出提示，不保留旧路径
    res_empty = local.discover([str(dir_empty)], server_b, model_b, force=True)
    controller._finished("find", res_empty)
    assert controller.ui.comboBox_hymt2_server.currentText() == ""
    assert controller.ui.comboBox_hymt2_model.currentText() == ""
    assert controller.ui.comboBox_hymt2_server.count() == 0
    assert controller.ui.comboBox_hymt2_model.count() == 0
    assert "未在当前目录下找到服务程序或模型文件；已清空路径" in controller.ui.label_hymt2_status.text()

    controller.shutdown()
