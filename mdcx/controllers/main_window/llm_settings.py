from pydantic import HttpUrl
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QLineEdit, QPushButton, QSpinBox, QWidget

from mdcx.config.manager import manager
from mdcx.llm import is_loopback_url


def setup_llm_settings(window):
    ui = window.Ui
    group = ui.groupBox_llm
    added_height = 365
    for child in ui.scrollAreaWidgetContents_fanyi.findChildren(
        QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly
    ):
        if child is not group and child.y() > group.y():
            child.move(child.x(), child.y() + added_height)
    group.resize(group.width(), group.height() + added_height)
    ui.gridLayoutWidget_llm.resize(661, 916)
    page = ui.scrollAreaWidgetContents_fanyi
    page.setMinimumHeight(page.height() + added_height)
    grid = ui.gridLayout_llm
    style = ui.lineEdit_llm_url.styleSheet()

    def row(index, title, name, control):
        setattr(ui, name, control)
        control.setObjectName(name)
        control.setMinimumHeight(30)
        control.setStyleSheet(style)
        label = QLabel(title)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(label, index, 0)
        grid.addWidget(control, index, 1)
        return control

    ui.pushButton_local_hymt2 = QPushButton("使用本机 Hy-MT2（海南鸡接口）")
    grid.addWidget(ui.pushButton_local_hymt2, 13, 1)
    timeout = row(14, "主模型超时（秒）：", "spinBox_llm_read_timeout", QSpinBox())
    timeout.setRange(1, 86400)
    retries = row(15, "拒绝 / 不可用重试：", "spinBox_llm_refusal_retries", QSpinBox())
    retries.setRange(0, 999)
    row(16, "备用 API URL：", "lineEdit_llm_fallback_url", QLineEdit())
    row(17, "备用 Model：", "lineEdit_llm_fallback_model", QLineEdit())
    key = row(18, "备用 API Key：", "lineEdit_llm_fallback_key", QLineEdit())
    key.setEchoMode(QLineEdit.EchoMode.Password)
    timeout = row(19, "备用超时（秒）：", "spinBox_llm_fallback_read_timeout", QSpinBox())
    timeout.setRange(1, 86400)
    ui.lineEdit_llm_key.setEchoMode(QLineEdit.EchoMode.Password)
    ui.label_llm_url_desc.setText("本机示例：http://127.0.0.1:8080/v1；本机可留空 Key")
    ui.label_llm_url_desc.setWordWrap(True)
    ui.label_llm_max_try.setText("云端主模型尝试：")
    ui.label_llm_max_try_desc.setText("仅云端主模型请求错误使用；本机及备用每一步只请求一次。")
    ui.label_llm_max_try_desc.setWordWrap(True)
    ui.spinBox_llm_max_try.setMinimum(1)
    help_text = QLabel(
        "本机服务须先启动。拒绝、请求失败或空返回：同模型重试 → 备用 → 对应字段原文。\n"
        "备用云端须填写地址、模型和 Key；留空即停用。使用页面底部“保存”。"
    )
    help_text.setWordWrap(True)
    grid.addWidget(help_text, 20, 0, 1, 2)

    def update_local_mode():
        ui.spinBox_llm_max_try.setEnabled(not is_loopback_url(ui.lineEdit_llm_url.text()))

    def local_preset():
        ui.lineEdit_llm_url.setText("http://127.0.0.1:8080/v1")
        ui.lineEdit_llm_model.setText("HY-MT2-7B-Q8_0")
        ui.lineEdit_llm_key.clear()
        ui.spinBox_llm_refusal_retries.setValue(1)
        ui.checkBox_llm.setChecked(True)

    ui.lineEdit_llm_url.textChanged.connect(update_local_mode)
    ui.pushButton_local_hymt2.clicked.connect(local_preset)
    load_llm_settings(window)
    update_local_mode()


def load_llm_settings(window):
    ui, tc = window.Ui, manager.config.translate_config
    ui.spinBox_llm_read_timeout.setValue(tc.llm_read_timeout)
    ui.spinBox_llm_refusal_retries.setValue(tc.llm_refusal_retries)
    ui.lineEdit_llm_fallback_url.setText(str(tc.llm_fallback_url) if tc.llm_fallback_url else "")
    ui.lineEdit_llm_fallback_model.setText(tc.llm_fallback_model)
    ui.lineEdit_llm_fallback_key.setText(tc.llm_fallback_key)
    ui.spinBox_llm_fallback_read_timeout.setValue(tc.llm_fallback_read_timeout)


def save_llm_settings(window):
    ui, tc = window.Ui, manager.config.translate_config
    url = ui.lineEdit_llm_fallback_url.text().strip()
    fallback_url = HttpUrl(url) if url else None
    tc.llm_read_timeout = ui.spinBox_llm_read_timeout.value()
    tc.llm_refusal_retries = ui.spinBox_llm_refusal_retries.value()
    tc.llm_fallback_url = fallback_url
    tc.llm_fallback_model = ui.lineEdit_llm_fallback_model.text().strip()
    tc.llm_fallback_key = ui.lineEdit_llm_fallback_key.text().strip()
    tc.llm_fallback_read_timeout = ui.spinBox_llm_fallback_read_timeout.value()
