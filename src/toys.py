"""桌面上的小東西：逗貓棒／毛線球、紙箱、貓跳台、貓咪留下的小禮物。

省電：玩具只在拿出來時跟著滑鼠（30fps），收起來就停；家具和禮物不跑任何計時器，
只有貓咪待在紙箱裡時，才每 1.2 秒畫一次呼吸的 Zzz。
"""
import random
import time

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

import art
import sprites
from i18n import tr
from macos import show_on_all_spaces

U = 3
TOY_U = 4
TOY_MS = 16
TOY_LIFETIME = 90          # 玩具拿出來 90 秒後自動收起來


def _base_flags(w, click_through):
    flags = (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.NoDropShadowWindowHint)
    if click_through:
        flags |= Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus
    w.setWindowFlags(flags)
    w.setAttribute(Qt.WA_TranslucentBackground)
    w.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
    w.setAttribute(Qt.WA_ShowWithoutActivating)


# ---------------- 玩具 ---------------- #
class Toy(QWidget):
    """跟著滑鼠的逗貓棒（羽毛垂在游標右下方），或是滾在後面追的毛線球。"""

    def __init__(self, kind, on_done):
        super().__init__(None)
        _base_flags(self, click_through=True)
        self.kind = kind
        self.on_done = on_done
        self.alive = True
        frames = art.WAND if kind == "wand" else art.YARN
        w, h = art.size_of(frames[0])
        self.setFixedSize(w * TOY_U, h * TOY_U)
        self.frame = 0
        self._t = 0
        self._started = time.monotonic()
        self._last_cursor = QCursor.pos()
        self._still_since = time.monotonic()
        c = QCursor.pos()
        self.fx, self.fy = float(c.x()), float(c.y())
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._step)
        self.timer.start(TOY_MS)
        self._step()
        self.show()
        show_on_all_spaces(self)

    def point(self):
        """貓咪要撲的位置（全域座標）。"""
        if self.kind == "wand":
            return self.x() + self.width() * 0.65, self.y() + self.height()
        return self.x() + self.width() / 2, self.y() + self.height()

    def _step(self):
        c = QCursor.pos()
        now = time.monotonic()
        if c != self._last_cursor:
            self._still_since = now
        self._last_cursor = c
        if now - self._started > TOY_LIFETIME:
            self.stop()
            return
        self._t += 1
        if self.kind == "wand":
            if self._t % 12 == 0:
                self.frame ^= 1
                self.update()
            self.move(c.x() - 2, c.y() - 2)          # 棍子的尾巴就在游標上
        else:
            # 毛線球：慢慢滾向游標，貼著螢幕底部
            screen = QGuiApplication.screenAt(c) or QGuiApplication.primaryScreen()
            r = screen.availableGeometry()
            tx = c.x() - self.width() / 2
            ty = r.bottom() + 1 - self.height()
            dx = (tx - self.fx) * 0.04
            self.fx += max(-7, min(7, dx))
            self.fy = ty
            if abs(dx) > 0.25 and self._t % max(2, int(16 - min(14, abs(dx) * 2))) == 0:
                self.frame ^= 1
                self.update()
            self.move(int(self.fx), int(self.fy))

    def stop(self):
        if not self.alive:
            return
        self.alive = False
        self.timer.stop()
        self.hide()
        self.on_done(self)
        self.deleteLater()

    def paintEvent(self, _e):
        frames = art.WAND if self.kind == "wand" else art.YARN
        QPainter(self).drawPixmap(0, 0, art.pix(frames[self.frame], TOY_U))


