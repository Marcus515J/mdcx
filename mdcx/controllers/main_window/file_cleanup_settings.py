from PyQt6.QtCore import QSignalBlocker
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mdcx.config.manager import manager


def setup_file_cleanup_settings(window):
    ui = window.Ui
    group = ui.groupBox_61
    added_height = 810 - group.height()
    group.resize(group.width(), 810)
    ui.groupBox_9.move(ui.groupBox_9.x(), ui.groupBox_9.y() + added_height)
    page = ui.scrollAreaWidgetContents_guaxiaomulu
    page.resize(page.width(), page.height() + added_height)
    page.setMinimumHeight(page.height())
    # The selected action describes reversibility; the former permanent-only
    # acknowledgements are no longer a second gate for dry runs and quarantine.
    ui.checkBox_i_understand_clean.hide()
    ui.checkBox_i_agree_clean.hide()
    ui.label_199.setText("启用的规则任一命中即清理；完整文件名严格相等，包含词忽略空白和大小写。")
    ui.label_199.setWordWrap(True)
    ui.label_263.setText("无番号视频大小(KB)<=：")
    ui.lineEdit_clean_file_name.setToolTip("填写完整文件名（含扩展名），多个用 | 分隔；空格与大小写必须一致")
    ui.lineEdit_clean_file_size.setToolTip("只作用于无番号视频；0 表示关闭，不会因文档很小而清理文档")

    panel = QWidget(group)
    panel.setObjectName("fileCleanupOptions")
    panel.setGeometry(20, 355, 661, 315)
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    form = QFormLayout()
    ui.checkBox_clean_dry_run = QCheckBox("演练：只记录日志，不移动或删除")
    form.addRow("运行模式", ui.checkBox_clean_dry_run)
    ui.comboBox_clean_action = QComboBox()
    ui.comboBox_clean_action.addItems(["移到 _待删（可恢复）", "永久删除匹配的单文件（无法恢复）"])
    form.addRow("处理方式", ui.comboBox_clean_action)
    ui.lineEdit_clean_directory = QLineEdit()
    ui.lineEdit_clean_directory.setPlaceholderText("留空：源文件盘符根目录下的 _待删")
    select = QPushButton("选择目录…")

    def select_directory():
        result = QFileDialog.getExistingDirectory(window, "选择待删目录", ui.lineEdit_clean_directory.text())
        if result:
            ui.lineEdit_clean_directory.setText(result)

    select.clicked.connect(select_directory)
    directory_row = QHBoxLayout()
    directory_row.addWidget(ui.lineEdit_clean_directory)
    directory_row.addWidget(select)
    form.addRow("待删目录", directory_row)
    ui.checkBox_clean_domain = QCheckBox("无番号视频文件名含 .com / .net / .cc / www.")
    form.addRow("域名样式规则", ui.checkBox_clean_domain)
    ui.doubleSpinBox_clean_video_size = QDoubleSpinBox()
    ui.doubleSpinBox_clean_video_size.setRange(0, 999999999)
    ui.doubleSpinBox_clean_video_size.setDecimals(2)
    ui.doubleSpinBox_clean_video_size.setSuffix(" MB")
    form.addRow("无番号视频小于 N", ui.doubleSpinBox_clean_video_size)
    layout.addLayout(form)
    help_text = QLabel(
        "关键词统一编辑上面的“文件名包含”，指定文件编辑“文件名等于”。\n"
        "排除规则优先。正常番号视频、NFO、图片、字幕和链接受保护。\n"
        "普通文档须命中文件名、扩展名或包含词；不会仅因很小而清理。\n"
        "仅含已确认垃圾的子目录始终整体移到待删；手动清理无需刮削。"
    )
    help_text.setWordWrap(True)
    layout.addWidget(help_text)
    ui.checkBox_auto_clean.setGeometry(20, 680, 240, 30)
    ui.checkBox_auto_clean.setEnabled(True)
    ui.pushButton_check_and_clean_files.setGeometry(160, 720, 321, 40)
    ui.pushButton_check_and_clean_files.setEnabled(True)
    ui.pushButton_save_cleanup = QPushButton("保存清理设置", group)
    ui.pushButton_save_cleanup.setGeometry(535, 680, 145, 30)
    ui.pushButton_save_cleanup.clicked.connect(window.pushButton_save_config_clicked)
    ui.label_271.setGeometry(20, 765, 661, 30)
    ui.label_271.setMinimumWidth(0)

    def sync_size(text):
        try:
            with QSignalBlocker(ui.doubleSpinBox_clean_video_size):
                ui.doubleSpinBox_clean_video_size.setValue(float(text))
        except ValueError:
            pass

    ui.lineEdit_escape_size.textChanged.connect(sync_size)
    ui.doubleSpinBox_clean_video_size.valueChanged.connect(lambda value: ui.lineEdit_escape_size.setText(f"{value:g}"))
    ui.checkBox_clean_dry_run.toggled.connect(lambda: refresh_cleanup_mode(window))
    ui.comboBox_clean_action.currentIndexChanged.connect(lambda: refresh_cleanup_mode(window))
    load_file_cleanup_settings(window)


def refresh_cleanup_mode(window):
    ui = window.Ui
    if ui.checkBox_clean_dry_run.isChecked():
        text = "当前为演练：只记录，不移动或删除。"
    elif ui.comboBox_clean_action.currentIndex() == 1:
        text = "当前为真实处理：单文件永久删除；纯垃圾目录整体移到待删。"
    else:
        text = "当前为真实处理：匹配文件和纯垃圾目录移到待删。"
    ui.label_271.setText(text)


def load_file_cleanup_settings(window):
    ui, cfg = window.Ui, manager.config
    ui.checkBox_clean_dry_run.setChecked(cfg.garbage_dry_run)
    ui.comboBox_clean_action.setCurrentIndex(int(cfg.garbage_permanent_delete))
    ui.lineEdit_clean_directory.setText(cfg.garbage_directory)
    ui.checkBox_clean_domain.setChecked(cfg.garbage_domain_rule)
    ui.doubleSpinBox_clean_video_size.setValue(cfg.file_size)
    ui.checkBox_auto_clean.setChecked(cfg.garbage_enabled)
    refresh_cleanup_mode(window)


def save_file_cleanup_settings(window):
    ui, cfg = window.Ui, manager.config
    cfg.garbage_enabled = ui.checkBox_auto_clean.isChecked()
    cfg.garbage_dry_run = ui.checkBox_clean_dry_run.isChecked()
    cfg.garbage_permanent_delete = ui.comboBox_clean_action.currentIndex() == 1
    cfg.garbage_directory = ui.lineEdit_clean_directory.text().strip()
    cfg.garbage_domain_rule = ui.checkBox_clean_domain.isChecked()
    cfg.file_size = ui.doubleSpinBox_clean_video_size.value()
