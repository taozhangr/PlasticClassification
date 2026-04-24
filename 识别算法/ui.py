import csv
from datetime import datetime
from html import escape
import os
from pathlib import Path
import re
import sys
try:
    import winreg
except ImportError:
    winreg = None

import PyQt5
import serial
from serial.tools import list_ports

from PyQt5.QtCore import QPointF, QRectF, QSize, QTimer, Qt
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPolygonF
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
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
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
APP_LOGO_PATH = APP_ROOT / "icon" / "logo.ico"
TRAIN_DATA_FILENAME = "train_data.csv"
SPECTRUM_CHANNELS = ("R", "S", "T", "U", "V", "W")
SPECTRUM_VALUE_PATTERN = re.compile(r"([RSTUVW])\[(-?\d+(?:\.\d+)?)\]")
SCAN_COMMAND = "action\r\n"
SCAN_TIMEOUT_MS = 5000
WAVELENGTH_RANGE_TEXT = "610-860 nm"

SPACING_8 = 8
SPACING_12 = 12
SPACING_16 = 16
SPACING_20 = 20
ICON_BLUE = "#2563eb"


def _com_sort_key(port_name):
    match = re.fullmatch(r"COM(\d+)", port_name.upper())
    if match:
        return (0, int(match.group(1)))
    return (1, port_name)


def _list_registry_serial_ports():
    if winreg is None or sys.platform != "win32":
        return []

    ports = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM") as key:
            index = 0
            while True:
                try:
                    _, port_name, _ = winreg.EnumValue(key, index)
                except OSError:
                    break
                if isinstance(port_name, str) and port_name.upper().startswith("COM"):
                    ports.append(port_name)
                index += 1
    except OSError:
        return []

    return sorted(set(ports), key=_com_sort_key)


def _list_available_serial_ports():
    ports = {}
    for port in list_ports.comports():
        ports[port.device] = f"{port.device} - {port.description}"

    # 部分虚拟串口只写入 SERIALCOMM 注册表，pyserial 的 PnP 枚举拿不到。
    for port_name in _list_registry_serial_ports():
        ports.setdefault(port_name, f"{port_name} - 虚拟串口")

    return [(port_name, ports[port_name]) for port_name in sorted(ports, key=_com_sort_key)]

