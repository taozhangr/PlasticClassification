import csv
import os
from pathlib import Path
import re
import sys

import PyQt5
import serial
from serial.tools import list_ports

from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from knn import SpectrumClassifier, get_prediction_label


def _configure_qt_runtime():
    pyqt_root = Path(PyQt5.__file__).resolve().parent
    qt_root = pyqt_root / "Qt5"
    plugin_root = qt_root / "plugins"
    platform_root = plugin_root / "platforms"
    bin_root = qt_root / "bin"

    if platform_root.exists():
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platform_root)
    if plugin_root.exists():
        os.environ["QT_PLUGIN_PATH"] = str(plugin_root)
    if bin_root.exists():
        os.environ["PATH"] = str(bin_root) + os.pathsep + os.environ.get("PATH", "")
        if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(bin_root))


_configure_qt_runtime()

APP_ROOT = Path(__file__).resolve().parent
APP_LOGO_PATH = APP_ROOT / "icon" / "logo.png"
TRAIN_DATA_FILENAME = "train_data.csv"
SPECTRUM_CHANNELS = ("R", "S", "T", "U", "V", "W")
SPECTRUM_VALUE_PATTERN = re.compile(r"([RSTUVW])\[(-?\d+(?:\.\d+)?)\]")
SCAN_COMMAND = "sc\r\n"
SCAN_TIMEOUT_MS = 5000

SPACING_8 = 8
SPACING_12 = 12
SPACING_16 = 16
SPACING_20 = 20

LIGHT_STYLESHEET = """
QMainWindow { background: #f3f5f8; }
QWidget {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "SimHei";
    font-size: 9px;
    color: #24324a;
}
QFrame#surface, QFrame#topBar { background: transparent; border: none; }
QFrame#card, QFrame#metricCard, QFrame#resultInfoCard {
    background: #ffffff;
    border: 1px solid #e4e9f1;
    border-radius: 12px;
}
QFrame#plotContainer {
    background: #ffffff;
    border: 1px solid #e5ebf3;
    border-radius: 10px;
}
QFrame#divider {
    background: #edf1f6;
    border: none;
    min-height: 1px;
    max-height: 1px;
}
QLabel#windowTitle { font-size: 9px; font-weight: 500; color: #3d4c66; }
QLabel#infoTitle { font-size: 14px; font-weight: 700; color: #1a304d; }
QLabel#sectionTitle { font-size: 12px; font-weight: 700; color: #1d3351; }
QLabel#fieldLabel { font-size: 9px; font-weight: 600; color: #2c3c57; }
QLabel#subtitle, QLabel#hintText { font-size: 9px; color: #8b99af; }
QLabel#metricTitle, QLabel#valueTitle, QLabel#mutedText { font-size: 9px; color: #8492a7; }
QLabel#metricValue { font-size: 11px; font-weight: 700; color: #1f3552; }
QLabel#resultName { font-size: 12px; font-weight: 700; color: #1f3553; }
QLabel#emptyTitle { font-size: 11px; font-weight: 700; color: #5a6a83; }
QLabel#emptySubtitle { font-size: 9px; color: #8b98ac; }
QLabel#resultCircle {
    min-width: 76px; max-width: 76px; min-height: 76px; max-height: 76px;
    border-radius: 38px;
    background: #f2f5fa;
    border: 1px solid #dde4ef;
    color: #4b5d78;
    font-size: 22px;
    font-weight: 700;
}
QLabel#statusDot, QLabel#statusDotMini {
    min-width: 8px; max-width: 8px; min-height: 8px; max-height: 8px;
    border-radius: 4px;
}
QLabel[status="offline"]#statusDot, QLabel[status="offline"]#statusDotMini { background: #b6c2d3; }
QLabel[status="online"]#statusDot, QLabel[status="online"]#statusDotMini { background: #1dbf73; }
QLabel#emptyIcon {
    min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;
    border-radius: 15px;
    border: 1px solid #d5deea;
    color: #aab7c9;
    font-size: 15px;
    font-weight: 700;
}
QPushButton, QComboBox, QLineEdit, QSpinBox {
    min-height: 28px;
    max-height: 28px;
    border-radius: 6px;
    border: 1px solid #d8e0ec;
    background: #ffffff;
    color: #2b3f5f;
    padding: 0 6px;
    font-size: 10px;
}
QComboBox {
    padding-right: 24px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border: none;
    background: transparent;
}
QSpinBox {
    padding: 0 24px;
}
QPushButton[role="spin_left"], QPushButton[role="spin_right"] {
    background: #f8fafd;
    border: 1px solid #d8e0ec;
    color: #4e6483;
    font-size: 11px;
    font-weight: bold;
    padding: 0;
    min-height: 28px;
    max-height: 28px;
    min-width: 28px;
    max-width: 28px;
}
QPushButton[role="spin_left"] {
    border-right: none;
    border-top-left-radius: 6px;
    border-bottom-left-radius: 6px;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
}
QPushButton[role="spin_right"] {
    border-left: none;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
}
QPushButton[role="spin_left"]:hover, QPushButton[role="spin_right"]:hover {
    background: #eef2f8;
}
QPushButton[role="spin_left"]:disabled, QPushButton[role="spin_right"]:disabled {
    color: #c0cddf;
}
QLabel#spinLabel {
    background: #ffffff;
    border-top: 1px solid #d8e0ec;
    border-bottom: 1px solid #d8e0ec;
    color: #2b3f5f;
    font-size: 11px;
}
QTextEdit {
    min-height: 108px;
    max-height: 16777215px;
    border-radius: 6px;
    border: 1px solid #d8e0ec;
    background: #ffffff;
    color: #2b3f5f;
    padding: 8px;
    font-size: 11px;
}
QPushButton:hover, QComboBox:hover, QLineEdit:hover, QSpinBox:hover {
    border-color: #c3d1e8;
}
QPushButton:disabled, QComboBox:disabled, QLineEdit:disabled, QSpinBox:disabled {
    color: #9cabbd;
    background: #f8fafd;
    border-color: #dee6f2;
}
QPushButton[role="primary"] {
    background: #2f66e8;
    border: 1px solid #2f66e8;
    color: #ffffff;
    font-weight: 700;
}
QPushButton[role="primary"]:hover {
    background: #285bd3;
    border-color: #285bd3;
}
QPushButton[role="secondary"] {
    background: #ffffff;
    border: 1px solid #d5deeb;
    color: #4e6483;
    font-weight: 600;
}
QPushButton[role="ghost"] {
    background: #ffffff;
    border: 1px solid #d6e0ef;
    color: #4f6687;
}
QPushButton#settingsButton {
    font-weight: 700;
}
QPushButton[role="icon"] {
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
    padding: 0;
    font-size: 11px;
}
QPushButton[role="mode"] {
    background: #ffffff;
    border: 1px solid #d5deea;
    color: #415978;
    min-width: 96px;
}
QPushButton[role="mode"]:hover {
    background: #f8fafd;
}
QPushButton[role="mode"]:checked {
    background: #f0f5ff;
    border: 1px solid #2f66e8;
    color: #2f66e8;
    font-weight: 700;
}
QListWidget {
    border: none;
    background: transparent;
}
QListWidget::item {
    border-bottom: 1px solid #eef2f8;
    padding: 8px 2px;
}
"""


