import os
from pathlib import Path
import sys
import ctypes

import PyQt5


def configure_qt_runtime():
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

    return plugin_root


QT_PLUGIN_ROOT = configure_qt_runtime()

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor, QIcon
from ui import SerialAssistant

APP_ROOT = Path(__file__).resolve().parent
APP_ICON_PNG_PATH = APP_ROOT / "icon" / "logo.png"
APP_ICON_ICO_PATH = APP_ROOT / "icon" / "logo.ico"
APP_USER_MODEL_ID = "PlasticClassification.NIRWorkbench"


def configure_windows_app_id():
    if sys.platform != "win32":
        return

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)


def place_window(window, app):
    screen = app.screenAt(QCursor.pos()) or app.primaryScreen()
    if screen is None:
        return

    available = screen.availableGeometry()
    horizontal_padding = max(available.width() // 14, 56)
    vertical_padding = max(available.height() // 12, 48)
    max_width = max(available.width() - horizontal_padding * 2, 960)
    max_height = max(available.height() - vertical_padding * 2, 640)
    target_width = min(window.width(), max_width)
    target_height = min(window.height(), max_height)
    window.resize(target_width, target_height)

    frame = window.frameGeometry()
    frame.moveCenter(available.center())
    window.move(frame.topLeft())


def load_app_icon():
    if APP_ICON_ICO_PATH.exists():
        icon = QIcon(str(APP_ICON_ICO_PATH))
        if not icon.isNull():
            return icon
    return QIcon()


def main():
    configure_windows_app_id()
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("Plastic Classification Workstation")
    app_icon = load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
    if QT_PLUGIN_ROOT.exists():
        app.addLibraryPath(str(QT_PLUGIN_ROOT))
    main_win = SerialAssistant()
    if not app_icon.isNull():
        main_win.setWindowIcon(app_icon)
    place_window(main_win, app)
    main_win.show()
    main_win.showNormal()
    main_win.raise_()
    main_win.activateWindow()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
