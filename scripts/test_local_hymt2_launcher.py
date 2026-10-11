"""Windows-only integration checks using a temporary, executable HTTP fixture.

No model, GPU, personal configuration, project dependencies or cloud API is used.
The launcher itself runs under Windows PowerShell 5.1, including its CMD entry.
"""

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
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


def available_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


@unittest.skipUnless(os.name == "nt", "requires Windows PowerShell 5.1")
class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="MDCx launcher compiler ")
        root = Path(cls.build.name)
        source = root / "server.cs"
        source.write_text(FAKE_SERVER, encoding="utf-8")
        cls.binary = root / "llama-server.exe"
        compile_script = root / "compile.ps1"
        compile_script.write_text(
            "param($Source, $Target)\n$ErrorActionPreference = 'Stop'\n"
            "if ($PSVersionTable.PSVersion.Major -ne 5) { throw 'Requires PS 5.1' }\n"
            "Add-Type -TypeDefinition ([IO.File]::ReadAllText($Source)) "
            "-OutputAssembly $Target -OutputType ConsoleApplication\n",
            encoding="utf-8-sig",
        )
        subprocess.run(
            [
                str(POWERSHELL),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(compile_script),
                str(source),
                str(cls.binary),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="MDCx 中文 [测试] & 空格 ")
        self.base = Path(self.temp.name)
        self.root = self.base / "扫描位置"
        self.root.mkdir()
        self.logs = self.base / "测试日志"
        self.record = self.base / "args.txt"
        self.port = available_port()
        self.env = dict(os.environ, MDCX_LAUNCHER_TEST_RECORD=str(self.record))
        self.external = []

    def tearDown(self):
        for process in self.external:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
        # Clean up only fixture processes if an assertion exposed a launcher leak.
        pid_file = Path(str(self.record) + ".pid")
        if pid_file.exists():
            subprocess.run(["taskkill", "/PID", pid_file.read_text(), "/F"], capture_output=True, timeout=10)
        self.temp.cleanup()

    def installation(self, record=True, relative=False, model_name="HY-MT2-7B-Q8_0.gguf"):
        install = self.root / "海南鸡 [安装] & 空格"
        server = install / "stage2-runtime" / "llama.cpp" / "llama-server.exe"
        server.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.binary, server)
        model = install / "stage2-runtime" / "models" / model_name
        model.parent.mkdir(exist_ok=True)
        model.write_bytes(b"GGUF\x03\x00\x00\x00mock")
        if record:
            (install / "stage2_runtime.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "llama_server_path": str(server.relative_to(install) if relative else server),
                        "model_path": str(model.relative_to(install) if relative else model),
                    }
                ),
                encoding="utf-8-sig",
            )
        return server, model

    def run_launcher(self, extra=(), stdin=None, mode="ready", wrapper=None):
        arguments = [
            "-SearchRoot",
            str(self.root),
            "-LogRoot",
            str(self.logs),
            "-Port",
            str(self.port),
            "-StartupTimeoutSeconds",
            "4",
        ]
        if stdin is None:
            arguments += ["-NonInteractive"]
        arguments += list(extra)
        if wrapper:
            command = ["cmd.exe", "/d", "/c", "call", str(wrapper), *arguments]
        else:
            command = [
                str(POWERSHELL),
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPTS / "start-local-hymt2.ps1"),
                *arguments,
            ]
        result = subprocess.run(
            command,
            input=stdin,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=40,
            env=dict(self.env, MDCX_LAUNCHER_TEST_MODE=mode),
        )
        self.output = result.stdout + result.stderr
        print(self.output, end="")
        return result

    def assert_stopped(self):
        with socket.socket() as client:
            client.settimeout(1)
            self.assertNotEqual(client.connect_ex(("127.0.0.1", self.port)), 0)
        pid = Path(str(self.record) + ".pid").read_text()
        check = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, timeout=10)
        self.assertNotIn("llama-server.exe", check.stdout)

    def start_external(self, alias):
        process = subprocess.Popen(
            [str(self.binary), "--port", str(self.port), "--alias", alias],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.external.append(process)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with socket.socket() as client:
                if client.connect_ex(("127.0.0.1", self.port)) == 0:
                    return process
            time.sleep(0.05)
        self.fail("fixture did not start")

    def test_install_record_and_quoted_paths(self):
        _, model = self.installation(model_name="已安装的翻译模型.gguf")
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, self.output)
        self.assertIn("找到海南鸡安装记录", self.output)
        args = self.record.read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            args,
            [
                "-m",
                str(model.resolve()),
                "-ngl",
                "999",
                "-c",
                "8192",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--alias",
                "HY-MT2-7B-Q8_0",
            ],
        )
        self.assert_stopped()

    def test_launcher_has_windows_powershell_utf8_bom(self):
        self.assertTrue((SCRIPTS / "start-local-hymt2.ps1").read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertFalse((SCRIPTS / "Start-HyMT2.cmd").read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_relative_install_record(self):
        self.installation(relative=True)
        self.assertEqual(self.run_launcher().returncode, 0, self.output)
        self.assert_stopped()

    def test_missing_record_fallback_and_multiple_models(self):
        _, model = self.installation(record=False)
        (model.parent / "HY-MT2-7B-Q4_K_M.gguf").write_bytes(b"GGUFmock")
        self.assertEqual(self.run_launcher().returncode, 0, self.output)
        self.assertIn(str(model.resolve()), self.record.read_text(encoding="utf-8"))
        self.assert_stopped()

    def test_stale_record_falls_back(self):
        server, _ = self.installation()
        (server.parent.parent.parent / "stage2_runtime.json").write_text(
            '{"llama_server_path":"missing.exe","model_path":"missing.gguf"}', encoding="utf-8"
        )
        self.assertEqual(self.run_launcher().returncode, 0, self.output)
        self.assertIn("文件已失效", self.output)
        self.assert_stopped()

    def test_broken_record_falls_back(self):
        server, _ = self.installation()
        (server.parent.parent.parent / "stage2_runtime.json").write_text("{broken", encoding="utf-8")
        self.assertEqual(self.run_launcher().returncode, 0, self.output)
        self.assertIn("无法读取", self.output)
        self.assert_stopped()

    def test_missing_runtime_reports_error_with_log(self):
        server, _ = self.installation(record=False)
        server.unlink()
        self.assertEqual(self.run_launcher().returncode, 1, self.output)
        self.assertIn("llama-server.exe 共 0 个", self.output)
        log = next(self.logs.glob("*/launcher.log")).read_text(encoding="utf-8")
        self.assertIn("启动失败", log)

    def test_invalid_model_header(self):
        _, model = self.installation(record=False)
        model.write_text("not a model")
        self.assertEqual(self.run_launcher().returncode, 1, self.output)
        self.assertIn("Hy-MT2 GGUF 共 0 个", self.output)

    def test_server_error_is_visible_and_logged(self):
        self.installation()
        self.assertEqual(self.run_launcher(mode="fail").returncode, 1, self.output)
        self.assertIn("42", self.output)
        self.assertIn("MOCK_DLL_FAILURE", self.output)
        self.assertIn("MOCK_DLL_FAILURE", next(self.logs.glob("*/server-stderr.log")).read_text())
        self.assert_stopped()

    def test_loading_timeout_cleans_up_owned_process(self):
        self.installation()
        self.assertEqual(self.run_launcher(mode="hang").returncode, 1, self.output)
        self.assertIn("等待模型加载超时", self.output)
        self.assert_stopped()

    def test_models_listed_but_weights_loading_does_not_claim_ready(self):
        self.installation()
        self.assertEqual(self.run_launcher(mode="loading").returncode, 1, self.output)
        self.assertIn("等待模型加载超时", self.output)
        self.assertNotIn("服务已就绪", self.output)
        self.assert_stopped()

    def test_ready_existing_service_reused_without_stopping(self):
        process = self.start_external("HY-MT2-other")
        self.assertEqual(self.run_launcher().returncode, 0, self.output)
        self.assertIn("直接使用", self.output)
        self.assertIn("HY-MT2-other", self.output)
        self.assertIn("先点击", self.output)
        self.assertIn("再将主模型名改为：HY-MT2-other", self.output)
        self.assertLess(self.output.index("先点击"), self.output.index("再将主模型名改为"))
        self.assertIsNone(process.poll())
        self.assertFalse(self.record.exists())

    def test_existing_service_with_model_path_as_id(self):
        process = self.start_external("C:/models/HY-MT2-7B-Q8_0.gguf")
        self.assertEqual(self.run_launcher().returncode, 0, self.output)
        self.assertIn("C:/models/HY-MT2-7B-Q8_0.gguf", self.output)
        self.assertIn("再将主模型名改为：C:/models/HY-MT2-7B-Q8_0.gguf", self.output)
        self.assertIsNone(process.poll())
        self.assertFalse(self.record.exists())

    def test_existing_service_with_default_alias_needs_only_preset(self):
        process = self.start_external("HY-MT2-7B-Q8_0")
        self.assertEqual(self.run_launcher().returncode, 0, self.output)
        self.assertIn("本机 Hy-MT2 预设", self.output)
        self.assertNotIn("再将主模型名改为", self.output)
        self.assertIsNone(process.poll())
        self.assertFalse(self.record.exists())

    def test_conflicting_service_is_not_stopped(self):
        process = self.start_external("unrelated-model")
        self.assertEqual(self.run_launcher().returncode, 1, self.output)
        self.assertIn("已被占用", self.output)
        self.assertIsNone(process.poll())
        self.assertFalse(self.record.exists())

    def test_local_health_check_ignores_environment_proxy(self):
        self.installation()
        self.env.update(
            HTTP_PROXY="http://127.0.0.1:1",
            HTTPS_PROXY="http://127.0.0.1:1",
            ALL_PROXY="http://127.0.0.1:1",
            NO_PROXY="",
        )
        self.assertEqual(self.run_launcher().returncode, 0, self.output)
        self.assert_stopped()

    def test_skips_junction_and_discard_directory(self):
        original = self.root
        self.root = self.base / "outside scan"
        self.root.mkdir()
        self.installation()
        self.root = original
        subprocess.run(
            ["cmd", "/d", "/c", "mklink", "/J", str(self.root / "junction"), str(self.base / "outside scan")],
            check=True,
            capture_output=True,
        )
        discard = self.root / "_待删"
        shutil.copytree(self.base / "outside scan", discard)
        try:
            self.assertEqual(self.run_launcher().returncode, 1, self.output)
            self.assertIn("llama-server.exe 共 0 个", self.output)
        finally:
            os.rmdir(self.root / "junction")

    def test_cmd_entry_and_enter_to_stop(self):
        self.installation()
        result = self.run_launcher(stdin="\n\n", wrapper=SCRIPTS / "Start-HyMT2.cmd")
        self.assertEqual(result.returncode, 0, self.output)
        self.assertIn("本窗口会保留", self.output)
        self.assert_stopped()

    def test_cmd_pause_survives_powershell_parse_error(self):
        wrapper = self.base / "Start-HyMT2.cmd"
        shutil.copyfile(SCRIPTS / wrapper.name, wrapper)
        (self.base / "start-local-hymt2.ps1").write_text("param( BROKEN", encoding="utf-8-sig")
        result = self.run_launcher(stdin="\n", wrapper=wrapper)
        self.assertNotEqual(result.returncode, 0, self.output)
        self.assertIn("本窗口会保留", self.output)

    def test_cmd_reports_missing_script_and_pauses(self):
        wrapper = self.base / "Start-HyMT2.cmd"
        shutil.copyfile(SCRIPTS / wrapper.name, wrapper)
        self.assertEqual(self.run_launcher(stdin="\n", wrapper=wrapper).returncode, 1, self.output)
        self.assertIn("找不到启动脚本", self.output)
        self.assertIn("本窗口会保留", self.output)

    def test_direct_powershell_error_waits_for_enter(self):
        self.assertEqual(self.run_launcher(stdin="\n").returncode, 1, self.output)
        self.assertIn("按回车关闭窗口", self.output)

    def test_drive_only_prompt_through_cmd(self):
        self.installation()
        for name in ["Start-HyMT2.cmd", "start-local-hymt2.ps1"]:
            shutil.copyfile(SCRIPTS / name, self.base / name)
        drive = next(letter + ":" for letter in "ZYXWVUTSR" if not Path(letter + ":/").exists())
        subprocess.run(["subst", drive, str(self.root)], check=True, capture_output=True)
        try:
            command = [
                "cmd.exe",
                "/d",
                "/c",
                "call",
                str(self.base / "Start-HyMT2.cmd"),
                "-LogRoot",
                str(self.logs),
                "-Port",
                str(self.port),
                "-StartupTimeoutSeconds",
                "4",
            ]
            result = subprocess.run(
                command,
                input="invalid\n" + drive + "\n\n\n",
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=40,
                env=self.env,
            )
            self.output = result.stdout + result.stderr
            print(self.output, end="")
            self.assertEqual(result.returncode, 0, self.output)
            self.assertIn("请输入存在的盘符", self.output)
            self.assertIn("服务已就绪", self.output)
            self.assert_stopped()
        finally:
            subprocess.run(["subst", drive, "/d"], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
