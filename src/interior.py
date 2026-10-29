"""貓屋裡面：像娃娃屋一樣把貓屋的前牆拿掉，直接在桌面上看到屋子裡。

這不是另一個視窗：貓屋本身會變成剖面圖，在家的貓咪就是桌面上真正的貓，
可以點、可以拖、可以按右鍵。這個檔案只負責畫房間（畫好一次就快取起來）。
"""
from PySide6.QtGui import QColor

import art

# ---------------- 尺寸（格） ---------------- #
IW, IH = 104, 76            # 整張剖面圖
IG = 66                     # 地板表面（貓咪腳踩的位置）
GRASS = 72                  # 草地頂端（貼齊桌面底部）
ROOM_L, ROOM_R = 14, 89     # 房間內牆的左右邊（貓咪中心可以走的範圍會再內縮）
EAVE = 24                   # 屋簷
CHIMNEY = (77, 0)           # 煙囪口

DOOR = (16, 41, 12, 25)     # 室內的門 (x, y, w, h)
CUSHION_X = (66, 87)        # 軟墊
BOWL_X = (37, 46)           # 碗

# 房屋外觀用的顏色（和 house.png 同一組）
C = {
    "K": (58, 55, 55), "R": (238, 104, 94), "r": (200, 70, 80), "h": (255, 156, 132), "e": (172, 58, 74),
    "B": (222, 128, 98), "b": (178, 88, 76), "m": (246, 204, 176), "c": (124, 112, 140),
    "T": (255, 222, 148), "t": (238, 188, 112), "l": (255, 242, 200), "Cr": (255, 251, 242),
    "Q": (98, 200, 190), "q": (56, 150, 152), "Y": (255, 214, 84), "y": (232, 170, 56),
    "G": (108, 198, 96), "g": (64, 150, 84), "j": (172, 228, 112), "P": (255, 132, 176),
    "p": (226, 88, 140), "V": (182, 146, 244), "W": (255, 255, 255), "O": (255, 168, 64),
    "Z": (246, 136, 160), "z": (214, 98, 132), "N": (255, 236, 222), "n": (255, 196, 206),
    # 室內
    "wall": (255, 238, 218), "stripe": (255, 224, 212), "dot": (250, 200, 196),
    "wain": (184, 230, 218), "wain_d": (146, 204, 192), "wain_l": (214, 244, 236),
    "wood": (214, 160, 108), "wood_d": (176, 124, 82), "wood_l": (240, 196, 140),
    "attic": (132, 90, 78), "attic_d": (104, 70, 62), "beam": (168, 116, 92),
    "stone": (196, 186, 206), "stone_d": (150, 142, 166),
}

BUSH = [
    "......KKKKK.......",
    "...KKKjjGGGKKK....",
    "..KjjGPGGjGGGGKK..",
    ".KjGPpPGGGGVGGGGK.",
    ".KGGGPGGYGVWVGjGK.",
    "KjGGGGGYOYGVGGPGGK",
    "KGGVGGGGYGGGGPpPgK",
    "KgGWVGgGGGgGGGPGgK",
    "KggVgggggggggggggK",
]

# 精緻一點的貓掌：粉紅門上的奶油色大肉球 + 四顆小肉球，帶一圈深粉紅描邊和亮點
PAW = [
    "..zz....zz..",
    ".zNNz..zNNz.",
    ".zNnz..zNnz.",
    "..zz....zz..",
    "zz..zzzz..zz",
    "zNz.zNNz.zNz",
    "zNz.zNNz.zNz",
    ".z.zNNNNz.z.",
    "..zNNNNNNz..",
    "..zNNNnNNz..",
    "..zNNnnnNz..",
    "...zNNNNz...",
    "....zzzz....",
]


def _c(k):
    return C.get(k) or art.COLORS[k]


