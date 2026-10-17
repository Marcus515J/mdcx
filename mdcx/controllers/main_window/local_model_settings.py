import re
import threading
from pathlib import Path

from PyQt6.QtCore import QDir, QObject, QStandardPaths, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QWidget,
)

from mdcx.config.manager import manager
from mdcx.local_model import LOCAL_URL, LocalModelService, discover, model_alias
from mdcx.signals import signal_qt

from .settings_layout import setting_row


def setup_local_model_controls(window, layout):
    ui = window.Ui
    panel = QWidget()
    panel.setObjectName("localModelSettings")
    grid = QGridLayout(panel)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(8)
    grid.setColumnStretch(1, 1)
    title = QLabel("本机模型管理（备用，默认 Hy-MT2）")
    grid.addWidget(title, 0, 0, 1, 2)
    ui.lineEdit_hymt2_root = QLineEdit()
    ui.lineEdit_hymt2_root.setPlaceholderText("大概在哪个盘，例如 H；也可输入 H D 或选择目录")
    ui.pushButton_hymt2_root = QPushButton("选择位置…")
    root_row = QHBoxLayout()
    root_row.addWidget(ui.lineEdit_hymt2_root, 1)
    root_row.addWidget(ui.pushButton_hymt2_root)
    setting_row(grid, 1, "查找盘符 / 目录：", root_row)
    for index, kind, title in ((2, "server", "服务程序："), (3, "model", "模型文件：")):
        combo = QComboBox()
        combo.setEditable(True)
        combo.setMinimumWidth(0)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(10)
        button = QPushButton("浏览…")
        setattr(ui, f"comboBox_hymt2_{kind}", combo)
        setattr(ui, f"pushButton_hymt2_{kind}", button)
        combo.setObjectName(f"comboBox_hymt2_{kind}")
        row = QHBoxLayout()
        row.addWidget(combo, 1)
        row.addWidget(button)
        setting_row(grid, index, title, row)
    actions = QHBoxLayout()
    for name, title in (
        ("find", "查找 / 验证路径"),
        ("rescan", "重新查找"),
        ("start", "启动备用模型"),
        ("stop", "停止"),
        ("logs", "打开日志"),
    ):
        button = QPushButton(title)
        button.setObjectName(f"pushButton_hymt2_{name}")
        setattr(ui, f"pushButton_hymt2_{name}", button)
        actions.addWidget(button)
    grid.addLayout(actions, 4, 0, 1, 2)
    ui.progressBar_hymt2 = QProgressBar()
    ui.progressBar_hymt2.setRange(0, 0)
    ui.progressBar_hymt2.setFixedHeight(6)
    ui.progressBar_hymt2.setTextVisible(False)
    ui.progressBar_hymt2.hide()
    grid.addWidget(ui.progressBar_hymt2, 5, 0, 1, 2)
    ui.label_hymt2_status = QLabel("未启动；云端主模型仍为主接口。")
    ui.label_hymt2_status.setTextFormat(Qt.TextFormat.PlainText)
    ui.label_hymt2_status.setWordWrap(True)
    grid.addWidget(ui.label_hymt2_status, 6, 0, 1, 2)
    note = QLabel(
        "首次选择盘符后查找；多份安装可从列表选择，路径随底部“保存”记忆。\n"
        "查找列出有效 GGUF，默认优先 Hy-MT2；切换模型前请先停止正在运行的服务。\n"
        "启动成功只填写备用接口，请保存后刮削。外部服务仅复用；本软件启动的服务会在退出时停止。"
    )
    note.setWordWrap(True)
    grid.addWidget(note, 7, 0, 1, 2)
    layout.addWidget(panel)