class CountSelector(QWidget):
    valueChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("countSelector")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.btn_minus = QPushButton("－")
        self.btn_minus.setCursor(Qt.PointingHandCursor)
        self.btn_minus.setProperty("role", "spin_left")
        self.btn_minus.clicked.connect(self._on_minus)

        self.label = QLabel("3")
        self.label.setObjectName("spinLabel")
        self.label.setAlignment(Qt.AlignCenter)

        self.btn_plus = QPushButton("＋")
        self.btn_plus.setCursor(Qt.PointingHandCursor)
        self.btn_plus.setProperty("role", "spin_right")
        self.btn_plus.clicked.connect(self._on_plus)

        layout.addWidget(self.btn_minus)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.btn_plus)

        self._min = 1
        self._max = 20
        self._val = 3

    def setRange(self, minimum, maximum):
        self._min = minimum
        self._max = maximum
        self._update_ui()

    def value(self):
        return self._val

    def setValue(self, v):
        self._val = max(self._min, min(self._max, v))
        self._update_ui()
        self.valueChanged.emit(self._val)

    def setFixedWidth(self, width):
        super().setFixedWidth(width)

    def setAlignment(self, align):
        self.label.setAlignment(align)

    def _on_minus(self):
        if self._val > self._min:
            self.setValue(self._val - 1)

    def _on_plus(self):
        if self._val < self._max:
            self.setValue(self._val + 1)

    def _update_ui(self):
        self.label.setText(str(self._val))
        self.btn_minus.setEnabled(self._val > self._min)
        self.btn_plus.setEnabled(self._val < self._max)


class NativeMessageDialog(QDialog):
    ICON_MAP = {
        QMessageBox.Warning: QStyle.SP_MessageBoxWarning,
        QMessageBox.Information: QStyle.SP_MessageBoxInformation,
        QMessageBox.Critical: QStyle.SP_MessageBoxCritical,
        QMessageBox.Question: QStyle.SP_MessageBoxQuestion,
    }

    def __init__(self, title, text, icon=QMessageBox.Information, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.MSWindowsFixedSizeDialogHint, True)

        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SetFixedSize)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        content_row = QHBoxLayout()
        content_row.setSpacing(14)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        icon_label.setFixedSize(32, 32)
        standard_icon = self.style().standardIcon(self.ICON_MAP.get(icon, QStyle.SP_MessageBoxInformation))
        icon_label.setPixmap(standard_icon.pixmap(32, 32))
        content_row.addWidget(icon_label, 0, Qt.AlignVCenter)

        text_label = QLabel(text)
        text_label.setWordWrap(False)
        text_label.setMinimumWidth(0)
        text_label.setMaximumWidth(16777215)
        text_label.setMinimumWidth(text_label.fontMetrics().horizontalAdvance(text) + 8)
        text_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        text_label.setTextInteractionFlags(Qt.NoTextInteraction)
        text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        content_row.addWidget(text_label, 1, Qt.AlignLeft | Qt.AlignVCenter)

        layout.addLayout(content_row)
        layout.addSpacing(8)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.setCenterButtons(False)
        buttons.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        ok_button.setText("确定")
        ok_button.setMinimumWidth(78)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons, 0, Qt.AlignRight)

        self.adjustSize()