class _Canvas(art.Canvas):
    def c(self, col):
        if isinstance(col, str):
            col = _c(col)
        return QColor(*col) if isinstance(col, tuple) else col

    def grid(self, x, y, grid, flip=False):
        for gy, row in enumerate(grid):
            row = row[::-1] if flip else row
            for gx, ch in enumerate(row):
                if ch != ".":
                    self.px(x + gx, y + gy, ch)


def glow(c, cx, cy, r, color=(255, 214, 140), alphas=(70, 46, 26), clip=None):
    """像素風的圓形光暈：幾圈一格一格的同心圓，最外圈用棋盤格點出漸層。"""
    import math
    n = len(alphas)
    for y in range(int(cy - r), int(cy + r) + 1):
        for x in range(int(cx - r), int(cx + r) + 1):
            if clip and not (clip[0] <= x <= clip[1] and clip[2] <= y <= clip[3]):
                continue
            d = math.hypot((x - cx), (y - cy) * 1.15) / r
            if d > 1:
                continue
            band = min(n - 1, int(d * n))
            c.px(x, y, QColor(*color, alphas[band]))


def _roof_half(y, apex=2):
    return int((y - apex) * 50 / 22) + 1


# ---------------- 擺設 ---------------- #
def _shadow(c, x, w, y=IG):
    c.rect(x + 1, y, w - 2, 1, QColor(60, 40, 40, 60))