def search_roots(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    tokens = re.split(r"[,，;；\s]+", text)
    if all(re.fullmatch(r"[A-Za-z]:?[\\/]?", token) for token in tokens):
        return [token[0].upper() + ":\\" for token in tokens]
    # A browsed directory may contain spaces or brackets; never split it.
    return [text]


def display_path(path: str) -> str:
    return QDir.toNativeSeparators(path)


class LocalModelController(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str, object, int)

    def __init__(self, window):
        super().__init__(window)
        self.window, self.ui = window, window.Ui
        self.service = LocalModelService()
        self.busy = ""
        self.checking = False
        self.operation_generation = 0
        self.closed = False
        self.config_generation = 0
        self.scraping = False
        self.discovery_cancel = threading.Event()
        self.progress.connect(self.ui.label_hymt2_status.setText)
        self.finished.connect(self._finished)
        for name, callback in (
            ("find", lambda: self.find()),
            ("rescan", lambda: self.find(force=True)),
            ("start", self.start),
            ("stop", self.stop),
            ("logs", self.open_logs),
        ):
            getattr(self.ui, f"pushButton_hymt2_{name}").clicked.connect(callback)
        self.ui.pushButton_hymt2_root.clicked.connect(self.browse_root)
        self.ui.pushButton_hymt2_server.clicked.connect(lambda: self.browse("server"))
        self.ui.pushButton_hymt2_model.clicked.connect(lambda: self.browse("model"))
        for control in (
            self.ui.lineEdit_hymt2_root,
            self.ui.comboBox_hymt2_server.lineEdit(),
            self.ui.comboBox_hymt2_model.lineEdit(),
        ):
            control.editingFinished.connect(lambda field=control: field.setText(display_path(field.text())))
        signal_qt.change_buttons_status.connect(self._scrape_started)
        signal_qt.reset_buttons_status.connect(self._scrape_finished)
        self.timer = QTimer(self)
        self.timer.setInterval(3000)
        self.timer.timeout.connect(self.check)
        self.timer.start()
        self.refresh_buttons()

    def _scrape_started(self):
        self.scraping = True
        self.refresh_buttons()

    def _scrape_finished(self):
        self.scraping = False
        self.refresh_buttons()

    def refresh_buttons(self):
        running = self.service.owned or bool(self.service.model_id)
        for name in ("find", "rescan", "start", "root", "server", "model"):
            getattr(self.ui, f"pushButton_hymt2_{name}").setEnabled(not self.busy and (name != "start" or not running))
        for control in (self.ui.lineEdit_hymt2_root, self.ui.comboBox_hymt2_server, self.ui.comboBox_hymt2_model):
            control.setEnabled(not self.busy)
        self.ui.pushButton_hymt2_stop.setText("取消" if self.busy in ("find", "start") else "停止")
        self.ui.pushButton_hymt2_stop.setEnabled(
            not self.scraping and (self.busy in ("find", "start") or (not self.busy and self.service.owned))
        )
        self.ui.pushButton_hymt2_stop.setToolTip(
            "刮削期间不能停止模型，请先结束刮削。" if self.scraping else "只停止本软件启动的服务。"
        )
        self.ui.pushButton_hymt2_logs.setEnabled(self.service.log_directory is not None)
        self.ui.progressBar_hymt2.setVisible(self.busy in ("find", "start", "stop"))

    def _work(self, operation, function):
        if self.busy or self.closed:
            return
        self.busy = operation
        self.operation_generation += 1
        generation = self.config_generation
        self.refresh_buttons()

        def run():
            try:
                value = function()
            except Exception as exc:
                value = exc
            if not self.closed:
                self.finished.emit(operation, value, generation)

        threading.Thread(target=run, name="HyMT2-" + operation, daemon=True).start()

    def find(self, force=False):
        if self.busy:
            return
        self.discovery_cancel.clear()
        roots = search_roots(self.ui.lineEdit_hymt2_root.text())
        server, model = self.paths()
        excluded = (manager.config.garbage_directory,)
        self._work(
            "find",
            lambda: discover(
                roots,
                server,
                model,
                force=force,
                cancel=self.discovery_cancel,
                progress=self.progress.emit,
                excluded=excluded,
            ),
        )

    def paths(self):
        return self.ui.comboBox_hymt2_server.currentText().strip(), self.ui.comboBox_hymt2_model.currentText().strip()

    def start(self):
        if self.busy:
            return
        self.service.cancel.clear()
        server, model = self.paths()
        parents = [manager.path.parent / "logs" / "hymt2"]
        fallback = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        if fallback:
            parents.append(Path(fallback) / "MDCx-HyMT2" / "logs")
        self.ui.label_hymt2_status.setText("正在检查本机服务并加载备用模型……")
        self._work("start", lambda: self.service.start(server, model, parents, self.progress.emit))

    def stop(self):
        if self.scraping:
            return
        if self.busy in ("find", "start"):
            self.discovery_cancel.set()
            self.service.cancel.set()
            self.ui.label_hymt2_status.setText("正在取消，请稍候……")
            self.ui.pushButton_hymt2_stop.setEnabled(False)
        elif not self.busy and self.service.owned:
            self.ui.label_hymt2_status.setText("正在停止本软件启动的服务……")
            self._work("stop", self.service.stop)

    def check(self):
        if self.busy or self.closed or self.checking:
            return
        # Polling observes the endpoint without locking controls or mutating service
        # state. An intervening user operation makes this observation obsolete.
        self.checking = True
        generation = self.operation_generation

        def run():
            try:
                value = self.service.ready_model()
            except Exception as exc:
                value = exc
            if not self.closed:
                self.finished.emit("check", value, generation)

        threading.Thread(target=run, name="HyMT2-check", daemon=True).start()

    def _finished(self, operation, value, generation=None):
        if self.closed:
            return
        if operation == "check":
            self.checking = False
            if self.busy or generation != self.operation_generation:
                return
            if not isinstance(value, Exception):
                value = self.service.check(ready=value)
        else:
            self.busy = ""
        if generation is not None and generation != self.config_generation and operation in ("find", "start"):
            self.ui.label_hymt2_status.setText("操作已结束；配置已切换，未覆盖当前路径或备用设置。可手动填写本机备用。")
            self.refresh_buttons()
            return
        if isinstance(value, Exception):
            self.ui.label_hymt2_status.setText(str(value))
        elif operation == "find":
            for kind, candidates in (("server", value.servers), ("model", value.models)):
                combo = getattr(self.ui, f"comboBox_hymt2_{kind}")
                previous = display_path(combo.currentText())
                candidates = [display_path(path) for path in candidates]
                if value.cached:
                    candidates = list(
                        dict.fromkeys([display_path(combo.itemText(i)) for i in range(combo.count())] + candidates)
                    )
                combo.clear()
                combo.addItems(candidates)
                if previous in candidates:
                    combo.setCurrentText(previous)
            self.ui.label_hymt2_status.setText(
                "已验证选中路径；保留已知候选，重新查找可更新完整模型列表。"
                if value.cached
                else f"找到程序 {len(value.servers)} 个、模型 {len(value.models)} 个；请从列表选择，缺失时可浏览补充。"
            )
        elif operation == "start":
            self.apply_fallback(value)
            owner = "本软件管理" if self.service.owned else "复用外部服务，不在此停止"
            self.ui.label_hymt2_status.setText(f"已就绪（{owner}）：{value}。请在页面底部保存备用设置。")
        elif operation == "stop":
            self.ui.label_hymt2_status.setText("已停止并释放本软件模型；云端主模型仍为主接口。")
        elif operation == "check":
            state, message = value
            # Keep discovery/errors/save reminders visible while a stopped service stays stopped.
            if state != "stopped" or self.ui.label_hymt2_status.text().startswith(("本软件管理", "外部服务")):
                self.ui.label_hymt2_status.setText(message)
        self.refresh_buttons()

    def apply_fallback(self, model_id=None):
        # All other cloud, prompt, temperature, retry and translator settings stay untouched.
        self.ui.lineEdit_llm_fallback_url.setText(LOCAL_URL)
        self.ui.lineEdit_llm_fallback_model.setText(
            model_id or self.service.model_id or model_alias(self.ui.comboBox_hymt2_model.currentText().strip())
        )
        self.ui.lineEdit_llm_fallback_key.clear()

    def browse_root(self):
        path = QFileDialog.getExistingDirectory(
            self.window, "选择大概安装模型的盘或目录", self.ui.lineEdit_hymt2_root.text()
        )
        if path:
            self.ui.lineEdit_hymt2_root.setText(display_path(path))

    def browse(self, kind):
        filter_text = "llama-server.exe (llama-server.exe)" if kind == "server" else "GGUF 模型 (*.gguf)"
        path, _ = QFileDialog.getOpenFileName(
            self.window, "选择服务程序" if kind == "server" else "选择 GGUF 模型", "", filter_text
        )
        if path:
            path = display_path(path)
            combo = getattr(self.ui, f"comboBox_hymt2_{kind}")
            if combo.findText(path) < 0:
                combo.addItem(path)
            combo.setCurrentText(path)

    def open_logs(self):
        if self.service.log_directory:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.service.log_directory)))

    def shutdown(self):
        self.closed = True
        self.timer.stop()
        self.discovery_cancel.set()
        self.service.close()
