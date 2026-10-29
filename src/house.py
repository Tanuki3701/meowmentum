"""貓屋：貓咪可以回家睡覺，或從門窗探出頭來；也可以把前牆拿掉，看看屋子裡面。

兩種樣子都是同一個桌面上的小物件（不是另外開視窗）：
- 外面：關著的門窗、探出頭的貓、冒煙的煙囪、花叢飄花瓣。
- 裡面：像娃娃屋的剖面，在家的貓咪就是桌面上真的貓，可以點、拖、按右鍵。

省電：貓屋收起來時完全不跑計時器；顯示時動畫只畫這個小視窗。
"""
import math
import random
import time

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

import art
import interior
import seasons
import sprites
from i18n import tr
from macos import show_on_all_spaces

SIZES = {"small": 2, "medium": 3, "large": 4}
INSIDE_SIZES = {"same": None, "large": 4, "xlarge": 5, "huge": 6}   # 看裡面時可以放得更大
MX, MY = 8, 18             # 圖的左右留白、上方留白（給花瓣和煙飄）
AW, AH = sprites.HOUSE_W, sprites.HOUSE_H
GROUND = sprites.HOUSE_GROUND
PETAL_COLORS = [QColor(255, 132, 176), QColor(255, 190, 214), QColor(255, 255, 255),
                QColor(255, 214, 84), QColor(182, 146, 244)]
SPRING_COLORS = [QColor(255, 182, 206), QColor(255, 206, 222), QColor(255, 236, 242)]
FRAME_MS = 33              # 花瓣、煙：約 30fps，看起來才順
DOOR_OPEN_S = 0.9          # 貓咪進出時門打開多久

INK = QColor(58, 55, 55)
SNOW = QColor(255, 255, 255)
SNOW_SHADE = QColor(212, 230, 250)
ICE = QColor(186, 228, 255)
SNOW_EDGE = QColor(150, 176, 214)

# 兩種樣子的尺寸：(寬, 高, 草地頂端, 煙囪口, 花叢位置)
VIEWS = {
    "outside": dict(w=AW, h=AH, ground=GROUND, chimney=sprites.HOUSE_CHIMNEY,
                    bushes=[(4, 18), (AW - 22, AW - 4)]),
    "inside": dict(w=interior.IW, h=interior.IH, ground=interior.GRASS, chimney=interior.CHIMNEY,
                   bushes=[(0, 12), (interior.IW - 12, interior.IW)]),
}


def _eye_icon():
    from PySide6.QtGui import QIcon
    return QIcon(art.icon_pm("eye"))


def _outside_roof():
    rows = {}
    for y in range(3, 26):
        half = int((y - 3) * 26 / 22) + 1
        rows[y] = (28 - half, 27 + half)
    return rows