def draw_item(c, item, night=False):
    if item == "cushion":
        x0, x1 = CUSHION_X
        w = x1 - x0
        _shadow(c, x0, w)
        c.rect(x0 + 1, IG - 7, w - 2, 1, "K")
        c.rect(x0, IG - 6, w, 6, "K")
        c.rect(x0 + 1, IG - 6, w - 2, 5, "P")
        c.rect(x0 + 2, IG - 7, w - 4, 2, (255, 180, 206))
        c.rect(x0 + 3, IG - 6, w - 6, 1, (255, 214, 228))
        c.rect(x0 + 1, IG - 2, w - 2, 1, (214, 96, 140))
        for x in range(x0 + 4, x1 - 2, 4):
            c.px(x, IG - 4, (255, 214, 228))
    elif item == "bowl":
        x0, x1 = BOWL_X
        _shadow(c, x0, x1 - x0)
        c.rect(x0 + 2, IG - 6, 5, 1, (186, 120, 70))
        c.px(x0 + 3, IG - 7, (214, 150, 90)); c.px(x0 + 5, IG - 7, (186, 120, 70))
        c.rect(x0, IG - 5, x1 - x0, 1, "K")
        c.rect(x0, IG - 4, x1 - x0, 4, "K")
        c.rect(x0 + 1, IG - 4, x1 - x0 - 2, 3, (98, 150, 214))
        c.rect(x0 + 1, IG - 4, x1 - x0 - 2, 1, (150, 196, 240))
        c.px(x0 + 4, IG - 2, "W"); c.px(x0 + 5, IG - 2, "W")
    elif item == "rug":
        c.rect(47, IG - 1, 22, 2, "K")
        c.rect(48, IG - 1, 20, 1, (246, 196, 120))
        for x in range(48, 68, 3):
            c.px(x, IG - 1, (236, 140, 100))
    elif item == "plant":                            # 窗台上的小盆栽
        c.rect(54, 44, 6, 5, "K")
        c.rect(55, 45, 4, 3, (226, 128, 92))
        c.rect(55, 45, 4, 1, (246, 162, 120))
        for dx, dy, h in ((56, 38, 6), (54, 40, 4), (58, 39, 5)):
            c.rect(dx, dy, 2, h, "K")
            c.rect(dx, dy + 1, 1, h - 1, "G")
            c.px(dx + 1, dy + 1, "j")
    elif item == "lamp":
        x = 84
        c.rect(x - 1, 40, 8, 6, "K")
        c.rect(x, 41, 6, 4, (255, 236, 170) if night else (255, 214, 120))
        c.rect(x, 41, 6, 1, "W" if night else (255, 236, 170))
        c.rect(x + 2, 46, 2, IG - 47, "K")
        c.rect(x, IG - 1, 6, 1, "K")
    elif item == "painting":
        c.rect(66, 29, 13, 10, "K")
        c.rect(67, 30, 11, 8, (214, 160, 108))
        c.rect(68, 31, 9, 6, (186, 228, 255))
        c.rect(68, 35, 9, 2, "G")
        c.rect(73, 32, 2, 2, "Y")
        c.rect(69, 34, 3, 1, "j")
    elif item == "scratcher":
        _shadow(c, 47, 8)
        c.rect(47, IG - 2, 8, 2, "K")
        c.rect(48, IG - 2, 6, 1, (186, 136, 96))
        c.rect(49, IG - 16, 4, 14, "K")
        c.rect(50, IG - 15, 2, 13, (238, 204, 152))
        for y in range(IG - 14, IG - 2, 2):
            c.rect(50, y, 2, 1, (214, 168, 112))
        c.rect(48, IG - 18, 6, 2, "K")
        c.rect(49, IG - 18, 4, 1, "Q")
    elif item == "fishtank":
        c.rect(63, 49, 18, 2, "K")                      # 牆上的層板
        c.rect(64, 49, 16, 1, (214, 160, 108))
        c.rect(65, 40, 14, 9, "K")
        c.rect(66, 41, 12, 7, (120, 200, 240))
        c.rect(66, 41, 12, 2, (186, 228, 255))
        c.rect(66, 46, 12, 2, (238, 204, 152))
        c.rect(68, 43, 1, 3, "G"); c.rect(76, 42, 1, 4, "G")
        c.rect(71, 43, 3, 2, "O"); c.px(74, 43, "O"); c.px(72, 43, "K")
    elif item == "yarn":
        c.grid(58, IG - 7, art.YARN[0])
        c.rect(57, IG - 1, 2, 1, (226, 88, 140))
    elif item == "pumpkin":
        c.grid(29, IG - 8, art.PUMPKIN)
    elif item == "xmas_tree":
        x = 30
        for i, w in enumerate((3, 5, 7, 9, 11, 13)):
            c.rect(x + 7 - w // 2, IG - 23 + i * 3, w, 3, "K")
            c.rect(x + 8 - w // 2, IG - 23 + i * 3, w - 2, 2, "G")
            c.rect(x + 8 - w // 2, IG - 23 + i * 3, w - 2, 1, "j")
        c.grid(x + 5, IG - 27, ["..K..", ".KYK.", "KYYYK", ".KYK.", "..K.."])
        for dx, dy, col in ((5, -18, "R"), (9, -15, "B"), (4, -12, "Y"), (10, -9, "R"), (6, -7, "B")):
            c.px(x + dx, IG + dy, col)
        c.rect(x + 6, IG - 5, 3, 5, "K"); c.rect(x + 7, IG - 5, 1, 5, "T")
    elif item == "lantern":
        for x in (34, 72):
            c.rect(x + 2, 27, 1, 3, "K")
            c.grid(x, 30, art.LANTERN)


def item_preview(item, unit=2):
    """商店裡的擺設預覽圖（單獨把那一樣畫出來，裁掉空白）。"""
    boxes = {"rug": (46, IG - 2, 24, 4), "plant": (53, 37, 8, 13), "lamp": (82, 39, 10, 28),
             "painting": (65, 28, 15, 12), "scratcher": (46, IG - 19, 10, 20),
             "fishtank": (62, 39, 20, 13), "yarn": (56, IG - 8, 10, 9), "cushion": (65, IG - 8, 24, 9)}
    x, y, w, h = boxes.get(item, (0, 0, 12, 12))
    c = _Canvas(IW, IH, unit)
    draw_item(c, item)
    pm = c.pixmap()
    d = pm.devicePixelRatio()
    out = pm.copy(int(x * unit * d), int(y * unit * d), int(w * unit * d), int(h * unit * d))
    out.setDevicePixelRatio(d)
    return out


# ---------------- 整間屋子的剖面 ---------------- #
SKY = {                      # 窗外天空：(上, 下)
    "morning": ((255, 196, 176), (255, 236, 196)),
    "day": ((150, 210, 250), (214, 238, 255)),
    "dusk": ((112, 84, 168), (252, 156, 104)),
    "night": ((22, 26, 62), (52, 58, 112)),
}


def dollhouse(owned, phase, deco, unit):
    if phase is True or phase is False:          # 舊的呼叫方式：night = True/False
        phase = "night" if phase else "day"
    night = phase == "night"
    lit = phase in ("dusk", "night")             # 傍晚就開燈
    key = ("dollhouse", tuple(sorted(owned)), phase, tuple(sorted(deco)), unit)
    if key in art._cache:
        return art._cache[key]
    c = _Canvas(IW, IH, unit)

    # 煙囪（畫在屋頂後面）
    cx = CHIMNEY[0] - 3
    c.rect(cx, 1, 7, 16, "K")
    c.rect(cx + 1, 2, 5, 15, "B")
    for y in range(4, 16, 3):
        c.rect(cx + 1, y, 5, 1, "m")
        c.px(cx + (2 if (y // 3) % 2 else 4), y + 1, "m")
    c.rect(cx + 1, 2, 1, 14, "b")
    c.rect(cx - 1, 0, 9, 3, "K")
    c.rect(cx, 1, 7, 1, "c")

    # 屋頂：外面一圈紅色瓦片，裡面是看得到樑的閣樓
    for y in range(2, EAVE + 1):
        half = _roof_half(y)
        x0, x1 = 52 - half, 51 + half
        c.rect(x0, y, x1 - x0 + 1, 1, "K")
        c.rect(x0 + 1, y, x1 - x0 - 1, 1, "R")
        row = y - 2
        if row % 4 == 3:
            c.rect(x0 + 1, y, x1 - x0 - 1, 1, "r")
        if row % 4 == 1:
            for x in range(x0 + 2 + (row // 4) % 2 * 2, x1 - 1, 4):
                c.px(x, y, "h")
        c.rect(x0 + 1, y, 2, 1, "h")
    for y in range(8, EAVE):
        half = _roof_half(y, apex=8) - 1
        x0, x1 = 52 - half, 51 + half
        if x1 <= x0:
            continue
        c.rect(x0, y, x1 - x0 + 1, 1, "K")
        c.rect(x0 + 1, y, x1 - x0 - 1, 1, "attic")
        c.px(x0 + 1, y, "attic_d"); c.px(x1 - 1, y, "attic_d")
    c.rect(51, 9, 2, EAVE - 9, "beam")                    # 中柱
    c.rect(51, 9, 1, EAVE - 9, (190, 140, 112))
    c.rect(36, 17, 32, 2, "beam")                         # 橫樑
    c.rect(36, 17, 32, 1, (190, 140, 112))
    c.rect(37, 19, 30, 1, "attic_d")
    # 閣樓裡的小東西：一盞小燈和一個毛線籃
    c.rect(44, 19, 1, 2, "K")
    c.rect(43, 21, 3, 2, (255, 226, 140) if lit else (236, 200, 120))
    c.rect(56, 21, 6, 3, "K"); c.rect(57, 21, 4, 2, (214, 168, 112)); c.px(58, 20, "P"); c.px(59, 20, "V")
    # 屋簷 + 天花板的樑
    c.rect(0, EAVE, IW, 2, "K")
    c.rect(1, EAVE, IW - 2, 1, "e")
    c.rect(ROOM_L - 4, EAVE + 2, ROOM_R - ROOM_L + 9, 3, "K")
    c.rect(ROOM_L - 3, EAVE + 2, ROOM_R - ROOM_L + 7, 2, "wood")
    c.rect(ROOM_L - 3, EAVE + 2, ROOM_R - ROOM_L + 7, 1, "wood_l")

    # 後牆：壁紙（直條紋 + 小點點）、腰板（薄荷綠）、踢腳板
    top = EAVE + 5
    c.rect(ROOM_L, top, ROOM_R - ROOM_L + 1, IG - top, "wall")
    for x in range(ROOM_L + 3, ROOM_R, 7):
        c.rect(x, top, 2, 53 - top, "stripe")
        for y in range(top + 2 + (x // 7) % 2 * 3, 53, 6):
            c.px(x, y, "dot")
    c.rect(ROOM_L, top, ROOM_R - ROOM_L + 1, 1, (236, 214, 196))   # 天花板下的陰影
    c.rect(ROOM_L, 53, ROOM_R - ROOM_L + 1, 2, "wood_d")
    c.rect(ROOM_L, 53, ROOM_R - ROOM_L + 1, 1, "wood_l")
    c.rect(ROOM_L, 55, ROOM_R - ROOM_L + 1, IG - 58, "wain")
    for x in range(ROOM_L + 2, ROOM_R, 5):
        c.rect(x, 55, 1, IG - 58, "wain_d")
        c.rect(x + 1, 55, 1, IG - 58, "wain_l")
    c.rect(ROOM_L, IG - 3, ROOM_R - ROOM_L + 1, 1, "K")
    c.rect(ROOM_L, IG - 2, ROOM_R - ROOM_L + 1, 2, "wood")
    c.rect(ROOM_L, IG - 2, ROOM_R - ROOM_L + 1, 1, "wood_l")

    # 窗戶：早上粉橘色的晨光、白天藍天白雲、傍晚紫橘色的夕陽、晚上深藍夜空和月亮星星
    wx, wy, ww, wh = 37, 31, 22, 16
    c.rect(wx - 2, wy - 2, ww + 4, wh + 4, "K")
    c.rect(wx - 1, wy - 1, ww + 2, wh + 2, "Cr")
    top_c, bot_c = SKY[phase]
    for i in range(wh):
        t = i / (wh - 1)
        c.rect(wx, wy + i, ww, 1, tuple(int(a + (b - a) * t) for a, b in zip(top_c, bot_c)))
    if phase == "morning":                       # 剛升起來的太陽和淡淡的雲
        c.rect(wx + 4, wy + 10, 5, 4, (255, 246, 214)); c.rect(wx + 5, wy + 9, 3, 6, (255, 246, 214))
        c.rect(wx + 5, wy + 10, 3, 4, (255, 255, 236))
        c.rect(wx + 12, wy + 4, 6, 2, (255, 236, 236)); c.rect(wx + 13, wy + 3, 3, 1, (255, 236, 236))
        c.rect(wx + 1, wy + wh - 2, ww - 2, 2, (182, 214, 160))       # 遠方的山丘
        c.rect(wx + 9, wy + wh - 3, 8, 1, (182, 214, 160))
    elif phase == "dusk":                        # 夕陽一半沉到山後面，天邊有一抹雲
        c.rect(wx + 12, wy + 9, 6, 4, (255, 214, 120)); c.rect(wx + 13, wy + 8, 4, 1, (255, 214, 120))
        c.rect(wx + 13, wy + 9, 4, 3, (255, 236, 160))
        c.rect(wx + 2, wy + 6, 7, 1, (236, 140, 150)); c.rect(wx + 4, wy + 5, 3, 1, (236, 140, 150))
        c.px(wx + 4, wy + 2, (255, 236, 200))
        c.rect(wx, wy + wh - 3, ww, 3, (92, 64, 110))
        c.rect(wx + 6, wy + wh - 4, 7, 1, (92, 64, 110))
    elif night:
        c.rect(wx + 15, wy + 2, 4, 4, (255, 240, 190))
        c.rect(wx + 17, wy + 2, 2, 3, (22, 26, 62))
        for sx, sy in ((wx + 3, wy + 3), (wx + 8, wy + 1), (wx + 6, wy + 9), (wx + 19, wy + 11), (wx + 12, wy + 6)):
            c.px(sx, sy, "W")
    else:
        c.rect(wx + 3, wy + 4, 6, 2, "W"); c.rect(wx + 4, wy + 3, 3, 1, "W")
        c.rect(wx + 13, wy + 10, 5, 2, "W"); c.rect(wx + 14, wy + 9, 2, 1, "W")
    if "snow" in deco:
        for sx, sy in ((wx + 2, wy + 12), (wx + 9, wy + 5), (wx + 15, wy + 13), (wx + 20, wy + 7), (wx + 5, wy + 8)):
            c.px(sx, sy, "W")
    c.rect(wx + ww // 2, wy, 1, wh, "Cr")
    c.rect(wx, wy + wh // 2, ww, 1, "Cr")
    c.rect(wx - 3, wy + wh + 1, ww + 6, 2, "K")           # 窗台
    c.rect(wx - 2, wy + wh + 1, ww + 4, 1, "wood_l")
    for side, flip in ((wx - 5, False), (wx + ww + 2, True)):   # 有皺褶的窗簾
        c.rect(side, wy - 3, 4, wh + 6, "K")
        c.rect(side + 1, wy - 2, 2, wh + 4, "P")
        c.rect(side + (2 if not flip else 1), wy - 2, 1, wh + 4, (255, 180, 206))
    c.rect(wx - 6, wy - 4, ww + 12, 2, "K")
    c.rect(wx - 5, wy - 4, ww + 10, 1, "wood")

    # 白天：從窗戶斜斜照進來的光（早上偏粉橘、傍晚偏橘紅，斜得更厲害）
    if phase != "night":
        beam = {"morning": (QColor(255, 226, 196, 52), 2), "day": (QColor(255, 255, 230, 46), 2),
                "dusk": (QColor(255, 170, 110, 46), 1)}[phase]
        for i in range(IG - (wy + wh + 3)):
            y = wy + wh + 3 + i
            shift = i // 2 if beam[1] == 2 else -i
            c.rect(wx + 2 + shift, y, ww - 4, 1, beam[0])

    # 室內的門（粉紅木門 + 精緻的貓掌）
    dx, dy, dw, dh = DOOR
    c.rect(dx - 2, dy - 2, dw + 4, dh + 2, "K")
    c.rect(dx - 1, dy - 1, dw + 2, dh + 1, "Q")
    c.rect(dx - 1, dy - 1, 1, dh + 1, "q")
    c.rect(dx, dy, dw, dh, "Z")
    for x in range(dx + 2, dx + dw, 3):
        c.rect(x, dy + 1, 1, dh - 1, (232, 118, 148))
    c.rect(dx, dy, dw, 1, (255, 170, 190))
    c.grid(dx, dy + 3, PAW)
    c.rect(dx + dw - 3, dy + 14, 2, 2, "K")
    c.px(dx + dw - 3, dy + 14, "Y")

    # 牆上的小時鐘
    c.rect(81, 30, 7, 7, "K")
    c.rect(82, 31, 5, 5, "Cr")
    c.px(84, 32, "K"); c.px(84, 33, "K"); c.px(85, 33, "K")
    c.px(82, 31, "K"); c.px(86, 31, "K"); c.px(82, 35, "K"); c.px(86, 35, "K")

    # 天花板的吊燈（一直都在；晚上會亮）
    c.rect(26, EAVE + 5, 1, 4, "K")
    c.rect(24, EAVE + 9, 5, 2, "K")
    c.rect(25, EAVE + 9, 3, 1, (255, 236, 170) if lit else (236, 214, 170))
    c.px(26, EAVE + 11, (255, 236, 170) if lit else "K")

    # 側牆的剖面（看得到牆的厚度）
    for x0 in (ROOM_L - 4, ROOM_R + 1):
        c.rect(x0, EAVE + 2, 4, IG - EAVE - 2, "K")
        c.rect(x0 + 1, EAVE + 2, 2, IG - EAVE - 2, "T")
        for y in range(EAVE + 5, IG, 4):
            c.rect(x0 + 1, y, 2, 1, "t")

    # 地板（木頭剖面）、地基、草地
    c.rect(ROOM_L - 4, IG, ROOM_R - ROOM_L + 9, 4, "K")
    c.rect(ROOM_L - 3, IG, ROOM_R - ROOM_L + 7, 3, "wood")
    c.rect(ROOM_L - 3, IG, ROOM_R - ROOM_L + 7, 1, "wood_l")
    for x in range(ROOM_L + 1, ROOM_R, 9):
        c.px(x, IG + 1, "wood_d"); c.px(x, IG + 2, "wood_d")
    c.rect(ROOM_L - 4, IG + 4, ROOM_R - ROOM_L + 9, 2, "stone")
    for x in range(ROOM_L - 3, ROOM_R + 4, 5):
        c.px(x, IG + 4, "stone_d")
    c.rect(0, GRASS, IW, 4, "K")
    c.rect(1, GRASS, IW - 2, 3, "G")
    c.rect(1, GRASS + 2, IW - 2, 1, "g")
    for x in range(2, IW - 2, 3):
        c.px(x, GRASS, "j")

    # 擺設
    items = [i for i in ("painting", "fishtank", "plant", "scratcher", "lamp", "rug", "yarn") if i in owned]
    for it in ("painting", "fishtank", "plant", "scratcher", "lamp"):
        if it in items:
            draw_item(c, it, lit)
    if "rug" in items:
        draw_item(c, "rug")
    if "xmas" in deco:
        draw_item(c, "xmas_tree")
    draw_item(c, "bowl")
    draw_item(c, "cushion")
    if "yarn" in items:
        draw_item(c, "yarn")
    if "halloween" in deco:
        draw_item(c, "pumpkin")
    if "lny" in deco:
        draw_item(c, "lantern")
    if "xmas" in deco:
        cols = [(232, 72, 72), (255, 214, 70), (90, 190, 90), (90, 150, 230)]
        for i, x in enumerate(range(ROOM_L + 2, ROOM_R, 5)):
            c.px(x, EAVE + 5, cols[i % 4])
        c.grid(dx + 2, dy - 1, art.WREATH)

    # 早上：整間屋子帶一點粉橘色的晨光
    if phase == "morning":
        c.rect(ROOM_L, top, ROOM_R - ROOM_L + 1, IG - top + 3, QColor(255, 170, 140, 22))
    # 傍晚：房間染上夕陽的橘色，燈也亮起來了
    if phase == "dusk":
        room = (ROOM_L, ROOM_R, top, IG + 3)
        c.rect(ROOM_L, top, ROOM_R - ROOM_L + 1, IG - top + 3, QColor(240, 110, 60, 40))
        glow(c, 26, EAVE + 13, 12, alphas=(46, 30, 16), clip=room)
        if "lamp" in owned:
            glow(c, 87, 47, 10, alphas=(46, 30, 16), clip=room)
            c.rect(84, 41, 6, 4, (255, 240, 190))
        c.rect(25, EAVE + 9, 3, 2, (255, 244, 200))
    # 晚上：房間變暗偏藍，吊燈和立燈照出一圈一圈的暖光
    if night:
        room = (ROOM_L, ROOM_R, top, IG + 3)
        c.rect(ROOM_L, top, ROOM_R - ROOM_L + 1, IG - top + 3, QColor(20, 24, 70, 120))
        glow(c, 26, EAVE + 13, 15, clip=room)
        if "lamp" in owned:
            glow(c, 87, 47, 13, clip=room)
            c.rect(84, 41, 6, 4, (255, 240, 190))
        c.rect(25, EAVE + 9, 3, 2, (255, 244, 200))

    # 兩側外面的花叢
    c.grid(-4, GRASS - 8, BUSH)
    c.grid(IW - 14, GRASS - 8, BUSH, flip=True)

    art._cache[key] = c.pixmap()
    return art._cache[key]
