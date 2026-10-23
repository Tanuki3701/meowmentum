"""貓屋：貓咪可以回家睡覺，或從門窗探出頭來。

省電：沒有貓咪在家時完全沒有計時器；有貓咪在家時每 1.4 秒才更新一次，
只有探頭的那一下才會短暫跑動畫。
"""
import random

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

import sprites
from i18n import tr
from macos import show_on_all_spaces

U = 3                      # 貓屋的像素放大倍數
W, H = 48, 46
GROUND = 43                # 草皮頂端（貓咪腳踩的位置）


class House(QWidget):
    def __init__(self, ctrl):
        super().__init__(None)
        self.ctrl = ctrl
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                            | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(W * U, H * U)
        self.residents = []        # 在家的貓
        self.state = {}            # cat -> {"slot", "mode": peek/sleep, "rise": 0..8}
        self._press = None
        self._tick_n = 0
        self._spaces_done = False

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.CoarseTimer)
        self.timer.setInterval(1400)
        self.timer.timeout.connect(self._tick)
        self.anim = QTimer(self)
        self.anim.setTimerType(Qt.CoarseTimer)
        self.anim.setInterval(70)
        self.anim.timeout.connect(self._animate)

        pos = ctrl.settings.value("house_pos")
        if isinstance(pos, QPoint) and QGuiApplication.screenAt(pos):
            self.move(pos)
        else:
            r = QGuiApplication.primaryScreen().availableGeometry()
            self.move(r.left() + 40, r.bottom() + 1 - GROUND * U)

    # ---------------- 顯示 ---------------- #
    def show_house(self):
        if not self.isVisible():
            self.show()
            if not self._spaces_done:
                show_on_all_spaces(self)
                self._spaces_done = True
        self.ctrl.settings.setValue("house_visible", "1")

    def hide_house(self):
        if self.residents:
            self.ctrl.come_out()
        self.hide()
        self.ctrl.settings.setValue("house_visible", "0")

    def door_cat_pos(self, cat):
        """貓咪站在門口時，貓咪視窗的左上角座標。"""
        dx, dy, dw, dh = sprites.HOUSE_SLOTS["door"]
        x = self.x() + (dx + dw / 2) * U - cat.width() / 2
        y = self.y() + GROUND * U - (cat.height() - cat.foot_off())
        return x, y

    # ---------------- 住戶 ---------------- #
    def add(self, cat):
        if cat in self.residents:
            return
        used = {s["slot"] for s in self.state.values()}
        free = [k for k in sprites.SLOT_ORDER if k not in used]
        slot = free[0] if free else random.choice(sprites.SLOT_ORDER)
        self.residents.append(cat)
        self.state[cat] = {"slot": slot, "mode": "peek", "rise": 0}
        self.show_house()
        self.timer.start()
        self.anim.start()
        self.update()

    def remove(self, cat):
        if cat in self.residents:
            self.residents.remove(cat)
            self.state.pop(cat, None)
        if not self.residents:
            self.timer.stop()
            self.anim.stop()
        self.update()

    def _tick(self):
        """偶爾換一下：有的貓去睡覺，有的探出頭來看看。"""
        self._tick_n += 1
        for cat, st in self.state.items():
            if random.random() < 0.25:
                st["mode"] = "sleep" if st["mode"] == "peek" else "peek"
                if st["mode"] == "peek":
                    st["rise"] = 0
                    self.anim.start()
        self.update()

    def _animate(self):
        moving = False
        for st in self.state.values():
            if st["mode"] == "peek" and st["rise"] < 8:
                st["rise"] += 1
                moving = True
        if not moving:
            self.anim.stop()
        self.update()

    # ---------------- 繪圖 ---------------- #
    def paintEvent(self, _e):
        p = QPainter(self)
        p.drawPixmap(0, 0, sprites.house(U))
        for cat, st in self.state.items():
            x, y, w, h = sprites.HOUSE_SLOTS[st["slot"]]
            hole = QRect(x * U, y * U, w * U, h * U)
            if st["mode"] == "peek":
                pm = sprites.face(cat.color, "peek", U)
                fw = pm.width() / pm.devicePixelRatio()
                fh = pm.height() / pm.devicePixelRatio()
                rise = min(fh, h * U) * st["rise"] / 8
                p.save()
                p.setClipRect(hole)
                p.drawPixmap(int(hole.center().x() - fw / 2 + 1), int(hole.bottom() + 1 - rise), pm)
                p.restore()
            else:
                zz = sprites.effect("zzz", 2)
                bob = (self._tick_n % 2) * 3
                p.drawPixmap(hole.right() - 6, hole.top() - 10 - bob, zz)

    # ---------------- 滑鼠 ---------------- #
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            gp = e.globalPosition().toPoint()
            self._press = (gp, gp - self.pos(), False)

    def mouseMoveEvent(self, e):
        if not self._press:
            return
        gp = e.globalPosition().toPoint()
        start, off, dragging = self._press
        if dragging or (gp - start).manhattanLength() > 5:
            self._press = (start, off, True)
            self.move(gp - off)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self._press:
            return
        dragging = self._press[2]
        self._press = None
        if dragging:
            self.ctrl.settings.setValue("house_pos", self.pos())
        elif self.residents:
            self.ctrl.come_out()
        else:
            self.ctrl.go_home_all()

    def contextMenuEvent(self, e):
        from glassmenu import GlassMenu
        menu = GlassMenu()
        if self.residents:
            menu.item("paw", tr("come_out"), self.ctrl.come_out)
        else:
            menu.item("home", tr("go_home_all"), self.ctrl.go_home_all)
        menu.item("close", tr("house_hide"), self.hide_house)
        menu.exec(e.globalPos())
