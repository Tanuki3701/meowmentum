"""貓屋裡面：可以打開來看看在家的貓咪在做什麼。

房間依照時間（白天／晚上）、節慶和你在商店買的擺設變化；
在家的貓咪會睡在軟墊上、吃飯、散步、玩毛線球。
省電：只有這個視窗打開時才跑動畫（每 0.16 秒一格），關掉就停。
"""
import random

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

import art
import pixel
import seasons
import sprites
from i18n import tr

RU = 3                      # 房間每一格 = 3pt
RW, RH = 112, 62            # 房間大小（格）
FLOOR = 42                  # 地板開始的 y
CAT_SCALE = 2
FRAME_MS = 160

# 每樣擺設在房間裡的位置（格）
SPOTS = {
    "cushion": (70, 48), "bowl": (24, 51), "rug": (36, 50), "plant": (100, 30),
    "lamp": (86, 12), "painting": (66, 9), "scratcher": (22, 26), "fishtank": (56, 30),
    "yarn": (58, 55), "pumpkin": (6, 47), "xmas_tree": (98, 20), "lantern": (30, 2),
}


# ---------------- 擺設的像素圖 ---------------- #
def _draw_item(c, item, x, y, night=False):
    if item == "cushion":
        c.rect(x, y + 2, 26, 7, "K")
        c.rect(x + 2, y, 22, 2, "K")
        c.rect(x + 1, y + 2, 24, 5, "P")
        c.rect(x + 3, y + 1, 20, 2, "H")
        c.rect(x + 3, y + 6, 20, 1, (214, 120, 140))
    elif item == "bowl":
        c.rect(x, y, 10, 1, "K")
        c.rect(x + 1, y - 1, 8, 1, (160, 104, 60))
        c.px(x + 3, y - 2, (160, 104, 60)); c.px(x + 6, y - 2, (130, 84, 50))
        c.rect(x, y + 1, 10, 3, "K")
        c.rect(x + 1, y + 1, 8, 2, "B")
        c.rect(x + 2, y + 1, 2, 1, "U")
    elif item == "rug":
        c.rect(x, y, 30, 8, "K")
        c.rect(x + 1, y + 1, 28, 6, (246, 196, 120))
        c.rect(x + 3, y + 2, 24, 4, (236, 150, 100))
        c.rect(x + 5, y + 3, 20, 2, (250, 214, 150))
    elif item == "plant":
        c.rect(x + 1, y + 8, 8, 6, "K")
        c.rect(x + 2, y + 9, 6, 4, (214, 120, 84))
        c.rect(x + 2, y + 9, 6, 1, (236, 150, 110))
        for dx, dy, h in ((4, 0, 8), (1, 3, 5), (7, 2, 6), (2, 1, 3), (6, 0, 3)):
            c.rect(x + dx, y + dy, 2, h, "K")
            c.rect(x + dx, y + dy + 1, 1, h - 1, "G")
    elif item == "lamp":
        if night:
            for r, a in ((9, 40), (6, 70)):
                c.rect(x + 3 - r, y + 3 - r // 2, 6 + 2 * r, 6 + r, QColor(255, 220, 140, a))
        c.rect(x, y, 10, 6, "K")
        c.rect(x + 1, y + 1, 8, 4, "X" if night else "Y")
        c.rect(x + 1, y + 1, 8, 1, "W" if night else "X")
        c.rect(x + 4, y + 6, 2, 22, "K")
        c.rect(x + 2, y + 27, 6, 1, "K")
    elif item == "painting":
        c.rect(x, y, 14, 11, "K")
        c.rect(x + 1, y + 1, 12, 9, "A")
        c.rect(x + 2, y + 2, 10, 7, (186, 228, 255))
        c.rect(x + 2, y + 7, 10, 2, "G")
        c.rect(x + 8, y + 3, 2, 2, "Y")
        c.rect(x + 4, y + 5, 2, 2, "W")
    elif item == "scratcher":
        c.rect(x, y + 14, 12, 3, "K")
        c.rect(x + 1, y + 15, 10, 1, "T")
        c.rect(x + 3, y, 6, 15, "K")
        c.rect(x + 4, y + 1, 4, 13, "E")
        for yy in range(y + 2, y + 14, 2):
            c.rect(x + 4, yy, 4, 1, "A")
        c.rect(x + 2, y - 1, 8, 2, "K")
        c.rect(x + 3, y - 1, 6, 1, "Q")
    elif item == "fishtank":
        c.rect(x - 2, y + 11, 20, 1, "K")                 # 小桌子
        c.rect(x - 1, y + 12, 2, 6, "K"); c.rect(x + 15, y + 12, 2, 6, "K")
        c.rect(x, y, 16, 11, "K")
        c.rect(x + 1, y + 1, 14, 9, "J")
        c.rect(x + 1, y + 1, 14, 2, "U")
        c.rect(x + 1, y + 8, 14, 2, "A")
        c.rect(x + 3, y + 5, 1, 3, "G"); c.rect(x + 12, y + 4, 1, 4, "G")
        c.rect(x + 6, y + 4, 3, 2, "O"); c.px(x + 9, y + 4, "O"); c.px(x + 7, y + 4, "K")
    elif item == "yarn":
        c.grid(x, y - 7, art.YARN[0])
    elif item == "pumpkin":
        c.grid(x, y - 8, art.PUMPKIN)
    elif item == "xmas_tree":
        for i, w in enumerate((3, 5, 7, 9, 11, 13)):
            c.rect(x + 7 - w // 2, y + 2 + i * 3, w, 3, "K")
            c.rect(x + 8 - w // 2, y + 2 + i * 3, w - 2, 2, "G")
        c.grid(x + 5, y - 3, ["..K..", ".KYK.", "KYYYK", ".KYK.", "..K.."])
        for dx, dy, col in ((5, 8, "R"), (9, 11, "B"), (4, 14, "Y"), (10, 17, "R"), (6, 19, "B")):
            c.px(x + dx, y + dy, col)
        c.rect(x + 6, y + 20, 3, 3, "K"); c.px(x + 7, y + 21, "T")
    elif item == "lantern":
        c.rect(x + 2, y, 1, 4, "K")
        c.grid(x, y + 4, art.LANTERN)


def item_preview(item, unit=2):
    """商店裡的擺設預覽圖。"""
    sizes = {"rug": (30, 8, 0, 0), "plant": (10, 14, 0, 0), "lamp": (19, 29, 4, 0),
             "painting": (14, 11, 0, 0), "scratcher": (12, 18, 0, 1), "fishtank": (20, 18, 2, 0),
             "yarn": (8, 8, 0, 7), "cushion": (26, 9, 0, 0)}
    w, h, ox, oy = sizes.get(item, (12, 12, 0, 0))
    c = art.Canvas(w, h, unit)
    _draw_item(c, item, ox, oy)
    return c.pixmap()


def room_background(owned, night, deco):
    key = ("room", tuple(sorted(owned)), night, tuple(sorted(deco)))
    if key in art._cache:
        return art._cache[key]
    c = art.Canvas(RW, RH, RU)
    # 牆：奶油色 + 粉紅直條紋
    c.rect(0, 0, RW, FLOOR, (255, 240, 214) if not night else (226, 206, 190))
    for x in range(3, RW, 8):
        c.rect(x, 0, 2, FLOOR, (255, 222, 214) if not night else (210, 186, 182))
    c.rect(0, FLOOR - 4, RW, 4, "K")                   # 踢腳板
    c.rect(0, FLOOR - 3, RW, 2, (186, 136, 96))
    # 地板：木頭
    c.rect(0, FLOOR, RW, RH - FLOOR, (214, 166, 112) if not night else (176, 132, 96))
    for y in range(FLOOR + 3, RH, 4):
        c.rect(0, y, RW, 1, (186, 136, 90) if not night else (150, 110, 80))
        for x in range((y * 7) % 13, RW, 23):
            c.rect(x, y - 3, 1, 3, (186, 136, 90) if not night else (150, 110, 80))
    # 窗戶（白天藍天、晚上星空和月亮）
    wx, wy, ww, wh = 30, 7, 22, 18
    c.rect(wx - 3, wy - 2, ww + 6, wh + 4, "K")
    c.rect(wx - 2, wy - 1, ww + 4, wh + 2, "C")
    sky_top, sky_bot = ((150, 210, 250), (214, 238, 255)) if not night else ((30, 36, 80), (64, 70, 130))
    for i in range(wh):
        t = i / (wh - 1)
        c.rect(wx, wy + i, ww, 1, tuple(int(a + (b - a) * t) for a, b in zip(sky_top, sky_bot)))
    if night:
        c.rect(wx + 15, wy + 3, 4, 4, (255, 240, 180)); c.rect(wx + 16, wy + 3, 3, 3, (64, 70, 130))
        c.rect(wx + 15, wy + 3, 2, 4, (255, 240, 180))
        for sx, sy in ((wx + 3, wy + 4), (wx + 8, wy + 2), (wx + 6, wy + 10), (wx + 18, wy + 12)):
            c.px(sx, sy, "W")
    else:
        c.rect(wx + 3, wy + 4, 6, 2, "W"); c.rect(wx + 4, wy + 3, 3, 1, "W")
        c.rect(wx + 13, wy + 9, 5, 2, "W")
    c.rect(wx + ww // 2, wy, 1, wh, "C"); c.rect(wx, wy + wh // 2, ww, 1, "C")
    for side in (wx - 4, wx + ww + 1):                 # 窗簾
        c.rect(side, wy - 3, 3, wh + 7, "K")
        c.rect(side + 1, wy - 2, 1, wh + 5, "P")
    c.rect(wx - 5, wy - 4, ww + 10, 2, "K")
    c.rect(wx - 4, wy - 4, ww + 8, 1, "T")
    if "snow" in deco:                                  # 窗外下雪
        for sx, sy in ((wx + 2, wy + 13), (wx + 9, wy + 6), (wx + 14, wy + 14), (wx + 19, wy + 8)):
            c.px(sx, sy, "W")
    # 門（從裡面看，也有肉球）
    c.rect(3, 13, 15, FLOOR - 13, "K")
    c.rect(4, 14, 13, FLOOR - 14, "Z" if not night else (200, 80, 120))
    for x in range(6, 17, 3):
        c.rect(x, 15, 1, FLOOR - 16, (214, 98, 132))
    c.grid(5, 19, art.DOOR_PAW)
    c.rect(14, 28, 2, 2, "Y")
    # 擺設：先畫地上的，再畫靠牆的
    items = ["rug"] if "rug" in owned else []
    items += ["painting", "scratcher", "plant", "lamp", "fishtank", "yarn"]
    for it in items:
        if it in owned and it in SPOTS and it != "rug":
            _draw_item(c, it, *SPOTS[it], night=night)
        elif it == "rug":
            _draw_item(c, it, *SPOTS[it])
    _draw_item(c, "cushion", *SPOTS["cushion"])
    _draw_item(c, "bowl", *SPOTS["bowl"])
    if "halloween" in deco:
        _draw_item(c, "pumpkin", *SPOTS["pumpkin"])
    if "xmas" in deco:
        _draw_item(c, "xmas_tree", *SPOTS["xmas_tree"])
    if "lny" in deco:
        _draw_item(c, "lantern", *SPOTS["lantern"])
        _draw_item(c, "lantern", 70, 2)
    if night:                                           # 晚上整個房間暗一點、偏藍
        c.rect(0, 0, RW, RH, QColor(30, 30, 80, 46))
        if "lamp" in owned:
            lx, ly = SPOTS["lamp"]
            c.rect(lx - 10, ly - 4, 30, 40, QColor(255, 210, 120, 40))
    art._cache[key] = c.pixmap()
    return art._cache[key]


class Room(QWidget):
    """畫房間和在家的貓咪。"""

    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.setFixedSize(RW * RU, RH * RU)
        self.acts = {}       # cat -> dict(kind, x, dir, t)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.CoarseTimer)
        self.timer.timeout.connect(self._step)
        self._n = 0

    def start(self):
        self.timer.start(FRAME_MS)
        self._sync()

    def stop(self):
        self.timer.stop()

    def _sync(self):
        res = list(self.ctrl.house.residents)
        for c in list(self.acts):
            if c not in res:
                self.acts.pop(c)
        for c in res:
            if c not in self.acts:
                self.acts[c] = self._new_act(c)

    def _new_act(self, cat):
        owned = self.ctrl.progress.owned
        taken = {a["kind"] for a in self.acts.values()}
        kinds = ["sleep", "eat", "walk", "walk", "sit"]
        if "yarn" in owned:
            kinds.append("play")
        if "scratcher" in owned:
            kinds.append("scratch")
        if self.ctrl.sleeping:
            kinds = ["sleep"]
        kinds = [k for k in kinds if k in ("walk", "sit") or k not in taken] or ["walk"]
        k = random.choice(kinds)
        x = {"sleep": SPOTS["cushion"][0] + 1, "eat": SPOTS["bowl"][0] + 9,
             "play": SPOTS["yarn"][0] - 12, "scratch": SPOTS["scratcher"][0] + 9}.get(k, random.uniform(10, RW - 26))
        return {"kind": k, "x": float(x), "dir": random.choice((1, 3)), "t": random.randint(25, 70),
                "tx": random.uniform(8, RW - 26)}

    def _step(self):
        self._n += 1
        self._sync()
        for cat, a in self.acts.items():
            a["t"] -= 1
            if a["t"] <= 0:
                self.acts[cat] = self._new_act(cat)
                continue
            if a["kind"] == "walk":
                d = a["tx"] - a["x"]
                if abs(d) < 1:
                    a["tx"] = random.uniform(8, RW - 26)
                else:
                    a["x"] += max(-1.2, min(1.2, d))
                    a["dir"] = 1 if d > 0 else 3
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        night = seasons.is_night()
        deco = seasons.decorations() if self.ctrl.seasonal else set()
        p.drawPixmap(0, 0, room_background(self.ctrl.progress.owned, night, deco))
        # 貓咪：地板上（腳踩在 y=FLOOR+12 左右，愈下面的愈前面）
        order = sorted(self.acts.items(), key=lambda kv: kv[1]["kind"] != "sleep")
        for cat, a in order:
            fr = sprites.cat_frames(cat.color, CAT_SCALE, cat.hat if self.ctrl.progress.has(cat.hat or "") else None,
                                    cat.neck if self.ctrl.progress.has(cat.neck or "") else None)
            k = a["kind"]
            if k == "sleep":
                pm = fr["sleep"][0][(self._n // 6) % 2]
                feet = SPOTS["cushion"][1] + 4
            elif k == "eat":
                pm = fr["walk"][3][0 if (self._n // 2) % 2 else 2]
                feet = FLOOR + 12
            elif k == "walk":
                pm = fr["walk"][a["dir"]][(self._n // 2) % 3]
                feet = FLOOR + 14
            elif k in ("play", "scratch"):
                side = 1 if k == "play" else 3
                pm = fr["expr"]["excited" if (self._n // 3) % 2 else "happy"][0 if side == 1 else 1]
                feet = FLOOR + 13
            else:
                pm = fr["walk"][2][1]
                feet = FLOOR + 10
            ch = pm.height() / pm.devicePixelRatio()
            y = feet * RU - (ch - sprites.FOOT_GAP * CAT_SCALE)
            p.drawPixmap(int(a["x"] * RU), int(y), pm)
            if k == "sleep" and (self._n // 6) % 2:
                zz = sprites.effect("zzz", 2)
                p.drawPixmap(int(a["x"] * RU + 50), int(y + 40), zz)
        if not self.acts:
            p.fillRect(QRect(0, 0, self.width(), self.height()), QColor(255, 255, 255, 60))


def _Panel(ctrl, PixelButton):
    from panels import U, PixelPanel

    class Panel(PixelPanel):
        def __init__(self):
            super().__init__()
            self.ctrl = ctrl
            lay = QVBoxLayout(self)
            lay.setContentsMargins(U * 2 + 8, U + 6, U * 2 + 8 + U, U * 2 + 10 + U)
            lay.setSpacing(8)
            self.title = QLabel()
            lay.addWidget(self._title_bar(pixel.icon_pixmap("home", 2), self.title, self.close_room))
            self.room = Room(ctrl)
            frame = QWidget()
            fl = QHBoxLayout(frame)
            fl.setContentsMargins(0, 0, 0, 0)
            fl.addWidget(self.room)
            lay.addWidget(frame)
            foot = QHBoxLayout()
            self.status = QLabel()
            self.status.setFont(pixel.font(12))
            self.status.setStyleSheet("color: #7a6a58;")
            foot.addWidget(self.status)
            foot.addStretch()
            self.call_btn = PixelButton()
            self.call_btn.clicked.connect(self._call)
            foot.addWidget(self.call_btn)
            lay.addLayout(foot)

        def open_near(self, house):
            self.refresh()
            self.adjustSize()
            x = house.x() + house.width() + 6
            y = house.y() + house.height() - self.height()
            from PySide6.QtGui import QGuiApplication
            g = (QGuiApplication.screenAt(house.geometry().center())
                 or QGuiApplication.primaryScreen()).availableGeometry()
            if x + self.width() > g.right():
                x = house.x() - self.width() - 6
            self.move(max(g.left(), x), max(g.top(), y))
            self.show()
            from macos import show_on_all_spaces
            show_on_all_spaces(self)
            self.raise_()
            self.room.start()

        def refresh(self):
            n = len(self.ctrl.house.residents)
            self.title.setText(tr("inside_title"))
            self.status.setText(tr("inside_n", n=n) if n else tr("inside_empty"))
            self.call_btn.setText(tr("come_out") if n else tr("go_home_all"))

        def _call(self):
            if self.ctrl.house.residents:
                self.ctrl.come_out()
            else:
                self.ctrl.go_home_all()
            from PySide6.QtCore import QTimer as _T
            _T.singleShot(1500, self.refresh)

        def close_room(self):
            self.room.stop()
            self.hide()

        def hideEvent(self, e):
            self.room.stop()
            super().hideEvent(e)

    return Panel()


def make_panel(ctrl):
    from panels import PixelButton
    return _Panel(ctrl, PixelButton)
