"""Discovery and ownership of an existing local llama.cpp translation service.

Blocking operations belong on a worker, never on the Qt thread. No installation,
download, private configuration inspection or unowned process termination.
"""

import json
import os
import re
import socket
import stat
import subprocess
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

MODEL_ALIAS = "HY-MT2-7B-Q8_0"
LOCAL_URL = "http://127.0.0.1:8080/v1"
SKIP_DIRECTORIES = {"$recycle.bin", "system volume information", "windows", "_待删"}


def model_alias(path: str) -> str:
    return Path(path.replace("\\", "/")).stem if path else MODEL_ALIAS


def model_family(name: str) -> str:
    if re.search(r"hy[-_]?mt2", name, re.I):
        return "hy-mt2"
    if re.search(r"index[-_]?translate", name, re.I):
        return "index-translate"
    return name.casefold()


def valid_file(path: str | Path, kind: str) -> bool:
    path = Path(path)
    try:
        if path.is_symlink() or path.is_junction() or not path.is_file():
            return False
        if kind == "server":
            if path.name.lower() != "llama-server.exe":
                return False
            header = b"MZ"
        else:
            if path.suffix.lower() != ".gguf":
                return False
            header = b"GGUF"
        with path.open("rb") as stream:
            return stream.read(len(header)) == header
    except OSError:
        return False


@dataclass
class Installation:
    servers: list[str]
    models: list[str]
    cached: bool = False


def discover(
    roots: list[str],
    server: str = "",
    model: str = "",
    *,
    cancel: threading.Event | None = None,
    progress: Callable[[str], None] = lambda _: None,
    force: bool = False,
    excluded: tuple[str, ...] = (),
) -> Installation:
    cancel = cancel or threading.Event()
    if not force and valid_file(server, "server") and valid_file(model, "model"):
        progress("已验证记忆的程序和模型路径，无需重新扫描。")
        return Installation([server], [model], cached=True)
    if not roots:
        raise ValueError("请选择大概安装模型的盘符，或浏览选择程序和模型。")
    queue = deque(Path(root) for root in roots)
    if any(not root.is_dir() or root.is_symlink() or root.is_junction() for root in queue):
        raise ValueError("查找位置不存在，或不是普通目录。")
    exclusions = [Path(p).absolute() for p in excluded if p]
    servers = {server} if valid_file(server, "server") else set()
    models = {model} if valid_file(model, "model") else set()
    recorded_servers, recorded_models = [], []
    visited = set()
    count, skipped, last_update = 0, 0, 0.0
    while queue:
        if cancel.is_set():
            raise InterruptedError("已取消查找。")
        directory = queue.popleft()
        key = os.path.normcase(str(directory.absolute()))
        if key in visited or any(directory.absolute().is_relative_to(p) for p in exclusions):
            continue
        visited.add(key)
        count += 1
        if time.monotonic() - last_update >= 1:
            progress(f"正在查找：已扫描 {count} 个目录，跳过 {skipped} 个无法访问的目录。")
            last_update = time.monotonic()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if cancel.is_set():
                        raise InterruptedError("已取消查找。")
                    try:
                        # Windows junctions and other reparse points must not be traversed.
                        attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
                        if entry.is_symlink() or attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024):
                            continue
                        path = Path(entry.path)
                        name = entry.name.lower()
                        if entry.is_dir(follow_symlinks=False):
                            if name not in SKIP_DIRECTORIES:
                                queue.append(path)
                        elif name == "stage2_runtime.json":
                            try:
                                if path.stat().st_size > 1024 * 1024:
                                    continue
                                record = json.loads(path.read_text(encoding="utf-8-sig"))
                                for field, kind, target in (
                                    ("llama_server_path", "server", recorded_servers),
                                    ("model_path", "model", recorded_models),
                                ):
                                    value = record.get(field)
                                    if not isinstance(value, str) or not value:
                                        continue
                                    candidate = Path(value)
                                    if not candidate.is_absolute():
                                        candidate = path.parent / candidate
                                    if valid_file(candidate, kind):
                                        target.append(str(candidate.absolute()))
                            except (OSError, ValueError, AttributeError):
                                pass
                        elif name == "llama-server.exe" and valid_file(path, "server"):
                            servers.add(str(path.absolute()))
                        elif path.suffix.lower() == ".gguf" and valid_file(path, "model"):
                            models.add(str(path.absolute()))
                    except OSError:
                        skipped += 1
        except OSError:
            skipped += 1
    # Installation records rank first; still show every candidate for explicit selection.
    servers = list(dict.fromkeys(recorded_servers + sorted(servers)))
    models = list(
        dict.fromkeys(recorded_models + sorted(models, key=lambda p: (not re.search(r"7b.*q8[_-]0", p.lower()), p)))
    )
    # Keep the established Hy-MT2 default while exposing other GGUF candidates.
    models.sort(key=lambda p: model_family(model_alias(p)) != "hy-mt2")
    progress(f"查找完成：程序 {len(servers)} 个，模型 {len(models)} 个；可浏览补充缺失文件。")
    return Installation(servers, models)


