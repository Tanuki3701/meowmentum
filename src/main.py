import signal
import sys

from PySide6.QtWidgets import QApplication

from cat import Cat
from macos import hide_dock_icon, show_on_all_spaces


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DesktopCat")
    app.setQuitOnLastWindowClosed(False)
    hide_dock_icon()

    # 從終端機執行時，Ctrl+C 可以直接結束
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    cat = Cat()
    cat.show()
    show_on_all_spaces(cat)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