LIGHT_STYLESHEET = """
QMainWindow { background: #f5f7fb; }
QWidget {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "SimHei";
    font-size: 11px;
    color: #24324a;
}
QFrame#surface { background: transparent; border: none; }
QFrame#card, QFrame#metricCard, QFrame#resultInfoCard {
    background: #ffffff;
    border: 1px solid #e3e9f2;
    border-radius: 12px;
}
QFrame#divider {
    background: #e8edf5;
    border: none;
    min-height: 1px;
    max-height: 1px;
}
QLabel#infoTitle { font-size: 14px; font-weight: 700; color: #1a304d; }
QLabel#sectionTitle { font-size: 15px; font-weight: 700; color: #172846; }
QLabel#fieldLabel { font-size: 11px; font-weight: 600; color: #273955; }
QLabel#subtitle, QLabel#hintText { font-size: 11px; color: #8a97aa; }
QLabel#metricTitle, QLabel#valueTitle, QLabel#mutedText { font-size: 11px; color: #7c8aa0; }
QLabel#metricValue { font-size: 13px; font-weight: 700; color: #14243c; }
QLabel#metricValue[accent="warning"] { color: #f59f00; }
QLabel#resultName {
    font-size: 17px;
    font-weight: 700;
    color: #2563eb;
}
QLabel#resultHint { font-size: 11px; color: #8a97aa; }
QLabel#emptyTitle { font-size: 13px; font-weight: 700; color: #2563eb; }
QLabel#emptySubtitle { font-size: 11px; color: #8b98ac; }
QLabel#statusDot, QLabel#statusDotMini {
    min-width: 8px; max-width: 8px; min-height: 8px; max-height: 8px;
    border-radius: 4px;
}
QLabel[status="offline"]#statusDot, QLabel[status="offline"]#statusDotMini { background: #b6c2d3; }
QLabel[status="online"]#statusDot, QLabel[status="online"]#statusDotMini { background: #1dbf73; }
QLabel#emptyIcon {
    min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px;
    border-radius: 18px;
    border: 1px solid #d8e3f2;
    color: #93a5bf;
    font-size: 16px;
    font-weight: 700;
}
QPushButton {
    min-height: 30px;
    max-height: 30px;
    border-radius: 7px;
    border: 1px solid #d7e0ec;
    background: #ffffff;
    color: #2b3f5f;
    padding: 0 10px;
    font-size: 12px;
}
QComboBox, QLineEdit {
    min-height: 34px;
    max-height: 34px;
    border-radius: 7px;
    border: 1px solid #d7e0ec;
    background: #ffffff;
    color: #2b3f5f;
    padding: 0 12px;
    font-size: 12px;
}
QComboBox {
    padding-right: 22px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border: none;
    background: transparent;
}
QTextEdit {
    min-height: 108px;
    max-height: 16777215px;
    border-radius: 8px;
    border: 1px solid #d7e0ec;
    background: #ffffff;
    color: #2b3f5f;
    padding: 14px;
    font-size: 12px;
}
QPushButton:hover, QComboBox:hover, QLineEdit:hover {
    border-color: #c3d1e8;
}
QPushButton:disabled, QComboBox:disabled, QLineEdit:disabled {
    color: #9cabbd;
    background: #f8fafd;
    border-color: #dee6f2;
}
QPushButton[role="primary"] {
    min-height: 34px;
    max-height: 34px;
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
    min-height: 30px;
    max-height: 30px;
    background: #ffffff;
    border: 1px solid #d5deeb;
    color: #4e6483;
    font-weight: 600;
}
QPushButton[role="ghost"] {
    min-height: 30px;
    max-height: 30px;
    background: #ffffff;
    border: 1px solid #d6e0ef;
    color: #263a57;
}
QPushButton#settingsButton {
    min-height: 42px;
    max-height: 42px;
    background: #ffffff;
    border: 1px solid #e3e9f2;
    border-radius: 12px;
    color: #1a304d;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#settingsButton:hover {
    background: #f8fafc;
}
QPushButton#startButton {
    min-height: 44px;
    max-height: 44px;
    font-size: 14px;
    border-radius: 8px;
}
QPushButton[role="icon"] {
    min-width: 34px;
    max-width: 34px;
    min-height: 34px;
    max-height: 34px;
    padding: 0;
}
QPushButton[role="mode"] {
    min-height: 36px;
    max-height: 36px;
    background: #f8fafc;
    border: 1px solid #d5deea;
    color: #233752;
    min-width: 104px;
    padding: 0 8px;
    font-weight: 600;
}
QPushButton[role="mode"]:hover {
    background: #f2f6ff;
}
QPushButton[role="mode"]:checked {
    background: #2f66e8;
    border: 1px solid #2f66e8;
    color: #ffffff;
    font-weight: 700;
}
"""


