"""Shared layout and theme conventions for controller-created settings."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def normalize_controls(container):
    container.setProperty("settingsPanel", True)
    # Inherit the application's light/dark QSS, including focus and disabled states.
    for control in container.findChildren(QWidget):
        if not isinstance(control, (QLineEdit, QAbstractSpinBox, QComboBox, QPushButton)):
            continue
        control.setStyleSheet("")
        if isinstance(control, QLineEdit) and isinstance(control.parentWidget(), (QAbstractSpinBox, QComboBox)):
            # The outer control owns its editor geometry. A full row height here
            # exceeds the padded content area and pushes text below its center.
            control.setMinimumHeight(0)
            continue
        control.setMinimumHeight(30)
        if isinstance(control, QPushButton):
            control.setProperty("settingsAction", True)
        if isinstance(control, QAbstractSpinBox):
            control.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)


def setting_row(grid, index, title, control):
    label = QLabel(title)
    label.setMinimumWidth(130)
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    grid.addWidget(label, index, 0)
    if isinstance(control, QLayout):
        grid.addLayout(control, index, 1)
    else:
        control.setMinimumHeight(30)
        grid.addWidget(control, index, 1)
    return control


def group_layout(group, grid_widget):
    layout = QVBoxLayout(group)
    layout.setContentsMargins(20, 30, 20, 16)
    layout.setSpacing(12)
    layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    grid = grid_widget.layout()
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(8)
    if isinstance(grid, QGridLayout):
        grid.setColumnStretch(1, 1)
    layout.addWidget(grid_widget)
    return layout


def stack_settings_page(page):
    groups = sorted(
        page.findChildren(QGroupBox, options=Qt.FindChildOption.FindDirectChildrenOnly), key=lambda c: c.y()
    )
    layout = QVBoxLayout(page)
    layout.setContentsMargins(30, 20, 30, 20)
    layout.setSpacing(20)
    layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    for group in groups:
        if group.layout() is None:
            # Preserve the dimensions of existing Designer groups.
            group.setFixedHeight(group.height())
        layout.addWidget(group)
    layout.activate()
