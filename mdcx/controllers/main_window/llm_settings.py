from pydantic import HttpUrl
from PyQt6.QtWidgets import QDoubleSpinBox, QLabel, QLineEdit, QPushButton, QSpinBox

from mdcx.config.manager import manager
from mdcx.llm import is_loopback_url

from .local_model_settings import LocalModelController, display_path, setup_local_model_controls
from .settings_layout import group_layout, normalize_controls, setting_row, stack_settings_page


def setup_llm_settings(window):
    ui = window.Ui
    group = ui.groupBox_llm
    page = ui.scrollAreaWidgetContents_fanyi
    grid = ui.gridLayout_llm
    layout = group_layout(group, ui.gridLayoutWidget_llm)

    def row(index, title, name, control):
        setattr(ui, name, control)
        control.setObjectName(name)
        control.setMinimumHeight(30)
        return setting_row(grid, index, title, control)

    ui.pushButton_local_hymt2 = QPushButton("将所选本机模型设为备用")
    grid.addWidget(ui.pushButton_local_hymt2, 13, 1)
    timeout = row(14, "主模型超时（秒）：", "spinBox_llm_read_timeout", QSpinBox())
    timeout.setRange(1, 86400)
    retries = row(15, "拒绝 / 不可用重试：", "spinBox_llm_refusal_retries", QSpinBox())
    retries.setRange(0, 999)
    row(16, "备用 API URL：", "lineEdit_llm_fallback_url", QLineEdit())
    row(17, "备用 Model：", "lineEdit_llm_fallback_model", QLineEdit())
    key = row(18, "备用 API Key：", "lineEdit_llm_fallback_key", QLineEdit())
    key.setEchoMode(QLineEdit.EchoMode.Normal)
    timeout = row(19, "备用超时（秒）：", "spinBox_llm_fallback_read_timeout", QSpinBox())
    timeout.setRange(1, 86400)
    temperature = row(20, "备用温度：", "doubleSpinBox_llm_fallback_temperature", QDoubleSpinBox())
    primary_temperature = ui.doubleSpinBox_llm_temperature
    temperature.setDecimals(primary_temperature.decimals())
    temperature.setRange(primary_temperature.minimum(), primary_temperature.maximum())
    temperature.setSingleStep(primary_temperature.singleStep())
    ui.lineEdit_llm_key.setEchoMode(QLineEdit.EchoMode.Normal)
    ui.label_llm_url_desc.setText("主接口保留你的云端主模型配置；所选本机模型填入下方备用接口。")
    ui.label_llm_url_desc.setWordWrap(True)
    ui.label_llm_max_try.setText("云端主模型尝试：")
    ui.label_llm_max_try_desc.setText("仅云端主模型请求错误使用；本机及备用每一步只请求一次。")
    ui.label_llm_max_try_desc.setWordWrap(True)
    ui.spinBox_llm_max_try.setMinimum(1)
    help_text = QLabel(
        "日常方案：云端主模型 → 同模型重试一次 → 本机备用 → 对应字段原文。\n"
        "本机需手动启动；配置使用页面底部“保存”。备用地址留空可停用。"
    )
    help_text.setWordWrap(True)
    grid.addWidget(help_text, 21, 0, 1, 2)

    def update_local_mode():
        ui.spinBox_llm_max_try.setEnabled(not is_loopback_url(ui.lineEdit_llm_url.text()))

    def local_preset():
        window.local_model_controller.apply_fallback()

    ui.lineEdit_llm_url.textChanged.connect(update_local_mode)
    ui.pushButton_local_hymt2.clicked.connect(local_preset)
    setup_local_model_controls(window, layout)
    window.local_model_controller = LocalModelController(window)
    normalize_controls(group)
    stack_settings_page(page)
    load_llm_settings(window)
    update_local_mode()


def load_llm_settings(window):
    ui, tc = window.Ui, manager.config.translate_config
    window.local_model_controller.config_generation += 1
    ui.spinBox_llm_read_timeout.setValue(tc.llm_read_timeout)
    ui.spinBox_llm_refusal_retries.setValue(tc.llm_refusal_retries)
    ui.lineEdit_llm_fallback_url.setText(str(tc.llm_fallback_url) if tc.llm_fallback_url else "")
    ui.lineEdit_llm_fallback_model.setText(tc.llm_fallback_model)
    ui.lineEdit_llm_fallback_key.setText(tc.llm_fallback_key)
    ui.spinBox_llm_fallback_read_timeout.setValue(tc.llm_fallback_read_timeout)
    ui.doubleSpinBox_llm_fallback_temperature.setValue(tc.llm_fallback_temperature)
    ui.lineEdit_hymt2_root.setText(display_path(tc.local_model_search_root))
    ui.comboBox_hymt2_server.clear()
    ui.comboBox_hymt2_server.addItem(display_path(tc.local_model_server_path))
    ui.comboBox_hymt2_model.clear()
    ui.comboBox_hymt2_model.addItem(display_path(tc.local_model_path))


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
    tc.llm_fallback_temperature = ui.doubleSpinBox_llm_fallback_temperature.value()
    tc.local_model_search_root = ui.lineEdit_hymt2_root.text().strip()
    tc.local_model_server_path = ui.comboBox_hymt2_server.currentText().strip()
    tc.local_model_path = ui.comboBox_hymt2_model.currentText().strip()
