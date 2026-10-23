"""貓屋：貓咪可以回家睡覺，或從門窗探出頭來。

動態：門口兩側的花叢偶爾飄出幾片小花瓣；有貓咪在家時，煙囪會冒煙。
省電：沒有東西在動的時候完全不跑動畫計時器。花瓣每隔幾秒才飄一陣，
飄完就停；煙只有在有貓咪在家時才會冒。
"""
import math
import random

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

import sprites
from i18n import tr
from macos import show_on_all_spaces

SIZES = {"small": 2, "medium": 3, "large": 4}
MX, MY = 8, 18             # 圖的左右留白、上方留白（給花瓣和煙飄）
AW, AH = sprites.HOUSE_W, sprites.HOUSE_H
GROUND = sprites.HOUSE_GROUND
CHIMNEY = sprites.HOUSE_CHIMNEY            # 煙囪口中心 (x, y)
PETAL_COLORS = [QColor(255, 132, 176), QColor(255, 190, 214), QColor(255, 255, 255),
                QColor(255, 214, 84), QColor(182, 146, 244)]
FRAME_MS = 90


class House(QWidget):
    def __init__(self, ctrl):
        super().__init__(None)
        self.ctrl = ctrl
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                            | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        size = str(ctrl.settings.value("house_size", "medium"))
        self.size_name = size if size in SIZES else "medium"
        self.U = SIZES[self.size_name]
        self.setFixedSize((AW + MX * 2) * self.U, (AH + MY) * self.U)
        self.residents = []        # 在家的貓
        self.state = {}            # cat -> {"slot", "mode": peek/sleep, "rise": 0..6}
        self.petals = []           # [x, y, vx, vy, phase, color, life]（圖的像素座標）
        self.smoke = []            # [x, y, r, life, max_life]
        self._press = None
        self._tick_n = 0
        self._spaces_done = False

        self.timer = QTimer(self)                # 有貓在家：換姿勢、冒煙
        self.timer.setTimerType(Qt.CoarseTimer)
        self.timer.setInterval(800)
        self.timer.timeout.connect(self._tick)
        self.anim = QTimer(self)                 # 動畫：只有東西在動時才跑
        self.anim.setTimerType(Qt.CoarseTimer)
        self.anim.setInterval(FRAME_MS)
        self.anim.timeout.connect(self._animate)
        self.gust = QTimer(self)                 # 每隔幾秒飄一陣花瓣
        self.gust.setSingleShot(True)
        self.gust.setTimerType(Qt.VeryCoarseTimer)
        self.gust.timeout.connect(self._gust)

        pos = ctrl.settings.value("house_pos")
        if isinstance(pos, QPoint) and QGuiApplication.screenAt(pos):
            self.move(pos)
        else:
            r = QGuiApplication.primaryScreen().availableGeometry()
            self.move(r.left() + 30, r.bottom() + 1 - (MY + GROUND) * self.U)

    # ---------------- 顯示 ---------------- #
    def show_house(self):
        if not self.isVisible():
            self.show()
            if not self._spaces_done:
                show_on_all_spaces(self)
                self._spaces_done = True
            self._schedule_gust(800)
        self.ctrl.settings.setValue("house_visible", "1")

    def hide_house(self):
        if self.residents:
            self.ctrl.come_out()
        self.hide()
        self.gust.stop()
        self.anim.stop()
        self.petals.clear()
        self.smoke.clear()
        self.ctrl.settings.setValue("house_visible", "0")

    def set_size(self, name):
        if name not in SIZES or name == self.size_name:
            return
        ground = QPoint(self.x() + MX * self.U, self.y() + (MY + GROUND) * self.U)
        self.size_name, self.U = name, SIZES[name]
        self.setFixedSize((AW + MX * 2) * self.U, (AH + MY) * self.U)
        self.move(ground.x() - MX * self.U, ground.y() - (MY + GROUND) * self.U)
        self.ctrl.settings.setValue("house_size", name)
        self.ctrl.settings.setValue("house_pos", self.pos())
        for cat in self.residents:                # 在家的貓也跟著移到新門口
            x, y = self.door_cat_pos(cat)
            cat.move(int(x), int(y))
        self.update()

    def door_cat_pos(self, cat):
        """貓咪站在門口時，貓咪視窗的左上角座標。"""
        dx, dy, dw, dh = sprites.HOUSE_SLOTS["door"]
        x = self.x() + (MX + dx + dw / 2) * self.U - cat.width() / 2
        y = self.y() + (MY + GROUND) * self.U - (cat.height() - cat.foot_off())
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
        self._puff()
        self.anim.start()
        self.update()

    def remove(self, cat):
        if cat in self.residents:
            self.residents.remove(cat)
            self.state.pop(cat, None)
        if not self.residents:
            self.timer.stop()
        self.update()

    def _tick(self):
        """冒一朵煙；偶爾換一下：有的貓去睡覺，有的探出頭來看看。"""
        self._tick_n += 1
        self._puff()
        if self._tick_n % 2 == 0:
            for st in self.state.values():
                if random.random() < 0.25:
                    st["mode"] = "sleep" if st["mode"] == "peek" else "peek"
                    if st["mode"] == "peek":
                        st["rise"] = 0
        self.anim.start()
        self.update()

    # ---------------- 粒子：煙、花瓣 ---------------- #
    def _puff(self):
        if len(self.smoke) < 8:
            life = random.randint(34, 42)
            self.smoke.append([CHIMNEY[0] + random.uniform(-0.6, 0.6), CHIMNEY[1], 1.2, life, life])

    def _schedule_gust(self, ms=None):
        if self.isVisible():
            self.gust.start(ms if ms is not None else random.randint(2600, 6000))

    def _gust(self):
        bushes = [(4, 18), (AW - 22, AW - 4)]
        for _ in range(random.randint(2, 4)):
            x0, x1 = random.choice(bushes)
            self.petals.append([random.uniform(x0, x1), GROUND - random.uniform(6, 9),
                                random.uniform(-0.35, 0.35), random.uniform(-0.45, -0.2),
                                random.uniform(0, 6.28), random.choice(PETAL_COLORS),
                                random.randint(50, 80)])
        self.anim.start()
        self._schedule_gust()

    def _animate(self):
        moving = False
        for st in self.state.values():
            if st["mode"] == "peek" and st["rise"] < 6:
                st["rise"] += 1
                moving = True
        for pt in self.petals:
            pt[4] += 0.32
            pt[3] = min(pt[3] + 0.018, 0.25)            # 先往上飄，再慢慢落下
            pt[0] += pt[2] + math.sin(pt[4]) * 0.35
            pt[1] += pt[3]
            pt[6] -= 1
        self.petals = [p for p in self.petals
                       if p[6] > 0 and -MX < p[0] < AW + MX and p[1] < GROUND + 2]
        for s in self.smoke:
            s[0] += 0.16 + math.sin(s[3] * 0.3) * 0.1
            s[1] -= 0.34
            s[2] = min(3.4, s[2] + 0.07)
            s[3] -= 1
        self.smoke = [s for s in self.smoke if s[3] > 0]
        if not (moving or self.petals or self.smoke):
            self.anim.stop()
        self.update()

    # ---------------- 繪圖 ---------------- #
    def _art_rect(self, x, y, w, h):
        u = self.U
        return QRect(int(round((MX + x) * u)), int(round((MY + y) * u)), max(1, int(w * u)), max(1, int(h * u)))

    def paintEvent(self, _e):
        p = QPainter(self)
        u = self.U
        # 煙（畫在房子後面，像從煙囪裡冒出來）：像素圓，淺灰外框 + 白色內裡
        for x, y, r, life, mx in self.smoke:
            a = int(235 * min(1.0, life / (mx * 0.55)))
            edge, fill = QColor(176, 170, 196, a), QColor(248, 246, 252, a)
            cx, cy = x, y
            ri = int(math.ceil(r))
            for j in range(-ri, ri + 1):
                for i in range(-ri, ri + 1):
                    d = math.hypot(i, j)
                    if d <= r:
                        c = edge if d > r - 1.0 else fill
                        p.fillRect(self._art_rect(int(round(cx)) + i, int(round(cy)) + j, 1, 1), c)
        # 門窗平常關著；有貓咪待著的那一格才打開
        p.drawPixmap(MX * u, MY * u, sprites.house(u, closed=True))
        opened = sprites.house(u)
        dpr = opened.devicePixelRatio()
        for st in self.state.values():
            x, y, w, h = sprites.HOUSE_SLOTS[st["slot"]]
            p.drawPixmap(self._art_rect(x, y, w, h), opened,
                         QRect(int(x * u * dpr), int(y * u * dpr), int(w * u * dpr), int(h * u * dpr)))
        for cat, st in self.state.items():
            x, y, w, h = sprites.HOUSE_SLOTS[st["slot"]]
            hole = self._art_rect(x, y, w, h)
            if st["mode"] == "peek":
                pm = sprites.face(cat.color, "peek", u)
                fw = pm.width() / pm.devicePixelRatio()
                fh = pm.height() / pm.devicePixelRatio()
                rise = min(fh, h * u) * st["rise"] / 6
                p.save()
                p.setClipRect(hole)
                p.drawPixmap(int(hole.center().x() - fw / 2 + 1), int(hole.bottom() + 1 - rise), pm)
                p.restore()
            else:
                zz = sprites.effect("zzz", u)
                bob = (self._tick_n // 2 % 2) * u
                zh = zz.height() / zz.devicePixelRatio()
                p.drawPixmap(hole.right() - u, int(hole.top() - zh - u - bob), zz)
        # 花瓣（畫在最前面）
        for x, y, _vx, _vy, ph, color, life in self.petals:
            c = QColor(color)
            c.setAlpha(255 if life > 10 else int(255 * life / 10))
            flip = math.sin(ph)                          # 翻轉：2x2 → 2x1 → 1x1
            w, h = (2, 2) if flip > 0.35 else ((2, 1) if flip > -0.4 else (1, 1))
            p.fillRect(self._art_rect(int(round(x)), int(round(y)), w, h), c)

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
            for cat in self.residents:
                x, y = self.door_cat_pos(cat)
                cat.move(int(x), int(y))

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self._press:
            return
        dragging = self._press[2]
        self._press = None
        if dragging:
            self.ctrl.settings.setValue("house_pos", self.pos())

    def fill_menu(self, menu):
        if self.residents:
            menu.item("paw", tr("come_out"), self.ctrl.come_out)
        if len(self.residents) < len(self.ctrl.cats):
            menu.item("home", tr("go_home_all"), self.ctrl.go_home_all)
        menu.sub("size", tr("house_size")).choices(
            {k: tr("hsize_" + k) for k in SIZES}, self.size_name, self.set_size)

    def contextMenuEvent(self, e):
        from glassmenu import GlassMenu
        menu = GlassMenu()
        self.fill_menu(menu)
        menu.addSeparator()
        menu.item("close", tr("house_hide"), self.hide_house)
        menu.exec(e.globalPos())