def _draw_icon_pixmap(name, color=ICON_BLUE, size=18, line_width=2):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    scale = size / 24

    def p(x, y):
        return QPointF(x * scale, y * scale)

    def r(x, y, w, h):
        return QRectF(x * scale, y * scale, w * scale, h * scale)

    pen = QPen(QColor(color), max(1, int(line_width * scale)))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    if name == "device":
        painter.drawRoundedRect(r(5, 9, 14, 10), 2 * scale, 2 * scale)
        painter.drawLine(p(8, 9), p(8, 6))
        painter.drawArc(r(8, 3, 8, 8), 0, 180 * 16)
        painter.drawEllipse(r(11, 6, 2, 2))
    elif name == "chart":
        painter.drawRoundedRect(r(4, 4, 16, 16), 2 * scale, 2 * scale)
        painter.drawPolyline(QPolygonF([p(7, 15), p(10, 11), p(13, 13), p(17, 8)]))
        painter.drawLine(p(7, 17), p(17, 17))
    elif name == "file":
        painter.drawRoundedRect(r(6, 3, 12, 18), 1.5 * scale, 1.5 * scale)
        painter.drawLine(p(14, 3), p(18, 7))
        painter.drawLine(p(14, 3), p(14, 7))
        painter.drawLine(p(14, 7), p(18, 7))
        painter.drawLine(p(9, 11), p(15, 11))
        painter.drawLine(p(9, 15), p(15, 15))
    elif name == "trophy":
        painter.drawRoundedRect(r(8, 4, 8, 9), 2 * scale, 2 * scale)
        painter.drawArc(r(4, 6, 6, 6), 90 * 16, 160 * 16)
        painter.drawArc(r(14, 6, 6, 6), -70 * 16, 160 * 16)
        painter.drawLine(p(12, 13), p(12, 17))
        painter.drawLine(p(9, 20), p(15, 20))
        painter.drawLine(p(10, 17), p(14, 17))
    elif name == "link":
        painter.drawArc(r(4, 8, 9, 8), 45 * 16, 270 * 16)
        painter.drawArc(r(11, 8, 9, 8), -135 * 16, 270 * 16)
        painter.drawLine(p(9, 14), p(15, 10))
    elif name == "refresh":
        painter.drawArc(r(5, 5, 14, 14), 40 * 16, 270 * 16)
        painter.drawLine(p(17, 5), p(19, 5))
        painter.drawLine(p(19, 5), p(19, 8))
        painter.drawArc(r(5, 5, 14, 14), 220 * 16, 120 * 16)
    elif name == "target":
        painter.drawEllipse(r(6, 6, 12, 12))
        painter.drawEllipse(r(10, 10, 4, 4))
        painter.drawLine(p(12, 3), p(12, 7))
        painter.drawLine(p(12, 17), p(12, 21))
        painter.drawLine(p(3, 12), p(7, 12))
        painter.drawLine(p(17, 12), p(21, 12))
    elif name == "cube":
        painter.drawPolygon(QPolygonF([p(12, 4), p(19, 8), p(12, 12), p(5, 8)]))
        painter.drawPolygon(QPolygonF([p(5, 8), p(12, 12), p(12, 20), p(5, 16)]))
        painter.drawPolygon(QPolygonF([p(19, 8), p(12, 12), p(12, 20), p(19, 16)]))
    elif name == "info":
        painter.drawEllipse(r(4, 4, 16, 16))
        painter.drawLine(p(12, 11), p(12, 16))
        painter.drawPoint(p(12, 8))
    elif name == "gear":
        painter.drawEllipse(r(8, 8, 8, 8))
        for start, end in (
            ((12, 3), (12, 6)),
            ((12, 18), (12, 21)),
            ((3, 12), (6, 12)),
            ((18, 12), (21, 12)),
            ((5, 5), (7, 7)),
            ((17, 17), (19, 19)),
            ((5, 19), (7, 17)),
            ((17, 7), (19, 5)),
        ):
            painter.drawLine(p(*start), p(*end))
    elif name == "trash":
        painter.drawLine(p(8, 7), p(16, 7))
        painter.drawLine(p(10, 4), p(14, 4))
        painter.drawRoundedRect(r(7, 7, 10, 13), 1.5 * scale, 1.5 * scale)
        painter.drawLine(p(10, 10), p(10, 17))
        painter.drawLine(p(14, 10), p(14, 17))
    elif name == "send":
        painter.drawPolygon(QPolygonF([p(4, 12), p(20, 5), p(13, 20), p(11, 13)]))
        painter.drawLine(p(11, 13), p(20, 5))
    elif name == "play":
        painter.setBrush(QColor(color))
        painter.drawPolygon(QPolygonF([p(9, 6), p(18, 12), p(9, 18)]))
    elif name == "grid":
        for x in (5, 14):
            for y in (5, 14):
                painter.drawRoundedRect(r(x, y, 5, 5), 1.2 * scale, 1.2 * scale)
    elif name == "pulse":
        painter.drawPolyline(QPolygonF([p(3, 12), p(8, 12), p(10, 7), p(14, 17), p(16, 12), p(21, 12)]))
    else:
        painter.drawEllipse(r(6, 6, 12, 12))

    painter.end()
    return pixmap


