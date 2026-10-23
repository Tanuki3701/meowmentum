"""貓咪頭上的小視窗：對話泡泡、番茄鐘倒數、愛心和 Zzz 特效。

這個視窗完全不接收滑鼠（點擊會穿過去），而且只有在有東西要顯示時才出現。
"""
import random

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

import sprites
from macos import show_on_all_spaces

INK = QColor(58, 55, 55)        # 和貓咪外框同色
PAPER = QColor(255, 252, 244)
FX_INTERVAL = 140               # 特效動畫間隔（只在有特效時跑）


class Overlay(QWidget):
    W, H = 280, 170

    def __init__(self, cat):
        super().__init__(None)
        self.cat = cat
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                            | Qt.WindowTransparentForInput | Qt.NoDropShadowWindowHint
                            | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(self.W, self.H)

        self.text = None
        self.label = None
        self.effects = []  # [kind, x, y, 剩餘步數]
        self._spaces_done = False

        self.text_timer = QTimer(self)
        self.text_timer.setSingleShot(True)
        self.text_timer.timeout.connect(self._clear_text)
        self.fx_timer = QTimer(self)
        self.fx_timer.setTimerType(Qt.CoarseTimer)
        self.fx_timer.setInterval(FX_INTERVAL)
        self.fx_timer.timeout.connect(self._step_effects)

        self.font = QFont()
        self.font.setPointSize(13)
        self.font.setBold(True)

    # ---------------- 對外 API ---------------- #
    def say(self, text, ms=4500):
        self.text = text
        self.text_timer.start(ms)
        self._refresh()

    def set_label(self, text):
        if text != self.label:
            self.label = text
            self._refresh()

    def burst(self, kind="heart", n=3):
        cx = self.W / 2
        base = self._head_y()
        for i in range(n):
            self.effects.append([kind, cx + random.uniform(-40, 40), base - random.uniform(0, 12),
                                 random.randint(7, 10)])
        if not self.fx_timer.isActive():
            self.fx_timer.start()
        self._refresh()

    def zzz(self):
        self.effects.append(["zzz", self.W / 2 + 30, self._head_y(), 9])
        if not self.fx_timer.isActive():
            self.fx_timer.start()
        self._refresh()

    def follow(self):
        if self.isVisible():
            c = self.cat
            self.move(c.x() + c.width() // 2 - self.W // 2,
                      c.y() + c.content_top() - self.H + 4)

    # ---------------- 內部 ---------------- #
    def _head_y(self):
        return self.H - 14

    def _clear_text(self):
        self.text = None
        self._refresh()

    def _step_effects(self):
        alive = []
        for fx in self.effects:
            fx[2] -= 6 if fx[0] == "heart" else 5
            if fx[0] == "zzz":
                fx[1] += 3
            fx[3] -= 1
            if fx[3] > 0:
                alive.append(fx)
        self.effects = alive
        if not alive:
            self.fx_timer.stop()
        self._refresh()

    def _refresh(self):
        need = bool(self.text or self.label or self.effects)
        if need and not self.isVisible():
            self.show()
            if not self._spaces_done:
                show_on_all_spaces(self)
                self._spaces_done = True
            self.follow()
        elif not need and self.isVisible():
            self.hide()
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        lines = [t for t in (self.label, self.text) if t]
        lift = 0
        if lines:
            p.setFont(self.font)
            fm = QFontMetrics(self.font)
            tw = max(fm.horizontalAdvance(t) for t in lines) + 24
            th = fm.height() * len(lines) + 14
            tw = min(tw, self.W - 8)
            r = QRectF((self.W - tw) / 2, self.H - th - 12, tw, th)
            path = QPainterPath()
            path.addRoundedRect(r, 10, 10)
            tail = QPainterPath()
            cx = self.W / 2
            tail.moveTo(cx - 7, r.bottom() - 1)
            tail.lineTo(cx, r.bottom() + 9)
            tail.lineTo(cx + 7, r.bottom() - 1)
            path = path.united(tail)
            p.setPen(QPen(INK, 2))
            p.setBrush(PAPER)
            p.drawPath(path)
            p.setPen(INK)
            p.drawText(r, Qt.AlignCenter, "\n".join(lines))
            lift = th + 8  # 有泡泡時，特效從泡泡上方飄出
        scale = max(2, self.cat.scale - 1)
        for kind, x, y, _ in self.effects:
            pm = sprites.effect(kind, scale)
            p.drawPixmap(int(x - pm.width() / pm.devicePixelRatio() / 2),
                         int(y - lift - pm.height() / pm.devicePixelRatio()), pm)