class LocalModelService:
    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.reused = False
        self.model_id = ""
        self.expected_model = ""
        self.log_directory: Path | None = None
        self.cancel = threading.Event()
        self._lock = threading.RLock()
        self._closed = False

    @property
    def owned(self) -> bool:
        with self._lock:
            return self.process is not None and self.process.poll() is None

    def ready_model(self) -> str:
        try:
            with httpx.Client(trust_env=False, follow_redirects=False, timeout=1.5) as client:
                health = client.get("http://127.0.0.1:8080/health")
                if health.status_code != 200 or health.json().get("status") != "ok":
                    return ""
                models = client.get(f"{LOCAL_URL}/models")
                if models.status_code != 200:
                    return ""
                for model in models.json().get("data", []):
                    model_id = model.get("id", "")
                    if (
                        isinstance(model_id, str)
                        and model_id
                        and (model_family(model_id) in ("hy-mt2", "index-translate") or model_id == self.expected_model)
                    ):
                        return model_id
        except (httpx.HTTPError, ValueError, AttributeError, TypeError):
            pass
        return ""

    def _log(self, message: str):
        if self.log_directory:
            try:
                with (self.log_directory / "manager.log").open("a", encoding="utf-8") as stream:
                    stream.write(time.strftime("%H:%M:%S ") + message + "\n")
            except OSError:
                pass

    def _create_logs(self, parents: list[Path]):
        for parent in parents:
            try:
                directory = parent / (time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8])
                directory.mkdir(parents=True)
                (directory / "manager.log").touch()
                self.log_directory = directory
                return
            except OSError:
                continue
        raise OSError("无法创建本机模型日志目录，请检查配置目录的写入权限。")

    def start(self, server: str, model: str, log_parents: list[Path], progress=lambda _: None, timeout=180) -> str:
        with self._lock:
            if self._closed or self.cancel.is_set():
                raise InterruptedError("已取消启动。")
            if self.owned:
                return self.model_id
            self.expected_model = model_alias(model) if valid_file(model, "model") else ""
        ready = self.ready_model()
        if self.cancel.is_set():
            raise InterruptedError("已取消启动。")
        if ready:
            if self.expected_model and model_family(ready) != model_family(self.expected_model):
                raise RuntimeError(
                    f"端口 8080 已运行 {ready}；请先停止已有服务，再启动所选模型 {self.expected_model}。"
                )
            self.reused, self.model_id = True, ready
            progress(f"复用已就绪的本机服务 {ready}；由其他程序管理。")
            return ready
        try:
            with socket.create_connection(("127.0.0.1", 8080), timeout=1):
                raise RuntimeError(
                    "端口 8080 已占用，但所选本机模型尚未就绪；请等待已有服务加载，或关闭占用程序后重试。"
                )
        except OSError:
            pass
        if not valid_file(server, "server"):
            raise ValueError("服务程序缺失或无效，请查找或浏览选择 llama-server.exe。")
        if not valid_file(model, "model"):
            raise ValueError("模型缺失或无效，请查找或浏览选择 GGUF 模型。")
        with self._lock:
            if self._closed or self.cancel.is_set():
                raise InterruptedError("已取消启动。")
            self._create_logs(log_parents)
            args = [
                str(Path(server).absolute()),
                "-m",
                str(Path(model).absolute()),
                "-ngl",
                "999",
                "-c",
                "8192",
                "--host",
                "127.0.0.1",
                "--port",
                "8080",
                "--alias",
                self.expected_model,
            ]
            self._log("启动本机备用服务。")
            with (
                (self.log_directory / "server-stdout.log").open("wb") as out,
                (self.log_directory / "server-stderr.log").open("wb") as err,
            ):
                self.process = subprocess.Popen(
                    args,
                    cwd=Path(server).absolute().parent,
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            self.reused = False
        began = time.monotonic()
        try:
            while not self.cancel.is_set():
                with self._lock:
                    if self.process is None or self.process.poll() is not None:
                        code = self.process.returncode if self.process else "已停止"
                        raise RuntimeError(f"llama-server 提前退出（{code}）；请打开日志检查显存、驱动或依赖。")
                ready = self.ready_model()
                # A process can exit while the health request is waiting. Report
                # its exit code before treating a missed deadline as load timeout.
                with self._lock:
                    if self.cancel.is_set():
                        raise InterruptedError("已取消启动。")
                    if self.process is None or self.process.poll() is not None:
                        code = self.process.returncode if self.process else "已停止"
                        raise RuntimeError(f"llama-server 提前退出（{code}）；请打开日志检查显存、驱动或依赖。")
                if ready:
                    with self._lock:
                        if self.cancel.is_set() or not self.owned:
                            raise InterruptedError("已取消启动。")
                        self.model_id = ready
                        self._log("模型就绪：" + ready)
                    return ready
                elapsed = int(time.monotonic() - began)
                if elapsed >= timeout:
                    raise TimeoutError(f"模型加载超时（{timeout} 秒）；请打开日志检查。")
                progress(f"正在加载模型，已等待 {elapsed} 秒（最多 {timeout} 秒）……")
                self.cancel.wait(0.5)
            raise InterruptedError("已取消启动。")
        except Exception as exc:
            self._log(str(exc))
            self.stop()
            raise

    def stop(self):
        """Stop only the exact child handle we own. Never kill by name or port."""
        with self._lock:
            process = self.process
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                self.process = None
                self._log("本软件启动的服务已停止。")
            self.model_id = ""
            self.expected_model = ""
            self.reused = False

    def check(self, ready: str | None = None) -> tuple[str, str]:
        """Apply a health observation; None performs a synchronous probe first."""
        with self._lock:
            if self.process is not None and self.process.poll() is not None:
                code = self.process.returncode
                self.process = None
                self.model_id = ""
                self._log(f"服务异常退出：{code}")
                return "failed", f"服务异常退出（{code}），请打开日志。"
        if ready is None:
            ready = self.ready_model()
        if ready:
            self.model_id = ready
            return "ready", ("本软件管理" if self.owned else "外部服务，不能在此停止") + "：" + ready
        if self.owned:
            return "unavailable", "本软件进程仍在运行，接口暂不可用；可停止后重试或查看日志。"
        self.reused = False
        self.model_id = ""
        return "stopped", "未启动；云端主模型仍为主接口。"

    def close(self):
        self.cancel.set()
        with self._lock:
            self._closed = True
            self.stop()