def _inside_roof():
    rows = {}
    for y in range(2, interior.EAVE + 1):
        half = interior._roof_half(y)
        rows[y] = (52 - half, 51 + half)
    return rows


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
        isize = str(ctrl.settings.value("inside_size", "same"))
        self.inside_size = isize if isize in INSIDE_SIZES else "same"
        self.view = "outside"
        self.U = self._unit_for(self.view)
        self._resize_for_view()
        self.residents = []        # 在家的貓
        self.state = {}            # 外面看：cat -> {"slot", "mode": peek/sleep, "rise": 0..6}
        self.petals = []           # [x, y, vx, vy, phase, color, life]（圖的格子座標）
        self.smoke = []            # [x, y, r, life, max_life]
        self._press = None
        self._tick_n = 0
        self._spaces_done = False
        self._door_until = 0.0
        self._last_anim = time.monotonic()
        self._fade = None

        self.timer = QTimer(self)                # 有貓在家：換姿勢
        self.timer.setTimerType(Qt.CoarseTimer)
        self.timer.setInterval(800)
        self.timer.timeout.connect(self._tick)
        self.anim = QTimer(self)                 # 動畫：只有東西在動時才跑
        self.anim.setTimerType(Qt.PreciseTimer)
        self.anim.setInterval(FRAME_MS)
        self.anim.timeout.connect(self._animate)
        self.smoke_timer = QTimer(self)          # 煙囪一直都有煙：每隔一下冒一朵
        self.smoke_timer.setTimerType(Qt.CoarseTimer)
        self.smoke_timer.setInterval(1100)
        self.smoke_timer.timeout.connect(self._smoke_tick)
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

    # ---------------- 尺寸 ---------------- #
    @property
    def V(self):
        return VIEWS[self.view]

    def _unit_for(self, view):
        if view == "inside" and INSIDE_SIZES[self.inside_size]:
            return INSIDE_SIZES[self.inside_size]
        return SIZES[self.size_name]

    def _resize_for_view(self):
        v = self.V
        self.setFixedSize((v["w"] + MX * 2) * self.U, (v["h"] + MY) * self.U)

    def _anchor(self):
        """貓屋的「地面中心點」（換樣子、換大小時保持不動）。"""
        v = self.V
        return (self.x() + (MX + v["w"] / 2) * self.U, self.y() + (MY + v["ground"]) * self.U)

    def _place_at(self, anchor):
        v = self.V
        x = int(round(anchor[0] - (MX + v["w"] / 2) * self.U))
        y = int(round(anchor[1] - (MY + v["ground"]) * self.U))
        s = QGuiApplication.screenAt(QPoint(int(anchor[0]), int(anchor[1]) - 4)) or QGuiApplication.primaryScreen()
        g = s.availableGeometry()
        x = max(g.left() - MX * self.U, min(x, g.right() + 1 - self.width() + MX * self.U))  # 整間屋子留在螢幕裡
        self.move(x, y)

    def screen_rect(self):
        s = QGuiApplication.screenAt(self.geometry().center()) or QGuiApplication.primaryScreen()
        return s.availableGeometry()

    # ---------------- 顯示 ---------------- #
    def show_house(self):
        if not self.isVisible():
            self.show()
            if not self._spaces_done:
                show_on_all_spaces(self)
                self._spaces_done = True
            self._schedule_gust(800)
            self.smoke_timer.start()
            self._smoke_tick()
        self.ctrl.settings.setValue("house_visible", "1")

    def hide_house(self):
        if self.view == "inside":
            self.set_view("outside", animate=False)
        if self.residents:
            self.ctrl.come_out()
        self.hide()
        self.gust.stop()
        self.smoke_timer.stop()
        self.anim.stop()
        self.petals.clear()
        self.smoke.clear()
        self.ctrl.settings.setValue("house_visible", "0")

    def set_size(self, name):
        if name not in SIZES or name == self.size_name:
            return
        anchor = self._anchor()
        self.size_name = name
        self.U = self._unit_for(self.view)
        self._resize_for_view()
        self._place_at(anchor)
        self.ctrl.settings.setValue("house_size", name)
        self._rescale_indoor()
        self.ctrl.settings.setValue("house_pos", self.pos())
        self.petals.clear()
        self.smoke.clear()
        self._sync_cats()
        self.update()

    def set_inside_size(self, name):
        if name not in INSIDE_SIZES or name == self.inside_size:
            return
        self.inside_size = name
        self.ctrl.settings.setValue("inside_size", name)
        if self.view != "inside":
            return
        anchor = self._anchor()
        self.U = self._unit_for("inside")
        self._resize_for_view()
        self._place_at(anchor)
        self.petals.clear()
        self.smoke.clear()
        self._rescale_indoor()
        self.update()

    def _rescale_indoor(self):
        """房間裡的貓咪和房間用同一個像素大小，看起來才像住在裡面。"""
        for cat in self.residents:
            if cat.indoor is self:
                cat.use_room_scale(self.U)
        self._sync_cats()

    # ---------------- 外面 ↔ 裡面 ---------------- #
    def toggle_view(self):
        self.set_view("inside" if self.view == "outside" else "outside")

    def set_view(self, view, animate=True):
        if view == self.view:
            return
        self.show_house()
        if not animate:
            self._switch(view)
            return
        self._fade_to(0.0, 140, lambda: (self._switch(view), self._fade_to(1.0, 200)))

    def _fade_to(self, value, ms, done=None):
        if self._fade is not None:
            self._fade.stop()
        a = QPropertyAnimation(self, b"windowOpacity", self)
        a.setDuration(ms)
        a.setStartValue(self.windowOpacity())
        a.setEndValue(value)
        a.setEasingCurve(QEasingCurve.InOutQuad)
        if done:
            a.finished.connect(done)
        a.start()
        self._fade = a

    def _switch(self, view):
        anchor = self._anchor()
        old = self.view
        self.view = view
        self.U = self._unit_for(view)
        self._resize_for_view()
        self._place_at(anchor)
        self.petals.clear()
        self.smoke.clear()
        for cat in list(self.residents):
            if view == "inside" and old == "outside":
                self.state.pop(cat, None)
                cat.enter_indoor(self, from_door=False)
            elif view == "outside" and cat.indoor is self:
                cat.indoor_to_home(self)
                self._new_state(cat)
        if view == "outside" and self.residents:
            self.timer.start()
        else:
            self.timer.stop()
        self.anim.start()
        self.update()
        for cat in self.residents:
            if cat.indoor is self:
                cat.raise_()

    def _sync_cats(self):
        """貓屋移動或換大小後，把在家的貓咪一起帶過去。"""
        for cat in self.residents:
            if cat.indoor is self:
                lo, hi = self.indoor_x_range(cat)
                cat._move_to(max(lo, min(hi, cat.x())), self.indoor_floor_y(cat), clamp=False)
            else:
                x, y = self.door_cat_pos(cat)
                cat.move(int(x), int(y))

    # ---------------- 給貓咪用的位置 ---------------- #
    def _gx(self, art_x):
        return self.x() + (MX + art_x) * self.U

    def _gy(self, art_y):
        return self.y() + (MY + art_y) * self.U

    def door_cat_pos(self, cat):
        """貓咪站在大門口（外面）時，貓咪視窗的左上角座標。"""
        if self.view == "outside":
            dx, dy, dw, dh = sprites.HOUSE_SLOTS["door"]
            cx = dx + dw / 2
        else:
            cx = interior.ROOM_L - 9
        x = self._gx(cx) - cat.width() / 2
        y = self._gy(self.V["ground"]) - (cat.height() - cat.foot_off())
        return x, y

    def indoor_floor_y(self, cat):
        return self._gy(interior.IG) - (cat.height() - cat.foot_off())

    def indoor_x_range(self, cat):
        lo = self._gx(interior.ROOM_L + 8) - cat.width() / 2
        hi = self._gx(interior.ROOM_R - 8) - cat.width() / 2
        return lo, max(lo, hi)

    def indoor_spot_x(self, cat, spot):
        x = {"door": interior.DOOR[0] + interior.DOOR[2] / 2,
             "cushion": sum(interior.CUSHION_X) / 2,
             "bowl": interior.BOWL_X[1] + 7}[spot]
        return self._gx(x) - cat.width() / 2

    def room_contains(self, point):
        """這一點（全域座標）是不是在房間裡面。"""
        if self.view != "inside":
            return False
        r = QRect(int(self._gx(interior.ROOM_L)), int(self._gy(interior.EAVE + 4)),
                  int((interior.ROOM_R - interior.ROOM_L) * self.U),
                  int((interior.IG - interior.EAVE - 2) * self.U))
        return r.contains(point)

    def open_door(self):
        """貓咪進出時，門打開一下。"""
        self._door_until = time.monotonic() + DOOR_OPEN_S
        self.update()
        QTimer.singleShot(int(DOOR_OPEN_S * 1000) + 30, self.update)

    # ---------------- 住戶 ---------------- #
    def _new_state(self, cat):
        used = {s["slot"] for s in self.state.values()}
        free = [k for k in sprites.SLOT_ORDER if k not in used]
        slot = free[0] if free else random.choice(sprites.SLOT_ORDER)
        self.state[cat] = {"slot": slot, "mode": "peek", "rise": 0}

    def add(self, cat):
        if cat in self.residents:
            return
        self.residents.append(cat)
        self.show_house()
        if self.view == "outside":
            self._new_state(cat)
            self.timer.start()
        self.anim.start()
        self.update()

    def remove(self, cat):
        if cat in self.residents:
            self.residents.remove(cat)
            self.state.pop(cat, None)
        if not self.state:
            self.timer.stop()
        self.update()

    def _tick(self):
        """偶爾換一下：有的貓去睡覺，有的探出頭來看看。"""
        self.residents = [c for c in self.residents if c.activity == "home" or c.indoor is self]
        self.state = {c: st for c, st in self.state.items() if c in self.residents and c.activity == "home"}
        if not self.state:
            self.timer.stop()
            self.update()
            return
        self._tick_n += 1
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
            cx, cy = self.V["chimney"]
            self.smoke.append([cx + random.uniform(-0.6, 0.6), cy, 1.2, life, life])

    def _smoke_tick(self):
        self._puff()
        self.anim.start()

    def _schedule_gust(self, ms=None):
        if self.isVisible():
            slow = 2 if self.ctrl.low_power else 1
            self.gust.start(ms if ms is not None else random.randint(2600, 6000) * slow)

    def _gust(self):
        spring = self.ctrl.seasonal and "spring" in seasons.decorations()
        g = self.V["ground"]
        for _ in range(random.randint(2, 4)):
            x0, x1 = random.choice(self.V["bushes"])
            self.petals.append([random.uniform(x0, x1), g - random.uniform(6, 9),
                                random.uniform(-0.35, 0.35), random.uniform(-0.45, -0.2),
                                random.uniform(0, 6.28),
                                random.choice(SPRING_COLORS if spring else PETAL_COLORS),
                                random.randint(50, 80)])
        self.anim.start()
        self._schedule_gust()

    def _animate(self):
        now = time.monotonic()
        k = min(3.0, max(0.2, (now - self._last_anim) / 0.09))   # 以前 90ms 一格的速度為準
        self._last_anim = now
        moving = False
        for st in self.state.values():
            if st["mode"] == "peek" and st["rise"] < 6:
                st["rise"] = min(6, st["rise"] + k)
                moving = True
        g = self.V["ground"]
        for pt in self.petals:
            pt[4] += 0.32 * k
            pt[3] = min(pt[3] + 0.018 * k, 0.25)            # 先往上飄，再慢慢落下
            pt[0] += (pt[2] + math.sin(pt[4]) * 0.35) * k
            pt[1] += pt[3] * k
            pt[6] -= k
        self.petals = [p for p in self.petals
                       if p[6] > 0 and -MX < p[0] < self.V["w"] + MX and p[1] < g + 2]
        for s in self.smoke:
            s[0] += (0.16 + math.sin(s[3] * 0.3) * 0.1) * k
            s[1] -= 0.34 * k
            s[2] = min(3.4, s[2] + 0.07 * k)
            s[3] -= k
        self.smoke = [s for s in self.smoke if s[3] > 0]
        if not (moving or self.petals or self.smoke):
            self.anim.stop()
        self.update()

    # ---------------- 繪圖 ---------------- #
    def _art_rect(self, x, y, w, h):
        u = self.U
        return QRect(int(round((MX + x) * u)), int(round((MY + y) * u)), max(1, int(round(w * u))),
                     max(1, int(round(h * u))))

    def _px(self, p, x, y, color, w=1, h=1):
        p.fillRect(self._art_rect(x, y, w, h), color)

    def paintEvent(self, _e):
        p = QPainter(self)
        u = self.U
        phase = seasons.phase()
        night = phase == "night"
        deco = seasons.decorations() if self.ctrl.seasonal else set()
        # 煙（畫在房子後面，像從煙囪裡冒出來）：像素圓，淺灰外框 + 白色內裡
        for x, y, r, life, mx in self.smoke:
            a = int(235 * min(1.0, life / (mx * 0.55)))
            edge, fill = QColor(176, 170, 196, a), QColor(248, 246, 252, a)
            ri = int(math.ceil(r))
            for j in range(-ri, ri + 1):
                for i in range(-ri, ri + 1):
                    d = math.hypot(i, j)
                    if d <= r:
                        self._px(p, int(round(x)) + i, int(round(y)) + j, edge if d > r - 1.0 else fill)
        if self.view == "inside":
            p.drawPixmap(MX * u, MY * u, interior.dollhouse(self.ctrl.progress.owned, phase, deco, u))
            if "snow" in deco:
                self._paint_snow(p, _inside_roof(), (interior.CHIMNEY[0] - 4, 0, 9),
                                 [(-4, interior.GRASS - 8, True, False), (interior.IW - 14, interior.GRASS - 8, True, True)],
                                 interior.GRASS, interior.IW, [], icicles=(6, 18, 30, 73, 88, 97), eave=interior.EAVE + 1)
        else:
            self._paint_outside(p, phase, deco)
        # 花瓣（畫在最前面）
        for x, y, _vx, _vy, ph, color, life in self.petals:
            c = QColor(color)
            c.setAlpha(255 if life > 10 else int(255 * life / 10))
            flip = math.sin(ph)                          # 翻轉：2x2 → 2x1 → 1x1
            w, h = (2, 2) if flip > 0.35 else ((2, 1) if flip > -0.4 else (1, 1))
            self._px(p, int(round(x)), int(round(y)), c, w, h)

    def _paint_outside(self, p, phase, deco):
        u = self.U
        # 門窗平常關著；有貓咪待著的那一格才打開（貓咪進出時，門也會開一下）
        p.drawPixmap(MX * u, MY * u, sprites.house(u, closed=True))
        opened = sprites.house(u)
        dpr = opened.devicePixelRatio()
        used = {st["slot"] for st in self.state.values()}
        if time.monotonic() < self._door_until:
            used.add("door")
        for key in used:
            x, y, w, h = sprites.HOUSE_SLOTS[key]
            p.drawPixmap(self._art_rect(x, y, w, h), opened,
                         QRect(int(x * u * dpr), int(y * u * dpr), int(w * u * dpr), int(h * u * dpr)))
        if phase != "day":
            self._paint_glass(p, used, phase)
        if deco:
            self._paint_decor(p, used, deco)
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

    # 關著的窗戶玻璃映著天色：(上, 下, 反光, 點綴)
    GLASS = {
        "morning": ((255, 184, 156), (160, 200, 246), (255, 250, 240), (255, 238, 190)),
        "dusk": ((128, 92, 170), (248, 150, 104), (255, 210, 170), (255, 230, 150)),
        "night": ((30, 36, 78), (52, 60, 112), (120, 140, 200), (255, 244, 200)),
    }

    def _paint_glass(self, p, used, phase):
        """早上、傍晚、晚上：關著的窗戶映出那時候的天色（晚上是暗暗的深藍色，帶一點星光）。"""
        top, bot, glint, dot = self.GLASS[phase]
        frame = QColor(206, 206, 222) if phase == "night" else QColor(250, 246, 240)
        for key in ("left", "right", "attic"):
            if key in used:
                continue
            x, y, w, h = sprites.HOUSE_SLOTS[key]
            for i in range(h):
                t = i / max(1, h - 1)
                self._px(p, x, y + i, QColor(*(int(a + (b - a) * t) for a, b in zip(top, bot))), w, 1)
            self._px(p, x + 1, y + 1, QColor(*glint))
            if phase == "night":
                self._px(p, x + w - 3, y + h - 2, QColor(*dot))            # 一顆星星的倒影
            else:
                self._px(p, x + 2, y + 1, QColor(*glint))                  # 斜斜的反光
                self._px(p, x + 1, y + 2, QColor(*glint))
                self._px(p, x + w - 3, y + h - 3, QColor(*dot))
            self._px(p, x + w // 2, y, frame, 1, h)
            if key != "attic":
                self._px(p, x, y + h // 2, frame, w, 1)

    # ---------------- 積雪 ---------------- #
    def _paint_snow(self, p, roof, chimney, bushes, ground, width, sills, icicles, eave, keep_out=None):
        """一層厚厚、有起伏的雪：屋頂、煙囪、窗台、花叢和地上都會積雪，屋簷掛著小冰柱。"""
        xs = sorted({x for x0, x1 in roof.values() for x in range(x0, x1 + 1)})
        cx, cy, cw = chimney
        keep = keep_out or []
        for x in xs:
            if cx <= x < cx + cw:                            # 煙囪擋住的地方不積雪
                continue
            surface = min(y for y, (x0, x1) in roof.items() if x0 <= x <= x1)
            edge = min(x - xs[0], xs[-1] - x)
            # 厚厚一層：鼓起來的雪蓋在屋瓦上，下緣一團一團、有長有短
            wave = math.sin(x * 0.62) + 0.6 * math.sin(x * 1.37 + 1.0)
            up = 1 + (1 if math.sin(x * 0.45 + 2.0) > 0.1 else 0)
            down = max(2, min(5, int(round(3.4 + wave * 1.1))))
            if edge < 2:
                up, down = 1, 2 + edge
            for kx0, kx1, ky in keep:                        # 別蓋到閣樓窗戶
                if kx0 <= x <= kx1:
                    down = min(down, ky - surface)
            if x == cx - 1:                                  # 靠著煙囪堆高一點
                up += 1
            top, bot = surface - up, surface + down
            self._px(p, x, top - 1, INK)
            self._px(p, x, top, SNOW, 1, bot - top)
            self._px(p, x, bot - 1, SNOW_SHADE)
            self._px(p, x, bot, SNOW_EDGE)
        for x0, x1 in (roof[eave - 1],):                    # 屋簷兩端的雪垂下來
            for x, d in ((x0, 3), (x0 + 1, 2), (x0 + 2, 1), (x1, 3), (x1 - 1, 2), (x1 - 2, 1)):
                self._px(p, x, eave - 1, SNOW, 1, d)
                self._px(p, x, eave - 2 + d, SNOW_SHADE)
                self._px(p, x, eave - 1 + d, INK)
        for x in icicles:
            ln = 1 + (x % 3)
            self._px(p, x, eave + 1, ICE, 1, ln)
            self._px(p, x, eave + 1 + ln, QColor(132, 190, 240))
        # 煙囪頂上一團雪
        self._px(p, cx, cy - 2, INK, cw, 1)
        self._px(p, cx - 1, cy - 1, INK)
        self._px(p, cx + cw, cy - 1, INK)
        self._px(p, cx, cy - 1, SNOW, cw, 2)
        self._px(p, cx + 1, cy - 3, INK, cw - 3, 1)
        self._px(p, cx + 1, cy - 2, SNOW, cw - 3, 1)
        for sx, sy, sw in sills:                             # 窗台
            self._px(p, sx, sy - 1, INK, sw, 1)
            self._px(p, sx, sy, SNOW, sw, 1)
        bush = interior.BUSH
        bw = len(bush[0])
        for bx, by, _ok, flip in bushes:                     # 花叢頂端
            for gx in range(bw):
                col = bw - 1 - gx if flip else gx
                top = next((gy for gy, row in enumerate(bush) if row[col] != "."), None)
                if top is None or top > 4:
                    continue
                h = 2 if (gx % 4) else 1
                self._px(p, bx + gx, by + top - h, INK)
                self._px(p, bx + gx, by + top - h + 1, SNOW, 1, h)
        for x in range(0, width):                            # 地上的雪
            h = 1 + (1 if (x * 5) % 7 < 3 else 0)
            self._px(p, x, ground - h - 1, INK)
            self._px(p, x, ground - h, SNOW, 1, h)
            self._px(p, x, ground, SNOW_SHADE)

    def _paint_decor(self, p, used, deco):
        """節慶裝飾：萬聖節南瓜、聖誕花圈和燈泡、積雪、春聯和燈籠。"""
        u = self.U
        if "snow" in deco:
            sills = [(sprites.HOUSE_SLOTS[k][0] - 2, sprites.HOUSE_SLOTS[k][1] + sprites.HOUSE_SLOTS[k][3] + 1,
                      sprites.HOUSE_SLOTS[k][2] + 4) for k in ("left", "right")]
            self._paint_snow(p, _outside_roof(), (37, 2, 9),
                             [(2, GROUND - 8, True, False), (AW - 20, GROUND - 8, True, True)],
                             GROUND, AW, sills, icicles=(4, 9, 15, 41, 47, 52), eave=25,
                             keep_out=[(21, 34, 10)])
        if "xmas" in deco:
            colors = [QColor(232, 72, 72), QColor(255, 214, 70), QColor(90, 190, 90), QColor(90, 150, 230)]
            for i, x in enumerate(range(5, AW - 4, 4)):
                self._px(p, x, 26, INK)
                self._px(p, x, 27, colors[i % 4])
            if "door" not in used:
                p.drawPixmap(self._art_rect(25, 39, 7, 8).topLeft(), art.pix(art.WREATH, u))
        if "halloween" in deco:
            p.drawPixmap(self._art_rect(13, GROUND - 8, 8, 8).topLeft(), art.pix(art.PUMPKIN, u))
        if "lny" in deco:
            p.drawPixmap(self._art_rect(17, 33, 2, 10).topLeft(), art.pix(art.COUPLET, u))
            p.drawPixmap(self._art_rect(37, 33, 2, 10).topLeft(), art.pix(art.COUPLET, u))
            p.drawPixmap(self._art_rect(5, 26, 5, 8).topLeft(), art.pix(art.LANTERN, u))
            p.drawPixmap(self._art_rect(46, 26, 5, 8).topLeft(), art.pix(art.LANTERN, u))

    # ---------------- 滑鼠 ---------------- #
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            gp = e.globalPosition().toPoint()
            self._press = (gp, gp - self.pos(), False, self.pos())

    def mouseMoveEvent(self, e):
        if not self._press:
            return
        gp = e.globalPosition().toPoint()
        start, off, dragging, origin = self._press
        if dragging or (gp - start).manhattanLength() > 5:
            self._press = (start, off, True, origin)
            before = self.pos()
            self.move(gp - off)
            delta = self.pos() - before
            for cat in self.residents:
                if cat.indoor is self:
                    cat._move_to(cat.fx + delta.x(), cat.fy + delta.y(), clamp=False)
                    if cat.target:
                        cat.target = (cat.target[0] + delta.x(), cat.target[1] + delta.y())
                else:
                    x, y = self.door_cat_pos(cat)
                    cat.move(int(x), int(y))

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self._press:
            return
        dragging = self._press[2]
        self._press = None
        if dragging:
            self.ctrl.settings.setValue("house_pos", self.pos())

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.toggle_view()

    def fill_menu(self, menu):
        if self.view == "outside":
            menu.item(_eye_icon(), tr("look_inside"), lambda: self.set_view("inside"))
        else:
            menu.item("home", tr("look_outside"), lambda: self.set_view("outside"))
        if self.residents:
            menu.item("paw", tr("come_out"), self.ctrl.come_out)
        if len(self.residents) < len(self.ctrl.cats):
            menu.item("home", tr("go_home_all"), self.ctrl.go_home_all)
        menu.sub("size", tr("house_size")).choices(
            {k: tr("hsize_" + k) for k in SIZES}, self.size_name, self.set_size)
        menu.sub("size", tr("inside_size")).choices(
            {k: tr("isize_" + k) for k in INSIDE_SIZES}, self.inside_size, self.set_inside_size)

    def contextMenuEvent(self, e):
        from glassmenu import GlassMenu
        menu = GlassMenu()
        self.fill_menu(menu)
        menu.addSeparator()
        menu.item("close", tr("house_hide"), self.hide_house)
        menu.exec(e.globalPos())
