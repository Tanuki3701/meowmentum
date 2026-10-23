import signal
import sys

from PySide6.QtWidgets import QApplication

import glassmenu
from controller import Controller
from macos import hide_dock_icon


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DesktopCat")
    app.setQuitOnLastWindowClosed(False)
    hide_dock_icon()
    glassmenu.install(app)   # 選單零延遲、關閉動畫

    # 從終端機執行時，Ctrl+C 可以直接結束
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    ctrl = Controller()  # noqa: F841  (保持參照，避免被回收)
    app.aboutToQuit.connect(lambda: [c.save_pos() for c in ctrl.cats])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
