import sys
from PyQt5.QtWidgets import QApplication
from knn import KNN
from ui import SerialAssistant
from QCandyUi import CandyWindow


def main():
    app = QApplication(sys.argv)
    main_win = SerialAssistant()
    candy_window = CandyWindow.createWindow(main_win, theme='blueDeep', title='塑料识别系统')
    candy_window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())

