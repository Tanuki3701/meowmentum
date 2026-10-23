"""毛玻璃右鍵選單：系統原生模糊 + 透明漸層 + 像素圖示，子選單零延遲。"""
import os
import tempfile

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QMenu, QProxyStyle, QStyle

import macos
import pixel

RADIUS = 12

QSS_GLASS = """
QMenu {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(255, 255, 255, 222), stop:1 rgba(252, 246, 238, 200));
    border: 1px solid rgba(255, 255, 255, 230);
    border-radius: %(r)dpx;
    padding: 6px 5px;
}
""" % {"r": RADIUS}

QSS_PLAIN = """
QMenu {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(252, 252, 255, 238), stop:1 rgba(246, 240, 232, 228));
    border: 1px solid rgba(255, 255, 255, 200);
    border-radius: %(r)dpx;
    padding: 6px 5px;
}
""" % {"r": RADIUS}

QSS_ITEMS = """
QMenu::item {
    color: #2d2a2e;
    font-size: 13px;
    padding: 5px 22px 5px 6px;
    margin: 0px 1px;
    border-radius: 7px;
    background: transparent;
}
QMenu::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(255, 255, 255, 215), stop:1 rgba(255, 255, 255, 140));
    color: #1d1b1f;
}
QMenu::item:disabled { color: rgba(45, 42, 46, 110); }
QMenu::icon { padding-left: 6px; }
QMenu::separator {
    height: 1px;
    margin: 5px 10px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(60, 55, 70, 0), stop:0.5 rgba(60, 55, 70, 55), stop:1 rgba(60, 55, 70, 0));
}
QMenu::right-arrow { width: 8px; height: 8px; margin-right: 6px; }
"""


class MenuStyle(QProxyStyle):
    """去掉選單的各種延遲與動畫。"""

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint in (QStyle.SH_Menu_SubMenuPopupDelay, QStyle.SH_Menu_SloppySubMenus,
                    QStyle.SH_Menu_SubMenuSloppyCloseTimeout, QStyle.SH_Menu_FadeOutOnHide,
                    QStyle.SH_Menu_FlashTriggeredItem):
            return 0
        if hint == QStyle.SH_Menu_MouseTracking:
            return 1
        return super().styleHint(hint, option, widget, returnData)

    def pixelMetric(self, metric, option=None, widget=None):
        if metric == QStyle.PM_SmallIconSize:
            return 18
        return super().pixelMetric(metric, option, widget)


_mask_path = None


def _mask():
    """給系統毛玻璃用的圓角遮罩圖。"""
    global _mask_path
    if _mask_path is None:
        size = RADIUS * 2 + 2
        img = QImage(size, size, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, size, size), RADIUS, RADIUS)
        p.fillPath(path, QColor(0, 0, 0))
        p.end()
        _mask_path = os.path.join(tempfile.gettempdir(), "meowmentum-glass-mask.png")
        img.save(_mask_path)
    return _mask_path


def install(app):
    QApplication.setEffectEnabled(Qt.UI_AnimateMenu, False)
    QApplication.setEffectEnabled(Qt.UI_FadeMenu, False)
    app.setStyle(MenuStyle())


class GlassMenu(QMenu):
    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet((QSS_GLASS if macos.GLASS_AVAILABLE else QSS_PLAIN) + QSS_ITEMS)
        self._glass = False

    def showEvent(self, e):
        super().showEvent(e)
        if macos.GLASS_AVAILABLE and not self._glass:
            self._glass = True
            QTimer.singleShot(0, lambda: macos.apply_glass(self, _mask(), RADIUS))

    def sub(self, icon_name, text):
        m = GlassMenu(text, self)
        m.setIcon(pixel.icon(icon_name) if isinstance(icon_name, str) else icon_name)
        self.addMenu(m)
        return m

    def item(self, icon_name, text, slot):
        act = self.addAction(text)
        if icon_name is not None:
            act.setIcon(pixel.icon(icon_name) if isinstance(icon_name, str) else icon_name)
        act.triggered.connect(lambda _=False: slot())
        return act

    def choices(self, options, current, handler, icons=None, checked_icons=None):
        """單選清單：目前選中的用勾勾圖示標示。"""
        for value, label in options.items():
            if value == current:
                ic = (checked_icons or {}).get(value) or pixel.icon("check")
            elif icons and value in icons:
                ic = icons[value]
            else:
                ic = pixel.blank_icon()
            act = self.addAction(ic, label)
            act.triggered.connect(lambda _=False, v=value: handler(v))
