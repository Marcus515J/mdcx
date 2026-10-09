from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from mdcx.config.manager import manager
from mdcx.config.models import Config


class GarbageSettingsDialog(QDialog):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("垃圾处理设置")
        self.resize(600, 560)
        layout = QVBoxLayout(self)
        help_text = QLabel(
            "无需先成功刮削：扫描时识别垃圾视频，整轮结束后处理纯垃圾目录。\n"
            "只有识别不出番号，并命中关键词、域名或大小规则的视频才会被处理。"
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        self.enabled = QCheckBox("启用自动垃圾处理")
        self.enabled.setChecked(config.garbage_enabled)
        layout.addWidget(self.enabled)
        self.dry_run = QCheckBox("演练模式：只记录日志，不移动或删除垃圾")
        self.dry_run.setChecked(config.garbage_dry_run)
        layout.addWidget(self.dry_run)
        self.mode_label = QLabel()
        self.mode_label.setWordWrap(True)
        layout.addWidget(self.mode_label)
        self.enabled.toggled.connect(self._refresh_mode)
        self.dry_run.toggled.connect(self._refresh_mode)
        self._refresh_mode()

        form = QFormLayout()
        self.keywords = QPlainTextEdit("\n".join(config.garbage_keywords))
        self.keywords.setPlaceholderText("每行一个关键词，可直接增删；匹配时自动去掉空白")
        self.keywords.setMinimumHeight(140)
        form.addRow("黑名单关键词（每行一项）", self.keywords)
        self.domain_rule = QCheckBox("文件名去空白后含 .com / .net / .cc / www.")
        self.domain_rule.setChecked(config.garbage_domain_rule)
        form.addRow("域名样式规则", self.domain_rule)
        self.size = QDoubleSpinBox()
        self.size.setRange(0, 999999999)
        self.size.setDecimals(2)
        self.size.setSuffix(" MB")
        self.size.setValue(config.file_size)
        self.size.setToolTip("与原有最小文件大小设置共用同一个值；正常番号不会被垃圾规则处理")
        form.addRow("大小下限 N", self.size)
        self.action = QComboBox()
        self.action.addItems(["移到 _待删（可恢复）", "永久删除垃圾文件（无法恢复）"])
        self.action.setCurrentIndex(int(config.garbage_permanent_delete))
        form.addRow("单文件处理方式", self.action)
        self.directory = QLineEdit(config.garbage_directory)
        self.directory.setPlaceholderText("留空使用源文件盘符根目录下的 _待删")
        select_button = QPushButton("选择目录…")
        select_button.clicked.connect(self._select_directory)
        directory_row = QHBoxLayout()
        directory_row.addWidget(self.directory)
        directory_row.addWidget(select_button)
        form.addRow("待删目录", directory_row)
        layout.addLayout(form)
        footer = QLabel(
            "纯垃圾目录始终整体移到待删目录。NFO、图片、字幕和未知文件会阻止整目录移动。\n"
            "其他垃圾文件的扩展名、文件名及包含词，请在当前页原有清理规则中编辑。"
        )
        footer.setWordWrap(True)
        layout.addWidget(footer)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存并生效")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_mode(self):
        if not self.enabled.isChecked():
            self.mode_label.setText("当前状态：未启用垃圾处理。")
        elif self.dry_run.isChecked():
            self.mode_label.setText("当前状态：演练。命中文件会跳过搜索，垃圾文件和目录保持原位。")
        else:
            self.mode_label.setText("当前状态：真实处理。命中的垃圾将按所选方式处理。")

    def _select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "选择待删目录", self.directory.text())
        if directory:
            self.directory.setText(directory)

    def apply_to_config(self, config: Config):
        config.garbage_enabled = self.enabled.isChecked()
        config.garbage_dry_run = self.dry_run.isChecked()
        config.garbage_keywords = list(
            dict.fromkeys(word.strip() for word in self.keywords.toPlainText().splitlines() if word.strip())
        )
        config.garbage_domain_rule = self.domain_rule.isChecked()
        config.file_size = self.size.value()
        config.garbage_permanent_delete = self.action.currentIndex() == 1
        config.garbage_directory = self.directory.text().strip()


def setup_garbage_settings_ui(window):
    button = QPushButton("垃圾处理设置…", window.Ui.groupBox_61)
    button.setObjectName("pushButton_garbage_settings")
    button.setGeometry(535, 478, 145, 30)
    button.setToolTip("增删垃圾关键词、调整阈值、演练与真实处理")
    button.clicked.connect(lambda: open_garbage_settings(window))
    window.Ui.pushButton_garbage_settings = button


def open_garbage_settings(window):
    dialog = GarbageSettingsDialog(manager.config, window)
    # Include any size change that is still pending in the main settings page.
    try:
        dialog.size.setValue(float(window.Ui.lineEdit_escape_size.text()))
    except ValueError:
        pass
    if dialog.exec() == QDialog.DialogCode.Accepted:
        dialog.apply_to_config(manager.config)
        window.Ui.lineEdit_escape_size.setText(str(manager.config.file_size))
        window.pushButton_save_config_clicked()
