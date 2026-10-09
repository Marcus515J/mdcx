from PyQt6.QtCore import QSignalBlocker, Qt
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from mdcx.config.manager import manager


def setup_file_cleanup_settings(window):
    ui = window.Ui
    group = ui.groupBox_61
    added_height = 775 - group.height()
    group.resize(group.width(), 775)
    ui.groupBox_9.move(ui.groupBox_9.x(), ui.groupBox_9.y() + added_height)
    page = ui.scrollAreaWidgetContents_guaxiaomulu
    page.resize(page.width(), page.height() + added_height)
    page.setMinimumHeight(page.height())
    ui.checkBox_i_understand_clean.hide()
    ui.checkBox_i_agree_clean.hide()
    ui.label_199.setText("启用规则任一命中即清理；完整文件名严格相等，包含词忽略空白和大小写。")
    ui.label_199.setWordWrap(True)
    ui.label_263.setText("视频大小(KB)≤：")
    ui.lineEdit_clean_file_name.setToolTip("填写完整文件名（含扩展名），多个用 | 分隔；空格与大小写必须一致")
    ui.lineEdit_clean_file_size.setToolTip("只作用于无番号视频；0 表示关闭，不因文档很小而清理文档")
    # Extend the existing grid so old and new labels/fields share the same columns.
    ui.gridLayoutWidget_34.resize(661, 510)
    grid = ui.gridLayout_52
    field_style = ui.lineEdit_clean_file_name.styleSheet()

    def row(index, text, control):
        label = QLabel(text, ui.gridLayoutWidget_34)
        label.setMinimumWidth(130)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(label, index, 0)
        if isinstance(control, QHBoxLayout):
            grid.addLayout(control, index, 1)
        else:
            control.setMinimumHeight(30)
            grid.addWidget(control, index, 1)

    ui.checkBox_clean_dry_run = QCheckBox("演练：只记录，不移动或删除")
    row(8, "运行模式：", ui.checkBox_clean_dry_run)
    ui.comboBox_clean_action = QComboBox()
    ui.comboBox_clean_action.setObjectName("comboBox_clean_action")
    ui.comboBox_clean_action.addItems(["移到 _待删（可恢复）", "永久删除匹配的单文件（无法恢复）"])
    ui.comboBox_clean_action.setStyleSheet("QComboBox {" + field_style + "}")
    row(9, "处理方式：", ui.comboBox_clean_action)
    ui.lineEdit_clean_directory = QLineEdit()
    ui.lineEdit_clean_directory.setObjectName("lineEdit_clean_directory")
    ui.lineEdit_clean_directory.setMinimumHeight(30)
    ui.lineEdit_clean_directory.setStyleSheet(field_style)
    ui.lineEdit_clean_directory.setPlaceholderText("留空：源文件盘符根目录下的 _待删")
    select = QPushButton("选择目录…")
    select.setFixedSize(110, 30)

    def select_directory():
        result = QFileDialog.getExistingDirectory(window, "选择待删目录", ui.lineEdit_clean_directory.text())
        if result:
            ui.lineEdit_clean_directory.setText(result)

    select.clicked.connect(select_directory)
    directory_row = QHBoxLayout()
    directory_row.addWidget(ui.lineEdit_clean_directory, 1)
    directory_row.addWidget(select)
    row(10, "待删目录：", directory_row)
    ui.checkBox_clean_domain = QCheckBox("无番号视频文件名含 .com / .net / .cc / www.")
    row(11, "域名规则：", ui.checkBox_clean_domain)
    ui.doubleSpinBox_clean_video_size = QDoubleSpinBox()
    ui.doubleSpinBox_clean_video_size.setObjectName("doubleSpinBox_clean_video_size")
    ui.doubleSpinBox_clean_video_size.setStyleSheet(field_style)
    ui.doubleSpinBox_clean_video_size.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    ui.doubleSpinBox_clean_video_size.setRange(0, 999999999)
    ui.doubleSpinBox_clean_video_size.setDecimals(2)
    ui.doubleSpinBox_clean_video_size.setSuffix(" MB")
    row(12, "视频小于 N：", ui.doubleSpinBox_clean_video_size)
    ui.doubleSpinBox_clean_video_size.setToolTip("仅限无番号视频；与原有最小视频大小共用 N")

    help_panel = QWidget(group)
    help_panel.setObjectName("fileCleanupOptions")
    help_panel.setGeometry(20, 568, 661, 95)
    help_layout = QGridLayout(help_panel)
    help_layout.setContentsMargins(0, 0, 0, 0)
    help_layout.setHorizontalSpacing(24)
    help_layout.setColumnStretch(0, 1)
    help_layout.setColumnStretch(1, 1)
    for column, text in enumerate(
        (
            "<b>规则怎么填</b><br>完整名称填“文件名等于”，广告词填“文件名包含”；排除规则优先。",
            "<b>处理与保护</b><br>正常番号视频、NFO、图片、字幕和链接保留；纯垃圾子目录整目录移到待删。",
        )
    ):
        label = QLabel(text, help_panel)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop)
        help_layout.addWidget(label, 0, column)
    note = QLabel("普通文档不会仅因体积小被清理。手动清理无需刮削；设置使用页面底部“保存”。", help_panel)
    note.setWordWrap(True)
    help_layout.addWidget(note, 1, 0, 1, 2)
    ui.checkBox_auto_clean.setGeometry(20, 680, 240, 40)
    ui.checkBox_auto_clean.setEnabled(True)
    ui.pushButton_check_and_clean_files.setGeometry(310, 680, 370, 40)
    ui.pushButton_check_and_clean_files.setEnabled(True)
    ui.label_271.setGeometry(20, 728, 661, 32)
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