# ---------------- 家具 ---------------- #
class Spot(QWidget):
    """放在桌面上的家具（紙箱 box、貓跳台 tree）：可以拖曳，貓咪會自己過來。"""

    def __init__(self, ctrl, kind):
        super().__init__(None)
        _base_flags(self, click_through=False)
        self.ctrl = ctrl
        self.kind = kind
        self.alive = True
        self.occupant = None
        self._press = None
        self.top_pad = 10 if kind == "box" else 0         # 紙箱上面留空間給探出來的頭
        if kind == "box":
            self.setFixedSize(art.BOX_W * U, (art.BOX_H + self.top_pad) * U)
        else:
            self.setFixedSize(art.TREE_W * U, art.TREE_H * U)
        self.zz = QTimer(self)
        self.zz.setTimerType(Qt.VeryCoarseTimer)
        self.zz.timeout.connect(self.update)
        pos = ctrl.settings.value(f"spot_{kind}_pos")
        if isinstance(pos, QPoint) and QGuiApplication.screenAt(pos):
            self.move(pos)
        else:
            r = QGuiApplication.primaryScreen().availableGeometry()
            x = r.left() + (360 if kind == "box" else 280)
            self.move(x, r.bottom() + 1 - self.height())
        self.show()
        show_on_all_spaces(self)

    # ---- 給貓咪用的位置 ----
    def ground(self):
        return self.y() + self.height()

    def approach(self, cat):
        y = self.ground() - (cat.height() - cat.foot_off())
        if self.kind == "box":
            return self.x() + self.width() / 2 - cat.width() / 2, y
        side = -1 if cat.center_x() < self.x() + self.width() / 2 else 1
        x = self.x() - cat.width() * 0.55 if side < 0 else self.x() + self.width() - cat.width() * 0.45
        return x, y

    def perch(self, cat):
        top = self.y() + (art.TREE_TOP - 2) * U
        return self.x() + self.width() / 2 - cat.width() / 2, top - (cat.height() - cat.foot_off())

    def occupy(self, cat):
        self.occupant = cat
        self.zz.start(1200)
        self.update()

    def release(self, cat):
        if self.occupant is cat:
            self.occupant = None
        self.zz.stop()
        self.update()

    # ---- 畫 ----
    def paintEvent(self, _e):
        p = QPainter(self)
        if self.kind == "tree":
            p.drawPixmap(0, 0, art.cat_tree(U))
            return
        oy = self.top_pad * U
        p.drawPixmap(0, oy, art.cardboard_box(U))
        cat = self.occupant
        if cat is not None:
            pm = sprites.face(cat.color, "peek", U)
            fw = pm.width() / pm.devicePixelRatio()
            fh = pm.height() / pm.devicePixelRatio()
            p.drawPixmap(int(self.width() / 2 - fw / 2), int(oy + 8 * U - fh), pm)
            p.drawPixmap(0, oy, art.cardboard_box(U, front_only=True))
            if self.ctrl.sleeping:
                zz = sprites.effect("zzz", 2)
                bob = (int(time.monotonic() / 1.2) % 2) * 3
                p.drawPixmap(int(self.width() / 2 + 14), 2 - bob + 6, zz)

    # ---- 滑鼠 ----
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
            if self.occupant is not None:
                self.occupant.leave_spot()
            self._press = (start, off, True)
            self.move(gp - off)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self._press:
            return
        dragging = self._press[2]
        self._press = None
        if dragging:
            r = (QGuiApplication.screenAt(self.geometry().center())
                 or QGuiApplication.primaryScreen()).availableGeometry()
            self.move(max(r.left(), min(self.x(), r.right() - self.width())), r.bottom() + 1 - self.height())
            self.ctrl.settings.setValue(f"spot_{self.kind}_pos", self.pos())
        elif self.occupant is not None:
            self.occupant.overlay.burst("heart", 2)
        else:
            self.ctrl.invite_to(self)

    def contextMenuEvent(self, e):
        from glassmenu import GlassMenu
        menu = GlassMenu()
        menu.item("paw", tr("invite_cat"), lambda: self.ctrl.invite_to(self))
        menu.item("close", tr("put_away"), lambda: self.ctrl.place_item(self.kind, False))
        menu.exec(e.globalPos())

    def dispose(self):
        self.alive = False
        if self.occupant is not None:
            self.occupant.leave_spot()
        self.zz.stop()
        self.close()
        self.deleteLater()


# ---------------- 小禮物 ---------------- #
class Gift(QWidget):
    """離開很久回來，貓咪旁邊會多一個小禮物；點一下收下，換小魚乾。"""

    def __init__(self, ctrl, cat):
        super().__init__(None)
        _base_flags(self, click_through=False)
        self.ctrl = ctrl
        self.kind = random.choice(list(art.GIFTS))
        w, h = art.size_of(art.GIFTS[self.kind])
        self.setFixedSize(w * U + 12, h * U + 12)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tr("gift_tip"))
        side = random.choice((-1, 1))
        r = cat.screen_rect()
        x = cat.center_x() + side * (cat.width() * 0.6 + 10) - self.width() / 2
        x = max(r.left(), min(r.right() - self.width(), x))
        ground = cat.y() + cat.height() - cat.foot_off()
        self.move(int(x), int(ground - self.height() + 4))
        self._t = 0
        self.timer = QTimer(self)                     # 一閃一閃，提醒你有禮物（每 0.6 秒一次）
        self.timer.setTimerType(Qt.VeryCoarseTimer)
        self.timer.timeout.connect(self._blink)
        self.timer.start(600)
        self.show()
        show_on_all_spaces(self)

    def _blink(self):
        self._t += 1
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        pm = art.pix(art.GIFTS[self.kind], U)
        p.drawPixmap(6, 8, pm)
        if self._t % 2 == 0:
            sp = sprites.effect("sparkle", 2)
            p.drawPixmap(self.width() - 16, 0, sp)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.timer.stop()
            self.ctrl.collect_gift(self)
            self.close()
            self.deleteLater()

