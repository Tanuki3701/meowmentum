"""貓咪頭上的小視窗：像素風對話框、番茄鐘倒數、愛心和 Zzz 特效。

這個視窗完全不接收滑鼠（點擊會穿過去），而且只有在有東西要顯示時才出現。
"""
import random

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget

import pixel
import sprites
from macos import show_on_all_spaces

FX_INTERVAL = 33    # 特效動畫間隔（只在有特效時跑；約 30fps 才順）
FX_K = FX_INTERVAL / 140   # 以前 140ms 一步的速度
U = 2               # 對話框的像素單位
PAD = 9
MAX_TEXT_W = 250


class Overlay(QWidget):
    W, H = 300, 190

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
        self.tag = None            # 滑鼠移到貓咪身上時顯示的名牌
        self.label = None          # (pixmap, 文字)，例如番茄 + 倒數
        self.effects = []          # [kind, x, y, 剩餘步數]
        self._spaces_done = False
        self.font = pixel.font(12)
        self.fm = QFontMetrics(self.font)

        self.text_timer = QTimer(self)
        self.text_timer.setSingleShot(True)
        self.text_timer.timeout.connect(self._clear_text)
        self.fx_timer = QTimer(self)
        self.fx_timer.setTimerType(Qt.PreciseTimer)
        self.fx_timer.setInterval(FX_INTERVAL)
        self.fx_timer.timeout.connect(self._step_effects)

    # ---------------- 對外 API ---------------- #
    def say(self, text, ms=4500):
        self.text = text
        self.text_timer.start(ms)
        self._refresh()

    def set_tag(self, tag):
        if tag != self.tag:
            self.tag = tag
            self._refresh()

    def set_label(self, label):
        self.label = label
        self._refresh()

    def burst(self, kind="heart", n=3):
        for _ in range(n):
            self.effects.append([kind, self.W / 2 + random.uniform(-40, 40),
                                 self.H - 14 - random.uniform(0, 12), random.randint(7, 10)])
        self._start_fx()

    def zzz(self):
        self.effects.append(["zzz", self.W / 2 + 30, self.H - 14, 9])
        self._start_fx()

    def follow(self):
        if self.isVisible():
            c = self.cat
            self.move(c.x() + c.width() // 2 - self.W // 2,
                      c.y() + c.content_top() - self.H + 4)

    # ---------------- 內部 ---------------- #
    def _start_fx(self):
        if not self.fx_timer.isActive():
            self.fx_timer.start()
        self._refresh()

    def _clear_text(self):
        self.text = None
        self._refresh()

    def _step_effects(self):
        alive = []
        for fx in self.effects:
            fx[2] -= (6 if fx[0] == "heart" else 5) * FX_K
            if fx[0] == "zzz":
                fx[1] += 3 * FX_K
            fx[3] -= FX_K
            if fx[3] > 0:
                alive.append(fx)
        self.effects = alive
        if not alive:
            self.fx_timer.stop()
        self._refresh()

    def _refresh(self):
        need = bool(self.text or self.label or self.effects or self.tag)
        if self.cat.ctrl.all_hidden:
            need = False
        if need and not self.isVisible():
            self.show()
            if not self._spaces_done:
                show_on_all_spaces(self)
                self._spaces_done = True
            self.follow()
        elif not need and self.isVisible():
            self.hide()
        self.update()

    def _layout(self):
        """算出對話框大小與各行位置。"""
        rows = []
        if self.label:
            pm, t = self.label
            iw = pm.width() / pm.devicePixelRatio()
            ih = pm.height() / pm.devicePixelRatio()
            rows.append(("label", int(iw + 6 + self.fm.horizontalAdvance(t)), int(max(ih, self.fm.height()))))
        if self.text:
            r = self.fm.boundingRect(QRect(0, 0, MAX_TEXT_W, 400), Qt.TextWordWrap, self.text)
            rows.append(("text", r.width(), r.height()))
        elif self.tag and not self.label:
            rows.append(("tag", self.fm.horizontalAdvance(self.tag), self.fm.height()))
        if not rows:
            return None, rows
        w = max(r[1] for r in rows) + PAD * 2 + U * 2
        h = sum(r[2] for r in rows) + 4 * (len(rows) - 1) + PAD * 2 - 2
        w += w % U
        h += h % U
        box = QRect((self.W - w) // 2 // U * U, self.H - h - 14, w, h)
        return box, rows

    def paintEvent(self, _e):
        p = QPainter(self)
        box, rows = self._layout()
        lift = 0
        is_tag = box and rows[0][0] == "tag"
        if is_tag:                                   # 名牌：薄荷綠小牌子，沒有尾巴
            box = QRect(box.left() + 4, box.top() + 10, box.width() - 8, box.height() - 6)
            pixel.draw_box(p, box, U, fill=QColor(196, 236, 226), light=QColor(232, 250, 244))
            p.setFont(self.font)
            p.setPen(pixel.INK)
            p.drawText(box, Qt.AlignCenter, self.tag)
            box = None
            lift = 26
        if box:
            pixel.draw_box(p, box, U)
            pixel.draw_tail(p, self.W // 2 // U * U, box.bottom() + 1 - U, U)
            p.setFont(self.font)
            p.setPen(pixel.INK)
            y = box.top() + PAD
            for kind, w, h in rows:
                x = box.left() + (box.width() - w) // 2
                if kind == "label":
                    pm, t = self.label
                    ih = pm.height() / pm.devicePixelRatio()
                    p.drawPixmap(x, int(y + (h - ih) / 2), pm)
                    tx = x + int(pm.width() / pm.devicePixelRatio()) + 6
                    p.drawText(QRect(tx, y, w, h), Qt.AlignVCenter | Qt.AlignLeft, t)
                else:
                    p.drawText(QRect(box.left() + PAD, y, box.width() - 2 * PAD, h),
                               Qt.AlignCenter | Qt.TextWordWrap, self.text)
                y += h + 4
            lift = box.height() + 8
        scale = max(2, self.cat.scale - 1)
        for kind, x, y, _ in self.effects:
            pm = sprites.effect(kind, scale)
            p.drawPixmap(int(x - pm.width() / pm.devicePixelRatio() / 2),
                         int(y - lift - pm.height() / pm.devicePixelRatio()), pm)