class SerialAssistant(QMainWindow):
    MODE_PREDICT = "识别模式"
    MODE_TRAIN = "训练模式"
    TRAIN_LABEL_OPTIONS = ["HDPE", "PC", "PE", "PET", "PP", "PS", "PVC", "PET-R", "PET-G", "PET-B"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("塑料光谱识别工作台")
        self.resize(1280, 740)
        self.setMinimumSize(1120, 660)
        self.setStyleSheet(LIGHT_STYLESHEET)

        self.current_mode = self.MODE_PREDICT
        self.connected = False
        self.collecting = False
        self.data_dir = APP_ROOT / "data"
        self.model_path = APP_ROOT / "classifier.pkl"
        self.pending_scan_values = {}
        self.train_group_scans = []
        self.saved_group_count = 0
        self.predict_scan_active = False
        self.serial_port = None
        self.serial_buffer = ""
        self.loaded_model = None
        self.loaded_model_path = None

        self.serial_timer = QTimer(self)
        self.serial_timer.setInterval(80)
        self.serial_timer.timeout.connect(self._poll_serial_data)
        self.scan_timeout_timer = QTimer(self)
        self.scan_timeout_timer.setSingleShot(True)
        self.scan_timeout_timer.setInterval(SCAN_TIMEOUT_MS)
        self.scan_timeout_timer.timeout.connect(self._handle_scan_timeout)

        self._build_ui()
        # 兼容旧逻辑中的控件命名
        self.baud_combo = self.baudrate_combo
        self.scan_button = self.start_button
        self.refresh_ports()
        self._apply_mode(self.MODE_PREDICT)
        self._load_classifier(silent=True)
        self._append_log("系统初始化完成，等待连接设备。")

    def _build_ui(self):
        surface = QFrame()
        surface.setObjectName("surface")
        self.setCentralWidget(surface)

        root_layout = QVBoxLayout(surface)
        root_layout.setContentsMargins(10, 8, 10, 10)
        root_layout.setSpacing(8)

        # 顶部自定义栏过高时会和系统标题栏形成视觉重复，默认隐藏。
        # 后续如需恢复可取消下一行注释并调用 _build_top_bar()。
        # root_layout.addWidget(self._build_top_bar())

        # 让左侧面板能够拉伸，背景卡片才不会悬空
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)
        content_layout.addWidget(self._build_left_panel())
        content_layout.addWidget(self._build_center_panel(), 1)
        content_layout.addWidget(self._build_right_panel())
        content_layout.setStretch(0, 30)
        content_layout.setStretch(1, 50)
        content_layout.setStretch(2, 20)
        root_layout.addLayout(content_layout, 1)

    def _build_top_bar(self):
        card = QFrame()
        card.setObjectName("topBar")
        card.setFixedHeight(24)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(6)

        logo = self._create_logo_label(14)
        layout.addWidget(logo)

        title = QLabel("塑料光谱识别工作台")
        title.setObjectName("windowTitle")
        layout.addWidget(title)
        layout.addStretch(1)
        return card

    def _build_left_panel(self):
        panel = QWidget()
        panel.setFixedWidth(348)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        device_card, device_layout = self._create_card("设备连接", "选择串口并连接设备", padding=14, spacing=9)

        port_row = QHBoxLayout()
        port_row.setContentsMargins(0, 0, 0, 0)
        port_row.setSpacing(SPACING_8)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumContentsLength(8)
        self.port_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        port_row.addWidget(self.port_combo, 1)
        self.refresh_button = QPushButton("⟳")
        self.refresh_button.setProperty("role", "icon")
        self.refresh_button.setToolTip("刷新串口")
        self.refresh_button.clicked.connect(self.refresh_ports)
        port_row.addWidget(self.refresh_button)
        self._add_field_block(device_layout, "串口", port_row)

        self.baudrate_combo = QComboBox()
        self.baudrate_combo.setMinimumContentsLength(8)
        self.baudrate_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.baudrate_combo.addItems(["9600", "19200", "38400", "57600", "115200", "230400"])
        self.baudrate_combo.setCurrentText("115200")
        self._add_field_block(device_layout, "波特率", self.baudrate_combo)

        self.data_bits_combo = QComboBox()
        self.data_bits_combo.setMinimumContentsLength(6)
        self.data_bits_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.data_bits_combo.addItems(["5", "6", "7", "8"])
        self.data_bits_combo.setCurrentText("8")
        self._add_field_block(device_layout, "数据位", self.data_bits_combo)

        self.parity_combo = QComboBox()
        self.parity_combo.setMinimumContentsLength(8)
        self.parity_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.parity_combo.addItems(["奇校验", "偶校验", "无"])
        self.parity_combo.setCurrentText("无")
        self._add_field_block(device_layout, "校验位", self.parity_combo)

        self.stop_bits_combo = QComboBox()
        self.stop_bits_combo.setMinimumContentsLength(6)
        self.stop_bits_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.stop_bits_combo.addItems(["1", "1.5", "2"])
        self.stop_bits_combo.setCurrentText("1")
        self._add_field_block(device_layout, "停止位", self.stop_bits_combo)

        self.connect_button = QPushButton("连接设备")
        self.connect_button.setProperty("role", "primary")
        self.connect_button.clicked.connect(self._toggle_connection_state)
        device_layout.addWidget(self.connect_button)

        layout.addWidget(device_card)

        collect_card, collect_layout = self._create_card("采集设置", "选择识别模式并设置采集次数", padding=14, spacing=9)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.predict_mode_button = QPushButton("识别模式")
        self.predict_mode_button.setProperty("role", "mode")
        self.predict_mode_button.setCheckable(True)
        self.train_mode_button = QPushButton("训练模式")
        self.train_mode_button.setProperty("role", "mode")
        self.train_mode_button.setCheckable(True)

        mode_group = QButtonGroup(self)
        mode_group.addButton(self.predict_mode_button)
        mode_group.addButton(self.train_mode_button)
        mode_group.setExclusive(True)

        self.predict_mode_button.clicked.connect(lambda: self._apply_mode(self.MODE_PREDICT))
        self.train_mode_button.clicked.connect(lambda: self._apply_mode(self.MODE_TRAIN))
        mode_row.addWidget(self.predict_mode_button)
        mode_row.addWidget(self.train_mode_button)
        collect_layout.addLayout(mode_row)

        spin_row = QHBoxLayout()
        spin_row.setContentsMargins(0, 0, 0, 0)
        spin_row.setSpacing(SPACING_8)
        spin_row.addWidget(self._field_label("采集次数"))
        spin_row.addStretch(1)
        self.sample_count_spin = CountSelector()
        self.sample_count_spin.setRange(1, 20)
        self.sample_count_spin.setValue(3)
        self.sample_count_spin.setFixedWidth(157)
        self.sample_count_spin.setAlignment(Qt.AlignCenter)
        self.sample_count_spin.valueChanged.connect(self._update_progress_text)
        spin_row.addWidget(self.sample_count_spin)
        collect_layout.addLayout(spin_row)

        tip = QLabel("建议 3-5 次，结果更稳定")
        tip.setObjectName("hintText")
        collect_layout.addWidget(tip)
        layout.addWidget(collect_card)

        # 避免窗口变高时在“系统设置”上方产生过大留白
        layout.addSpacing(8)

        self.settings_button = QPushButton("系统设置")
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.setProperty("role", "ghost")
        self.settings_button.clicked.connect(self._show_settings_dialog)
        layout.addWidget(self.settings_button)

        return panel

    def _show_settings_dialog(self):
        class SettingsDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("系统设置")
                self.resize(400, 200)
                self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
                self.setWindowModality(Qt.ApplicationModal)
                # 避免继承主窗口 QSS，强制使用系统原生样式
                self.setStyleSheet("")
                
                layout = QVBoxLayout(self)
                layout.setContentsMargins(SPACING_20, SPACING_20, SPACING_20, SPACING_20)
                layout.setSpacing(SPACING_16)
                
                # 数据保存路径
                data_path_layout = QVBoxLayout()
                data_path_layout.setSpacing(4)
                data_path_label = QLabel("数据保存路径：")
                data_path_label.setObjectName("fieldLabel")
                data_path_layout.addWidget(data_path_label)
                
                data_row = QHBoxLayout()
                self.data_input = QLineEdit()
                self.data_input.setText(str(parent.data_dir))
                data_btn = QPushButton("浏览...")
                data_btn.clicked.connect(self._browse_data_path)
                data_row.addWidget(self.data_input, 1)
                data_row.addWidget(data_btn)
                data_path_layout.addLayout(data_row)
                layout.addLayout(data_path_layout)
                
                # 模型文件路径
                model_path_layout = QVBoxLayout()
                model_path_layout.setSpacing(4)
                model_path_label = QLabel("模型文件路径：")
                model_path_label.setObjectName("fieldLabel")
                model_path_layout.addWidget(model_path_label)
                
                model_row = QHBoxLayout()
                self.model_input = QLineEdit()
                self.model_input.setText(str(parent.model_path))
                model_btn = QPushButton("浏览...")
                model_btn.clicked.connect(self._browse_model_path)
                model_row.addWidget(self.model_input, 1)
                model_row.addWidget(model_btn)
                model_path_layout.addLayout(model_row)
                layout.addLayout(model_path_layout)
                
                layout.addStretch(1)
                
                # 底部按钮（系统原生风格）
                buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
                buttons.button(QDialogButtonBox.Save).setText("保存")
                buttons.button(QDialogButtonBox.Cancel).setText("取消")
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons)
                
            def _browse_data_path(self):
                path = QFileDialog.getExistingDirectory(self, "选择数据保存目录", self.data_input.text())
                if path:
                    self.data_input.setText(path)
                    
            def _browse_model_path(self):
                path, _ = QFileDialog.getOpenFileName(self, "选择模型文件", self.model_input.text(), "Model Files (*.pkl *.joblib);;All Files (*)")
                if path:
                    self.model_input.setText(path)
                    
        dialog = SettingsDialog(self)
        if self._exec_native_dialog(dialog) == QDialog.Accepted:
            self.data_dir = Path(dialog.data_input.text()).expanduser()
            self.model_path = Path(dialog.model_input.text()).expanduser()
            self.loaded_model = None
            self.loaded_model_path = None
            self._append_log(
                f"系统设置已更新，训练数据目录：{self.data_dir}，模型文件：{self.model_path}"
            )

    def _build_center_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        top_card, top_layout = self._create_card(padding=12, spacing=8)
        top_card.setFixedHeight(154)

        status_grid = QGridLayout()
        status_grid.setHorizontalSpacing(8)
        status_grid.setVerticalSpacing(12)

        head_text = QVBoxLayout()
        head_text.setSpacing(1)
        head_title = QLabel("光谱采集与识别")
        head_title.setObjectName("sectionTitle")
        head_subtitle = QLabel("采集样本光谱并进行识别分析")
        head_subtitle.setObjectName("subtitle")
        head_text.addWidget(head_title)
        head_text.addWidget(head_subtitle)
        head_text.addStretch(1) # Push texts to the top if needed
        status_grid.addLayout(head_text, 0, 0, 1, 2)

        self.start_button = QPushButton("开始采集")
        self.start_button.setProperty("role", "primary")
        self.start_button.setSizePolicy(self.start_button.sizePolicy().Expanding, self.start_button.sizePolicy().Fixed)
        self.start_button.clicked.connect(self._handle_start_button_clicked)
        
        status_grid.addWidget(self.start_button, 0, 2, 1, 1, alignment=Qt.AlignBottom)

        self.connection_metric_value, self.connection_metric_dot = self._create_metric_card("连接状态", "离线", True)
        self.mode_metric_value, _ = self._create_metric_card("模式", "识别模式")
        self.progress_metric_value, _ = self._create_metric_card("采集进度", "0 / 3")

        status_grid.addWidget(self._metric_card_holder(self.connection_metric_value, self.connection_metric_dot), 1, 0)
        status_grid.addWidget(self._metric_card_holder(self.mode_metric_value), 1, 1)
        status_grid.addWidget(self._metric_card_holder(self.progress_metric_value), 1, 2)

        status_grid.setColumnStretch(0, 1)
        status_grid.setColumnStretch(1, 1)
        status_grid.setColumnStretch(2, 1)
        
        top_layout.addLayout(status_grid)
        layout.addWidget(top_card, 0) # Fixed height portion

        log_card, log_layout = self._create_card(padding=10, spacing=8)
        log_head = QHBoxLayout()
        log_head.setSpacing(SPACING_8)
        log_title = QLabel("实时日志")
        log_title.setObjectName("sectionTitle")
        log_head.addWidget(log_title)
        log_head.addStretch(1)
        clear_button = QPushButton("清空日志")
        clear_button.setProperty("role", "secondary")
        clear_button.clicked.connect(self._clear_logs)
        log_head.addWidget(clear_button)
        log_layout.addLayout(log_head)

        self.log_stack = QStackedWidget()
        self.log_empty = self._create_empty_widget("日志将显示在这里", None, "!")
        self.log_stack.addWidget(self.log_empty)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_stack.addWidget(self.log_text)
        self.log_stack.setCurrentIndex(0)
        log_layout.addWidget(self.log_stack)

        cmd_row = QHBoxLayout()
        cmd_row.setSpacing(SPACING_8)
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("输入自定义串口指令")
        self.send_button = QPushButton("发送指令")
        self.send_button.setProperty("role", "primary")
        self.send_button.clicked.connect(self._send_command)
        cmd_row.addWidget(self.command_input, 1)
        cmd_row.addWidget(self.send_button)
        log_layout.addLayout(cmd_row)

        layout.addWidget(log_card, 1)
        return panel

    def _build_right_panel(self):
        panel = QWidget()
        panel.setFixedWidth(252)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        result_card, result_layout = self._create_card("识别结果", padding=10, spacing=8)
        result_card.setFixedHeight(154) # 强制与左侧的光谱采集记录卡片高度对齐

        result_layout.addStretch(1) # Push to center

        self.result_name_label = QLabel("暂无结果")
        self.result_name_label.setObjectName("resultName")
        font = self.result_name_label.font()
        font.setPointSize(24)
        font.setBold(True)
        self.result_name_label.setFont(font)
        self.result_name_label.setAlignment(Qt.AlignCenter)
        
        self.result_name_label.setStyleSheet("color: #2f66e8;") # 采用醒目的主色调
        result_layout.addWidget(self.result_name_label)
        result_layout.addStretch(1) # Push to center
        
        layout.addWidget(result_card)

        history_card, history_layout = self._create_card("最近记录", "最多保留最近 20 条记录", padding=10, spacing=8)
        self.history_stack = QStackedWidget()
        history_empty = self._create_empty_widget("暂无记录", None, "⌁")
        self.history_stack.addWidget(history_empty)

        self.history_list = QListWidget()
        self.history_stack.addWidget(self.history_list)
        self.history_stack.setCurrentIndex(0)
        history_layout.addWidget(self.history_stack, 1)
        layout.addWidget(history_card, 1)
        # layout.addStretch(1) 移除可能导致变形的占位

        return panel

    def _create_logo_label(self, size):
        logo = QLabel()
        logo.setFixedSize(size, size)
        logo.setAlignment(Qt.AlignCenter)
        if APP_LOGO_PATH.exists():
            pixmap = QPixmap(str(APP_LOGO_PATH))
            if not pixmap.isNull():
                logo.setPixmap(pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return logo
        logo.setText("∿")
        font = QFont()
        font.setPointSize(max(10, int(size / 2.6)))
        font.setBold(True)
        logo.setFont(font)
        return logo

    def _create_card(self, title=None, subtitle=None, padding=SPACING_16, spacing=SPACING_12):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(padding, padding, padding, padding)
        layout.setSpacing(spacing)
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("sectionTitle")
            layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("subtitle")
            layout.addWidget(subtitle_label)
        return card, layout

    def _create_metric_card(self, title, value, with_dot=False):
        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        dot_label = None
        if with_dot:
            dot_label = QLabel()
            dot_label.setObjectName("statusDotMini")
            dot_label.setProperty("status", "offline")
        value_label.metric_title = title
        return value_label, dot_label

    def _metric_card_holder(self, value_label, dot_label=None):
        card = QFrame()
        card.setObjectName("metricCard")
        card.setMinimumHeight(62)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)
        title = QLabel(value_label.metric_title)
        title.setObjectName("metricTitle")
        layout.addWidget(title)
        if dot_label:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(dot_label)
            row.addWidget(value_label)
            row.addStretch(1)
            layout.addLayout(row)
        else:
            layout.addWidget(value_label)
        return card

    def _legend_item(self, color, text):
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        line = QFrame()
        line.setFixedSize(18, 2)
        line.setStyleSheet("QFrame { border: none; background: %s; }" % color)
        row.addWidget(line)
        label = QLabel(text)
        label.setObjectName("mutedText")
        row.addWidget(label)
        return widget

    def _create_empty_widget(self, title, subtitle=None, icon="•"):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(6)
        layout.addStretch(1)
        icon_label = QLabel(icon)
        icon_label.setObjectName("emptyIcon")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label, alignment=Qt.AlignCenter)
        title_label = QLabel(title)
        title_label.setObjectName("emptyTitle")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("emptySubtitle")
            subtitle_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(subtitle_label)
        layout.addStretch(1)
        return box

    def _add_field_block(self, parent_layout, label_text, control):
        block = QWidget()
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(4)
        block_layout.addWidget(self._field_label(label_text))
        if isinstance(control, QHBoxLayout):
            block_layout.addLayout(control)
        else:
            block_layout.addWidget(control)
        parent_layout.addWidget(block)

    def _create_value_row(self, parent_layout, name, value):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 8, 12, 8)
        row_layout.setSpacing(8)
        title = QLabel(name)
        title.setObjectName("valueLabelTitle")
        value_label = QLabel(value)
        value_label.setObjectName("fieldLabel")
        row_layout.addWidget(title)
        row_layout.addStretch(1)
        row_layout.addWidget(value_label)
        parent_layout.addWidget(row)
        return value_label

    def _field_label(self, text):
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _create_divider(self):
        divider = QFrame()
        divider.setObjectName("divider")
        return divider

    def refresh_ports(self):
        previous = self.port_combo.currentData() or self.port_combo.currentText()
        ports = sorted(list_ports.comports(), key=lambda item: item.device)
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        if not ports:
            self.port_combo.addItem("无可用串口")
        else:
            selected_index = 0
            for index, port in enumerate(ports):
                label = f"{port.device} - {port.description}"
                self.port_combo.addItem(label, port.device)
                if previous and previous == port.device:
                    selected_index = index
            self.port_combo.setCurrentIndex(selected_index)
        self.port_combo.blockSignals(False)
        if not self.connected:
            self._append_log(f"串口列表已刷新，共 {len(ports)} 个可用端口。")

    def _toggle_connection_state(self):
        if self.connected:
            self._disconnect_serial("设备已断开连接。")
            return

        port_name = self.port_combo.currentData()
        if not port_name:
            self._show_native_message(QMessageBox.Warning, "未选择串口", "请先选择有效串口。")
            return

        try:
            self.serial_port = serial.Serial(
                port=port_name,
                baudrate=int(self.baudrate_combo.currentText()),
                bytesize=self._get_serial_bytesize(),
                parity=self._get_serial_parity(),
                stopbits=self._get_serial_stopbits(),
                timeout=0,
                write_timeout=1,
            )
        except serial.SerialException as exc:
            self.serial_port = None
            self._show_native_message(QMessageBox.Critical, "连接失败", f"打开串口失败：{exc}")
            self._append_log(f"打开串口失败：{exc}")
            return

        self.serial_buffer = ""
        self.connected = True
        self.serial_timer.start()
        self._update_connection_status(True)
        self._append_log(f"设备连接成功：{port_name}")

    def _apply_mode(self, mode_text):
        self.current_mode = mode_text
        self._reset_train_collection_state()
        self.predict_scan_active = False
        self._clear_scan_timeout()
        self.predict_mode_button.setChecked(mode_text == self.MODE_PREDICT)
        self.train_mode_button.setChecked(mode_text == self.MODE_TRAIN)
        self.mode_metric_value.setText(mode_text)
        self.start_button.setText("开始识别" if mode_text == self.MODE_PREDICT else "开始采集")
        self.result_name_label.setText("暂无结果")
        self._append_log(f"切换到{mode_text}。")
        self._update_progress_text()

    def _update_progress_text(self):
        if self.current_mode == self.MODE_TRAIN:
            current = len(self.train_group_scans)
            target = self.sample_count_spin.value()
        else:
            current = 0 if self.predict_scan_active else 1 if self.result_name_label.text() not in ("暂无结果", "识别中") else 0
            target = 1
        self.progress_metric_value.setText(f"{current} / {target}")

    def _send_command(self):
        text = self.command_input.text().strip()
        if not text:
            return
        try:
            normalized = self._write_serial_command(text)
        except RuntimeError as exc:
            self._show_native_message(QMessageBox.Warning, "发送失败", str(exc))
            self._append_log(f"发送失败：{exc}")
            return
        except serial.SerialException as exc:
            self._show_native_message(QMessageBox.Critical, "发送失败", f"串口发送异常：{exc}")
            self._append_log(f"串口发送异常：{exc}")
            self._disconnect_serial("串口异常，已自动断开。")
            return

        self._append_log(f"发送指令：{normalized.encode('unicode_escape').decode('ascii')}")
        self.command_input.clear()

    def _clear_logs(self):
        self.log_text.clear()
        self.log_stack.setCurrentIndex(0)

    def _append_log(self, message):
        if self.log_stack.currentIndex() == 0:
            self.log_stack.setCurrentIndex(1)
        self.log_text.append(message)
        if self.history_stack.currentIndex() == 0:
            self.history_stack.setCurrentIndex(1)
        self.history_list.insertItem(0, QListWidgetItem(message))
        while self.history_list.count() > 20:
            self.history_list.takeItem(self.history_list.count() - 1)

    def _exec_native_dialog(self, dialog):
        app = QApplication.instance()
        original_stylesheet = app.styleSheet() if app is not None else ""
        if app is not None:
            app.setStyleSheet("")
        dialog.setStyleSheet("")
        try:
            return dialog.exec()
        finally:
            if app is not None:
                app.setStyleSheet(original_stylesheet)

    def _show_native_message(self, icon, title, text):
        dialog = NativeMessageDialog(title, text, icon, self)
        if not self.windowIcon().isNull():
            dialog.setWindowIcon(self.windowIcon())
        self._exec_native_dialog(dialog)

    def _handle_start_button_clicked(self):
        if not self.connected:
            self._show_native_message(QMessageBox.Warning, "设备未连接", "请先连接设备，再开始采集。")
            self._append_log("开始采集失败：设备未连接。")
            return

        if self.current_mode == self.MODE_TRAIN:
            self._handle_train_collect_action()
            return

        self._start_predict_scan()

    def _handle_train_collect_action(self):
        if self.collecting:
            self._append_log("当前组正在采集中，请等待收满目标次数的完整扫描。")
            return

        self._reset_train_collection_state()
        self.collecting = True
        self.sample_count_spin.setEnabled(False)
        self.start_button.setText("采集中...")
        self.result_name_label.setText("采集中")
        train_path = self._ensure_train_data_file()
        self._append_log(
            f"{self.MODE_TRAIN}开始采集，目标 {self.sample_count_spin.value()} 次完整扫描。"
            f" 数据将追加到：{train_path}"
        )
        if not self._request_scan():
            self._reset_train_collection_state()

    def _prompt_train_label(self):
        dialog = QInputDialog(self)
        dialog.setWindowTitle("手动标注")
        dialog.setLabelText("请选择当前样本标签：")
        dialog.setComboBoxItems(self.TRAIN_LABEL_OPTIONS)
        dialog.setTextValue(self.TRAIN_LABEL_OPTIONS[0])
        dialog.setOkButtonText("确定")
        dialog.setCancelButtonText("取消")
        dialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        if self._exec_native_dialog(dialog) == QDialog.Accepted:
            return dialog.textValue()

        self._show_native_message(QMessageBox.Information, "标注未完成", "请完成手动标注后再提交该次采集。")
        return None

    def _handle_spectrum_value(self, channel, value):
        if self.current_mode == self.MODE_TRAIN:
            if not self.collecting:
                return
        elif self.current_mode == self.MODE_PREDICT:
            if not self.predict_scan_active:
                return
        else:
            return

        self._arm_scan_timeout()
        if channel in self.pending_scan_values:
            self.pending_scan_values.clear()
            self._append_log("检测到重复通道，上一条扫描数据不完整，已作废并重新开始当前次扫描。")

        self.pending_scan_values[channel] = value

        if all(key in self.pending_scan_values for key in SPECTRUM_CHANNELS):
            scan_values = [self.pending_scan_values[key] for key in SPECTRUM_CHANNELS]
            self.pending_scan_values.clear()
            self._handle_complete_scan(scan_values)

    def _append_train_row(self, avg_values, label):
        train_path = self._ensure_train_data_file()
        with train_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow([*(f"{value:.4f}" for value in avg_values), label])

    def _ensure_train_data_file(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        train_path = self.data_dir / TRAIN_DATA_FILENAME
        if not train_path.exists():
            train_path.touch()
            self._append_log(f"已创建训练数据文件：{train_path}")
        return train_path

    def _reset_train_collection_state(self):
        self.collecting = False
        self.pending_scan_values.clear()
        self.train_group_scans.clear()
        self._clear_scan_timeout()
        self.sample_count_spin.setEnabled(True)
        self.start_button.setText("开始识别" if self.current_mode == self.MODE_PREDICT else "开始采集")
        self._update_progress_text()

    @staticmethod
    def _format_scan_values(values):
        return ", ".join(f"{channel}={value:.4f}" for channel, value in zip(SPECTRUM_CHANNELS, values))

    def _start_predict_scan(self):
        if self.predict_scan_active:
            self._append_log("当前正在等待识别结果，请勿重复触发。")
            return

        if self._load_classifier() is None:
            return

        self.predict_scan_active = True
        self.pending_scan_values.clear()
        self.result_name_label.setText("识别中")
        self._update_progress_text()
        self._append_log(f"{self.MODE_PREDICT}开始采集。")
        if not self._request_scan():
            self.predict_scan_active = False
            self.result_name_label.setText("暂无结果")
            self._update_progress_text()

    def _handle_predict_scan_complete(self, scan_values):
        classifier = self._load_classifier()
        if classifier is None:
            self.predict_scan_active = False
            self.result_name_label.setText("模型错误")
            self._update_progress_text()
            return

        try:
            predicted = classifier.predict([scan_values])[0]
            label = get_prediction_label(predicted)
        except Exception as exc:
            self.predict_scan_active = False
            self.result_name_label.setText("预测失败")
            self._show_native_message(QMessageBox.Critical, "预测失败", f"执行模型预测失败：{exc}")
            self._append_log(f"执行模型预测失败：{exc}")
            self._update_progress_text()
            return

        self.predict_scan_active = False
        self._clear_scan_timeout()
        self.result_name_label.setText(str(label))
        self._append_log(f"识别结果：{label}，光谱：{self._format_scan_values(scan_values)}")
        self._update_progress_text()

    def _request_scan(self):
        try:
            self._write_serial_command(SCAN_COMMAND)
        except RuntimeError as exc:
            self._show_native_message(QMessageBox.Warning, "无法采集", str(exc))
            self._append_log(f"无法采集：{exc}")
            return False
        except serial.SerialException as exc:
            self._show_native_message(QMessageBox.Critical, "采集失败", f"发送扫描指令失败：{exc}")
            self._append_log(f"发送扫描指令失败：{exc}")
            self._disconnect_serial("串口异常，已自动断开。")
            return False

        self._arm_scan_timeout()
        self._append_log("已发送扫描指令：sc\\r\\n")
        return True

    def _write_serial_command(self, text):
        if not self.connected or self.serial_port is None:
            raise RuntimeError("设备未连接，请先打开串口。")

        normalized = self._normalize_command_text(text)
        self.serial_port.write(normalized.encode("utf-8"))
        self.serial_port.flush()
        return normalized

    @staticmethod
    def _normalize_command_text(text):
        return (
            text.replace("\\r", "\r")
            .replace("\\n", "\n")
            .replace("/r", "\r")
            .replace("/n", "\n")
        )

    def _poll_serial_data(self):
        if self.serial_port is None or not self.connected:
            return

        try:
            waiting = self.serial_port.in_waiting
            if waiting <= 0:
                return
            chunk = self.serial_port.read(waiting).decode("utf-8", errors="ignore")
        except serial.SerialException as exc:
            self._append_log(f"串口读取异常：{exc}")
            self._show_native_message(QMessageBox.Critical, "串口异常", f"读取串口数据失败：{exc}")
            self._disconnect_serial("串口异常，已自动断开。")
            return

        if not chunk:
            return

        stripped = chunk.strip()
        if stripped:
            self._append_log(f"接收数据：{stripped}")

        self.serial_buffer += chunk
        last_complete = self.serial_buffer.rfind("]")
        if last_complete < 0:
            if len(self.serial_buffer) > 256:
                self.serial_buffer = self.serial_buffer[-256:]
            return

        completed_text = self.serial_buffer[: last_complete + 1]
        self.serial_buffer = self.serial_buffer[last_complete + 1 :]
        self._process_serial_payload(completed_text)

    def _process_serial_payload(self, text):
        for channel, raw_value in SPECTRUM_VALUE_PATTERN.findall(text):
            self._handle_spectrum_value(channel, float(raw_value))

    def _load_classifier(self, silent=False):
        model_path = self.model_path.expanduser()
        if self.loaded_model is not None and self.loaded_model_path == model_path:
            return self.loaded_model

        try:
            self.loaded_model = SpectrumClassifier.load(str(model_path))
            self.loaded_model_path = model_path
            if not silent:
                self._append_log(f"模型加载成功：{model_path}")
            return self.loaded_model
        except FileNotFoundError:
            self.loaded_model = None
            self.loaded_model_path = None
            if not silent:
                self._show_native_message(QMessageBox.Warning, "模型不存在", f"未找到模型文件：{model_path}")
                self._append_log(f"未找到模型文件：{model_path}")
        except Exception as exc:
            self.loaded_model = None
            self.loaded_model_path = None
            if not silent:
                self._show_native_message(QMessageBox.Critical, "模型加载失败", f"加载模型失败：{exc}")
                self._append_log(f"加载模型失败：{exc}")
        return None

    def _update_connection_status(self, connected):
        if not connected:
            status = "offline"
            status_text = "离线"
        else:
            status = "online"
            status_text = "设备在线"
        self.connection_metric_value.setText(status_text)
        self.connection_metric_dot.setProperty("status", status)
        self.connection_metric_dot.style().unpolish(self.connection_metric_dot)
        self.connection_metric_dot.style().polish(self.connection_metric_dot)
        self.connect_button.setText("断开连接" if connected else "连接设备")

    def _disconnect_serial(self, log_message=None):
        self.serial_timer.stop()
        self._clear_scan_timeout()
        self.connected = False
        self.collecting = False
        self.predict_scan_active = False
        self.pending_scan_values.clear()
        self.serial_buffer = ""

        if self.serial_port is not None:
            try:
                if self.serial_port.is_open:
                    self.serial_port.close()
            except serial.SerialException:
                pass
            finally:
                self.serial_port = None

        self.sample_count_spin.setEnabled(True)
        self.start_button.setText("开始识别" if self.current_mode == self.MODE_PREDICT else "开始采集")
        self._update_connection_status(False)
        self._update_progress_text()
        if log_message:
            self._append_log(log_message)

    def _handle_complete_scan(self, scan_values):
        self._clear_scan_timeout()
        self.pending_scan_values.clear()
        if self.current_mode == self.MODE_PREDICT:
            self._handle_predict_scan_complete(scan_values)
            return

        self._handle_train_scan_complete(scan_values)

    def _handle_train_scan_complete(self, scan_values):
        self.train_group_scans.append(scan_values)
        self._update_progress_text()
        current = len(self.train_group_scans)
        target = self.sample_count_spin.value()
        self._append_log(
            f"已接收第 {current}/{target} 次完整扫描："
            f"{self._format_scan_values(scan_values)}"
        )

        if current < target:
            self._request_scan()
            return

        avg_values = [
            sum(scan[index] for scan in self.train_group_scans) / current
            for index in range(len(SPECTRUM_CHANNELS))
        ]
        self._append_log(f"当前组平均值：{self._format_scan_values(avg_values)}")
        self.result_name_label.setText("等待标注")

        label = self._prompt_train_label()
        if label is None:
            self._append_log("未完成标注，当前组数据已作废，不会写入训练集。")
            self.result_name_label.setText("已作废")
            self._reset_train_collection_state()
            return

        self._append_train_row(avg_values, label)
        self.saved_group_count += 1
        self.result_name_label.setText(label)
        self._append_log(
            f"第 {self.saved_group_count} 组样本已保存，标签：{label}，"
            f"均值：{self._format_scan_values(avg_values)}"
        )
        self._reset_train_collection_state()

    def _arm_scan_timeout(self):
        if self.collecting or self.predict_scan_active:
            self.scan_timeout_timer.start()

    def _clear_scan_timeout(self):
        self.scan_timeout_timer.stop()

    def _handle_scan_timeout(self):
        self.pending_scan_values.clear()
        if self.predict_scan_active:
            self.predict_scan_active = False
            self.result_name_label.setText("采集超时")
            self._append_log("等待扫描结果超时，本次识别已取消。")
            self._show_native_message(QMessageBox.Warning, "采集超时", "设备未在规定时间内返回完整光谱，本次识别已取消。")
            self._update_progress_text()
            return

        if not self.collecting:
            return

        collected_count = len(self.train_group_scans)
        self.result_name_label.setText("采集超时")
        if collected_count > 0:
            self._append_log(
                f"等待第 {collected_count + 1} 次扫描结果超时，当前组已丢弃前面 {collected_count} 次已采集结果。"
            )
        else:
            self._append_log("等待训练扫描结果超时，当前组采集已取消。")
        self._show_native_message(QMessageBox.Warning, "采集超时", "设备未在规定时间内返回完整光谱，当前训练组已取消。")
        self._reset_train_collection_state()

    def _get_serial_bytesize(self):
        return {
            "5": serial.FIVEBITS,
            "6": serial.SIXBITS,
            "7": serial.SEVENBITS,
            "8": serial.EIGHTBITS,
        }[self.data_bits_combo.currentText()]

    def _get_serial_parity(self):
        return {
            "奇校验": serial.PARITY_ODD,
            "偶校验": serial.PARITY_EVEN,
            "无": serial.PARITY_NONE,
        }[self.parity_combo.currentText()]

    def _get_serial_stopbits(self):
        return {
            "1": serial.STOPBITS_ONE,
            "1.5": serial.STOPBITS_ONE_POINT_FIVE,
            "2": serial.STOPBITS_TWO,
        }[self.stop_bits_combo.currentText()]

    def closeEvent(self, event):
        self._disconnect_serial()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SerialAssistant()
    window.show()
    sys.exit(app.exec_())