def _make_icon(name, color=ICON_BLUE, size=18):
    return QIcon(_draw_icon_pixmap(name, color, size))


def _make_checkable_icon(name, normal_color=ICON_BLUE, checked_color="#ffffff", size=18):
    icon = QIcon()
    icon.addPixmap(_draw_icon_pixmap(name, normal_color, size), QIcon.Normal, QIcon.Off)
    icon.addPixmap(_draw_icon_pixmap(name, checked_color, size), QIcon.Normal, QIcon.On)
    return icon


def _make_icon_label(name, size=20, color=ICON_BLUE):
    label = QLabel()
    label.setFixedSize(size, size)
    label.setAlignment(Qt.AlignCenter)
    label.setPixmap(_draw_icon_pixmap(name, color, size))
    return label


class EmptyResultIllustration(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(190, 150)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)

        painter.setBrush(QColor("#dfe9ff"))
        painter.drawEllipse(QRectF(22, 122, 146, 18))

        painter.setBrush(QColor("#e8effc"))
        painter.drawRoundedRect(QRectF(54, 62, 86, 62), 8, 8)

        painter.setBrush(QColor("#afc2e4"))
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(46, 58),
                    QPointF(148, 58),
                    QPointF(158, 82),
                    QPointF(36, 82),
                ]
            )
        )

        painter.setBrush(QColor("#cfdcf3"))
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(62, 58),
                    QPointF(94, 58),
                    QPointF(84, 92),
                    QPointF(48, 82),
                ]
            )
        )
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(100, 58),
                    QPointF(138, 58),
                    QPointF(154, 82),
                    QPointF(112, 92),
                ]
            )
        )

        painter.setBrush(QColor("#c9d7ef"))
        painter.drawEllipse(QRectF(78, 32, 34, 34))
        painter.setBrush(QColor("#dce6fa"))
        painter.drawEllipse(QRectF(106, 52, 34, 34))
        painter.setBrush(QColor("#c0cde3"))
        painter.drawEllipse(QRectF(95, 74, 38, 38))

        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(QRectF(80, 96, 56, 34), 12, 12)

        painter.setBrush(QColor("#bdd0f3"))
        for x, y, radius in ((24, 48, 6), (64, 18, 4), (150, 30, 4), (112, 8, 3)):
            painter.drawEllipse(QRectF(x, y, radius * 2, radius * 2))

        painter.setPen(QPen(QColor("#b8c9ec"), 3))
        painter.drawLine(QPointF(148, 50), QPointF(170, 30))
        painter.drawLine(QPointF(160, 38), QPointF(166, 44))
        painter.drawLine(QPointF(162, 34), QPointF(176, 22))


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
        self.setWindowTitle("光纤光谱识别工作台")
        self.resize(1400, 760)
        self.setMinimumSize(1120, 660)
        self.setStyleSheet(LIGHT_STYLESHEET)

        self.current_mode = self.MODE_PREDICT
        self.connected = False
        self.collecting = False
        self.data_dir = APP_ROOT / "data"
        self.model_path = APP_ROOT / "classifier.pkl"
        self.pending_scan_values = {}
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
        self._append_log("请输入指令或点击“开始识别”进行采集。")

    def _build_ui(self):
        surface = QFrame()
        surface.setObjectName("surface")
        self.setCentralWidget(surface)

        root_layout = QVBoxLayout(surface)
        root_layout.setContentsMargins(16, 14, 16, 16)
        root_layout.setSpacing(12)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)
        content_layout.addWidget(self._build_left_panel())
        content_layout.addWidget(self._build_center_panel(), 1)
        content_layout.addWidget(self._build_right_panel())
        content_layout.setStretch(0, 24)
        content_layout.setStretch(1, 56)
        content_layout.setStretch(2, 20)
        root_layout.addLayout(content_layout, 1)

    def _build_top_bar(self):
        card = QFrame()
        card.setObjectName("topBar")
        card.setFixedHeight(40)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(10)

        logo = self._create_logo_label(24)
        layout.addWidget(logo)

        title = QLabel("光纤光谱识别工作台")
        title.setObjectName("windowTitle")
        layout.addWidget(title)
        layout.addStretch(1)
        return card

    def _build_left_panel(self):
        panel = QWidget()
        panel.setFixedWidth(286)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        device_card, device_layout = self._create_card("设备连接", "选择串口并连接设备", padding=18, spacing=5, icon_name="device")

        port_row = QHBoxLayout()
        port_row.setContentsMargins(0, 0, 0, 0)
        port_row.setSpacing(6)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumContentsLength(8)
        self.port_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        port_row.addWidget(self.port_combo, 1)
        self.refresh_button = QPushButton()
        self.refresh_button.setProperty("role", "icon")
        self.refresh_button.setIcon(_make_icon("refresh"))
        self.refresh_button.setIconSize(QSize(17, 17))
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
        self.connect_button.setIcon(_make_icon("link", "#ffffff"))
        self.connect_button.setIconSize(QSize(17, 17))
        self.connect_button.clicked.connect(self._toggle_connection_state)
        device_layout.addStretch(1)
        device_layout.addWidget(self.connect_button)

        layout.addWidget(device_card, 1)

        collect_card, collect_layout = self._create_card("采集设置", "选择识别与训练模式", padding=18, spacing=10, icon_name="gear")
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.predict_mode_button = QPushButton("识别模式")
        self.predict_mode_button.setProperty("role", "mode")
        self.predict_mode_button.setCheckable(True)
        self.predict_mode_button.setIcon(_make_checkable_icon("target"))
        self.predict_mode_button.setIconSize(QSize(15, 15))
        self.train_mode_button = QPushButton("训练模式")
        self.train_mode_button.setProperty("role", "mode")
        self.train_mode_button.setCheckable(True)
        self.train_mode_button.setIcon(_make_checkable_icon("cube"))
        self.train_mode_button.setIconSize(QSize(15, 15))

        mode_group = QButtonGroup(self)
        mode_group.addButton(self.predict_mode_button)
        mode_group.addButton(self.train_mode_button)
        mode_group.setExclusive(True)

        self.predict_mode_button.clicked.connect(lambda: self._apply_mode(self.MODE_PREDICT))
        self.train_mode_button.clicked.connect(lambda: self._apply_mode(self.MODE_TRAIN))
        mode_row.addWidget(self.predict_mode_button, 1)
        mode_row.addWidget(self.train_mode_button, 1)
        collect_layout.addLayout(mode_row)

        tip_row = QHBoxLayout()
        tip_row.setContentsMargins(0, 6, 0, 0)
        tip_row.setSpacing(6)
        tip_row.addWidget(_make_icon_label("info", 16))
        tip = QLabel("每个样品采集一次完整光谱光源")
        tip.setObjectName("hintText")
        tip_row.addWidget(tip)
        tip_row.addStretch(1)
        collect_layout.addLayout(tip_row)

        layout.addWidget(collect_card)

        self.settings_button = QPushButton("系统设置")
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.setProperty("role", "ghost")
        self.settings_button.setIcon(_make_icon("gear", "#263a57"))
        self.settings_button.setIconSize(QSize(17, 17))
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

        top_card, top_layout = self._create_card(padding=18, spacing=10)
        top_card.setFixedHeight(168)

        status_grid = QGridLayout()
        status_grid.setHorizontalSpacing(8)
        status_grid.setVerticalSpacing(12)

        head_text = QVBoxLayout()
        head_text.setSpacing(5)
        head_subtitle = QLabel("采集光纤光谱并进行识别分析")
        head_subtitle.setObjectName("subtitle")
        head_text.addLayout(self._section_title_row("光谱采集与识别", "chart"))
        head_text.addWidget(head_subtitle)
        status_grid.addLayout(head_text, 0, 0, 1, 2)

        self.start_button = QPushButton("开始识别")
        self.start_button.setObjectName("startButton")
        self.start_button.setProperty("role", "primary")
        self.start_button.setMinimumWidth(176)
        self.start_button.setIcon(_make_icon("play", "#ffffff"))
        self.start_button.setIconSize(QSize(18, 18))
        self.start_button.clicked.connect(self._handle_start_button_clicked)
        
        status_grid.addWidget(self.start_button, 0, 2, 1, 1, alignment=Qt.AlignVCenter | Qt.AlignRight)

        self.connection_metric_value, self.connection_metric_dot = self._create_metric_card("连接状态", "离线", True, "link")
        self.mode_metric_value, _ = self._create_metric_card("模式", "识别模式", False, "grid")
        self.progress_metric_value, _ = self._create_metric_card("采集状态", "待采集", False, "pulse")

        status_grid.addWidget(self._metric_card_holder(self.connection_metric_value, self.connection_metric_dot), 1, 0)
        status_grid.addWidget(self._metric_card_holder(self.mode_metric_value), 1, 1)
        status_grid.addWidget(self._metric_card_holder(self.progress_metric_value), 1, 2)

        status_grid.setColumnStretch(0, 1)
        status_grid.setColumnStretch(1, 1)
        status_grid.setColumnStretch(2, 1)
        
        top_layout.addLayout(status_grid)
        layout.addWidget(top_card, 0) # Fixed height portion

        log_card, log_layout = self._create_card(padding=16, spacing=12)
        log_head = QHBoxLayout()
        log_head.setSpacing(SPACING_8)
        log_head.addLayout(self._section_title_row("实时日志", "file"))
        log_head.addStretch(1)
        clear_button = QPushButton("清空日志")
        clear_button.setProperty("role", "secondary")
        clear_button.setIcon(_make_icon("trash", "#4e6483"))
        clear_button.setIconSize(QSize(16, 16))
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
        self.send_button.setIcon(_make_icon("send", "#ffffff"))
        self.send_button.setIconSize(QSize(18, 18))
        self.send_button.setMinimumWidth(126)
        self.send_button.clicked.connect(self._send_command)
        cmd_row.addWidget(self.command_input, 1)
        cmd_row.addWidget(self.send_button)
        log_layout.addLayout(cmd_row)

        layout.addWidget(log_card, 1)
        return panel

    def _build_right_panel(self):
        panel = QWidget()
        panel.setFixedWidth(300)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        result_card, result_layout = self._create_card("识别结果", padding=18, spacing=12, icon_name="trophy")
        result_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        result_layout.addStretch(2)
        result_layout.addWidget(EmptyResultIllustration(), 0, Qt.AlignCenter)

        self.result_name_label = QLabel("暂无结果")
        self.result_name_label.setObjectName("resultName")
        self.result_name_label.setAlignment(Qt.AlignCenter)
        result_layout.addWidget(self.result_name_label)

        self.result_hint_label = QLabel("请连接设备并开始识别以获取结果")
        self.result_hint_label.setObjectName("resultHint")
        self.result_hint_label.setAlignment(Qt.AlignCenter)
        result_layout.addWidget(self.result_hint_label)

        result_layout.addSpacing(28)
        result_layout.addWidget(self._create_divider())
        result_layout.addSpacing(6)

        info_title = QLabel("结果信息")
        info_title.setObjectName("metricTitle")
        result_layout.addWidget(info_title)
        self.result_category_value = self._create_value_row(result_layout, "识别类别", "--")
        self.result_range_value = self._create_value_row(result_layout, "波长范围", WAVELENGTH_RANGE_TEXT)
        self.result_time_value = self._create_value_row(result_layout, "采集时间", "--")
        self.result_note_value = self._create_value_row(result_layout, "备注信息", "--")
        result_layout.addStretch(1)

        layout.addWidget(result_card, 1)
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

    def _create_card(self, title=None, subtitle=None, padding=SPACING_16, spacing=SPACING_12, icon_name=None):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(padding, padding, padding, padding)
        layout.setSpacing(spacing)
        if title:
            layout.addLayout(self._section_title_row(title, icon_name))
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("subtitle")
            layout.addWidget(subtitle_label)
        return card, layout

    def _section_title_row(self, title, icon_name=None):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        if icon_name:
            row.addWidget(_make_icon_label(icon_name, 22))
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        row.addWidget(title_label)
        row.addStretch(1)
        return row

    def _create_metric_card(self, title, value, with_dot=False, icon_name=None):
        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        dot_label = None
        if with_dot:
            dot_label = QLabel()
            dot_label.setObjectName("statusDotMini")
            dot_label.setProperty("status", "offline")
        value_label.metric_title = title
        value_label.metric_icon_name = icon_name
        return value_label, dot_label

    def _metric_card_holder(self, value_label, dot_label=None):
        card = QFrame()
        card.setObjectName("metricCard")
        card.setMinimumHeight(76)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        if value_label.metric_icon_name:
            title_row.addWidget(_make_icon_label(value_label.metric_icon_name, 16))
        title = QLabel(value_label.metric_title)
        title.setObjectName("metricTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        layout.addLayout(title_row)
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
        block_layout.setSpacing(2)
        block_layout.addWidget(self._field_label(label_text))
        if isinstance(control, QHBoxLayout):
            block_layout.addLayout(control)
        else:
            block_layout.addWidget(control)
        parent_layout.addWidget(block)

    def _create_value_row(self, parent_layout, name, value):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 5, 4, 5)
        row_layout.setSpacing(8)
        title = QLabel(name)
        title.setObjectName("mutedText")
        value_label = QLabel(value)
        value_label.setObjectName("fieldLabel")
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
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
        ports = _list_available_serial_ports()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        if not ports:
            self.port_combo.addItem("无可用串口")
        else:
            selected_index = 0
            for index, (port_name, label) in enumerate(ports):
                self.port_combo.addItem(label, port_name)
                if previous and previous == port_name:
                    selected_index = index
            self.port_combo.setCurrentIndex(selected_index)
        self.port_combo.blockSignals(False)
        if not self.connected:
            self._append_log(f"串口初始化完成，共 {len(ports)} 个可用端口。")

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
        self._set_result_state("暂无结果", "请连接设备并开始识别以获取结果")
        self._append_log(f"切换到{mode_text}。")
        self._update_progress_text()

    def _set_result_state(
        self,
        name,
        hint=None,
        category="--",
        wavelength_range=WAVELENGTH_RANGE_TEXT,
        collected_at="--",
        note="--",
    ):
        self.result_name_label.setText(name)
        self.result_hint_label.setText(hint or "请连接设备并开始识别以获取结果")
        self.result_category_value.setText(category)
        self.result_range_value.setText(wavelength_range)
        self.result_time_value.setText(collected_at)
        self.result_note_value.setText(note)

    def _update_progress_text(self):
        if self.collecting:
            status_text = "采集中"
        elif self.predict_scan_active:
            status_text = "识别中"
        elif self.result_name_label.text() == "等待标注":
            status_text = "待标注"
        elif self.result_name_label.text() not in ("暂无结果", "识别中", "采集中"):
            status_text = "已完成"
        else:
            status_text = "待采集"
        self.progress_metric_value.setText(status_text)
        self.progress_metric_value.setProperty("accent", "warning" if status_text == "待采集" else "")
        self.progress_metric_value.style().unpolish(self.progress_metric_value)
        self.progress_metric_value.style().polish(self.progress_metric_value)

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
        timestamp = datetime.now().strftime("%H:%M:%S")
        safe_message = escape(str(message))
        self.log_text.append(f'<span style="color:{ICON_BLUE};">[{timestamp}]</span>&nbsp;&nbsp;{safe_message}')

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
            self._append_log("当前样品正在采集中，请等待完整扫描返回。")
            return

        self._reset_train_collection_state()
        self.collecting = True
        self.start_button.setText("采集中...")
        self._set_result_state("采集中", "正在等待完整光谱返回", note="训练采集")
        self._update_progress_text()
        train_path = self._ensure_train_data_file()
        self._append_log(
            f"{self.MODE_TRAIN}开始采集，本次样品测量一次。数据将追加到：{train_path}"
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

    def _append_train_row(self, scan_values, label):
        train_path = self._ensure_train_data_file()
        with train_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow([*(f"{value:.4f}" for value in scan_values), label])

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
        self._clear_scan_timeout()
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
        self._set_result_state("识别中", "正在等待完整光谱返回", note="识别采集")
        self._update_progress_text()
        self._append_log(f"{self.MODE_PREDICT}开始采集。")
        if not self._request_scan():
            self.predict_scan_active = False
            self._set_result_state("暂无结果", "请连接设备并开始识别以获取结果")
            self._update_progress_text()

    def _handle_predict_scan_complete(self, scan_values):
        classifier = self._load_classifier()
        if classifier is None:
            self.predict_scan_active = False
            self._set_result_state("模型错误", "请检查模型文件路径", note="模型不可用")
            self._update_progress_text()
            return

        try:
            predicted = classifier.predict([scan_values])[0]
            label = get_prediction_label(predicted)
        except Exception as exc:
            self.predict_scan_active = False
            self._set_result_state("预测失败", "模型预测过程出现异常", note="预测失败")
            self._show_native_message(QMessageBox.Critical, "预测失败", f"执行模型预测失败：{exc}")
            self._append_log(f"执行模型预测失败：{exc}")
            self._update_progress_text()
            return

        self.predict_scan_active = False
        self._clear_scan_timeout()
        self._set_result_state(
            str(label),
            "识别完成",
            category=str(label),
            collected_at=datetime.now().strftime("%H:%M:%S"),
            note="模型预测",
        )
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
        self._append_log("已发送扫描指令：action\\r\\n")
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
        self._append_log(f"已接收当前样品完整扫描：{self._format_scan_values(scan_values)}")
        self.collecting = False
        self.start_button.setText("等待标注")
        self._set_result_state("等待标注", "请选择当前样本标签", note="训练采集")
        self._update_progress_text()

        label = self._prompt_train_label()
        if label is None:
            self._append_log("未完成标注，当前样品数据已作废，不会写入训练集。")
            self._set_result_state("已作废", "当前样品未写入训练集", note="未标注")
            self._reset_train_collection_state()
            return

        self._append_train_row(scan_values, label)
        self.saved_group_count += 1
        self._set_result_state(
            label,
            "训练样本已保存",
            category=label,
            collected_at=datetime.now().strftime("%H:%M:%S"),
            note="训练样本",
        )
        self._append_log(
            f"第 {self.saved_group_count} 个样本已保存，标签：{label}，"
            f"光谱：{self._format_scan_values(scan_values)}"
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
            self._set_result_state("采集超时", "本次识别已取消", note="超时")
            self._append_log("等待扫描结果超时，本次识别已取消。")
            self._show_native_message(QMessageBox.Warning, "采集超时", "设备未在规定时间内返回完整光谱，本次识别已取消。")
            self._update_progress_text()
            return

        if not self.collecting:
            return

        self._set_result_state("采集超时", "当前样品采集已取消", note="超时")
        self._append_log("等待训练扫描结果超时，当前样品采集已取消。")
        self._show_native_message(QMessageBox.Warning, "采集超时", "设备未在规定时间内返回完整光谱，当前样品采集已取消。")
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
