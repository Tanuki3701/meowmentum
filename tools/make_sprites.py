"""產生所有額外的像素美術（沿用原始精靈圖的畫風與調色盤）。

執行：python3 tools/make_sprites.py

輸出到 assets/sprites/：
- base_walk.png   原始走路圖，改成「語意索引」（程式執行時再換成任何毛色）
- base_sleep.png  睡覺 2 格
- base_expr.png   表情 4 格：開心、興奮、嫌棄、暈眩（面向右）
- base_face.png   正面貓臉 16x14、探頭小臉 10x8、肉球 6x5
- effects.png     愛心、Zzz、閃光、汗滴、音符、5 種口味罐頭（固定顏色）
- house.png       貓屋
以及 assets/icon.png（App 圖示）、assets/tray.png（選單列圖示）。

語意索引：0 透明、1 外框 O、2 腮紅 R、3 陰影 D、4 粉紅 P、5 中間色 M、6 亮色 L、
7 眼睛 E、8 眼睛亮部 F、9 白色 W。
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")
SPRITES = os.path.join(ASSETS, "sprites")

SEM = ".ORDPMLEFW"                       # 索引 → 語意字元
ORANGE_IDX = {0: ".", 1: "O", 2: "R", 3: "D", 4: "P", 5: "M", 6: "L"}
INK = (58, 55, 55)
# 用橘貓的顏色當作 base 圖的預覽色（執行時會被換掉）
BASE_PALETTE = [(0, 0, 0), INK, (177, 78, 69), (153, 107, 74), (186, 108, 76), (195, 151, 83),
                (217, 183, 92), INK, INK, (255, 255, 255)]

# 原圖的毛色（語意 → RGB），之後也給程式內建毛色用
BUILTIN = {
    "orange": dict(O=INK, R=(177, 78, 69), D=(153, 107, 74), P=(186, 108, 76), M=(195, 151, 83),
                   L=(217, 183, 92), E=INK, F=INK),
    "black": dict(O=INK, R=(177, 78, 69), D=(48, 39, 50), P=(186, 108, 76), M=(58, 49, 58),
                  L=(75, 68, 76), E=(0, 107, 70), F=(73, 146, 49)),
    "white": dict(O=INK, R=(188, 139, 109), D=(130, 124, 124), P=(214, 179, 157), M=(183, 179, 178),
                  L=(239, 233, 231), E=INK, F=INK),
    "brown": dict(O=INK, R=(188, 139, 109), D=(81, 34, 30), P=(214, 179, 157), M=(128, 53, 38),
                  L=(143, 68, 38), E=INK, F=INK),
}


# ---------------- 小工具 ---------------- #
class Grid:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.c = [["."] * w for _ in range(h)]

    def put(self, x, y, text):
        for i, ch in enumerate(text):
            if ch != " " and 0 <= x + i < self.w and 0 <= y < self.h:
                self.c[y][x + i] = ch

    def art(self, x, y, lines):
        for i, line in enumerate(lines):
            self.put(x, y + i, line)

    def get(self, x, y):
        return self.c[y][x]

    def set(self, x, y, ch):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.c[y][x] = ch


def save_semantic(grids, path, cell=(32, 48)):
    """把語意格子存成調色盤 PNG（索引 = SEM 的位置）。"""
    cw, ch = cell
    img = Image.new("P", (cw * len(grids), ch), 0)
    pal = []
    for rgb in BASE_PALETTE:
        pal += list(rgb)
    img.putpalette(pal + [0] * (768 - len(pal)))
    for i, g in enumerate(grids):
        for y in range(g.h):
            for x in range(g.w):
                if g.c[y][x] != ".":
                    img.putpixel((i * cw + x, y), SEM.index(g.c[y][x]))
    img.save(path, transparency=0)


def read_orange(row, col):
    im = Image.open(os.path.join(SPRITES, "cat_orange-32x48.png"))
    g = Grid(32, 48)
    for y in range(48):
        for x in range(32):
            g.c[y][x] = ORANGE_IDX[im.getpixel((col * 32 + x, row * 48 + y))]
    return g


# ---------------- 走路圖（加上眼睛索引）---------------- #
def base_walk():
    orange = Image.open(os.path.join(SPRITES, "cat_orange-32x48.png"))
    black = Image.open(os.path.join(SPRITES, "cat_black-32x48.png"))
    out = Image.new("P", orange.size, 0)
    pal = []
    for rgb in BASE_PALETTE:
        pal += list(rgb)
    out.putpalette(pal + [0] * (768 - len(pal)))
    for y in range(orange.height):
        for x in range(orange.width):
            v = orange.getpixel((x, y))
            b = black.getpixel((x, y))
            if b == 5:
                v = 7      # 眼睛
            elif b == 8:
                v = 8      # 眼睛亮部
            out.putpixel((x, y), v)
    out.save(os.path.join(SPRITES, "base_walk.png"), transparency=0)


# ---------------- 睡覺 ---------------- #
def sleep_frame(breath):
    side = read_orange(1, 1)
    g = Grid(32, 48)
    b = breath
    g.put(2, 39, "ODO")
    g.put(2, 40, "OMDO")
    g.put(2, 41, "OMMDOOOOOOOOOO")
    g.put(3, 42, "OMMMMMMMMMLLLO")
    g.put(4, 43, "OOOOOOOOOOOOO")
    g.put(9, 33 - b, "DDDDDDDDD")
    g.put(7, 34 - b, "DDMMMMMMMMMDD")
    g.put(6, 35 - b, "DMMLLLMMMLLLMMD")
    for y in range(36 - b, 40):
        g.put(5, y, "DMLLLLLLLLLLLLLLD")
    g.put(5, 40, "DMMLLLLLLLLLLLLMD")
    g.put(6, 41, "DMMMMMMMMMMMMMD")
    g.put(7, 42, "ODDDDDDDDDDDDO")
    dy = 6
    for y in range(23, 35):
        for x in range(16, 30):
            if side.get(x, y) != ".":
                g.set(x, y + dy, side.get(x, y))
    g.set(24, 29 + dy, "L")
    g.set(24, 30 + dy, "L")
    g.set(23, 30 + dy, "O")
    g.set(24, 31 + dy, "O")
    g.set(25, 31 + dy, "O")
    g.put(19, 40, "OMLLLLMO")
    g.put(19, 41, "OMLLOLLMO")
    g.put(19, 42, "OOOOOOOOO")
    return g


# ---------------- 表情（從側面站姿改眼睛和嘴巴）---------------- #
def expression(kind):
    """表情的線條用「眼睛色」畫：淺色貓是深色線，黑貓會是綠色線，一樣看得清楚。"""
    g = read_orange(1, 1)
    g.set(24, 29, "L")       # 先擦掉原本的眼睛
    g.set(24, 30, "L")
    if kind == "happy":      # ^ 瞇眼 + 腮紅
        g.set(23, 30, "E")
        g.set(24, 29, "E")
        g.set(25, 30, "E")
        g.set(23, 31, "R")
        g.set(24, 31, "R")
    elif kind == "excited":  # 閃亮大眼 + 張嘴
        g.set(23, 29, "E")
        g.set(24, 29, "W")
        g.set(23, 30, "E")
        g.set(24, 30, "E")
        g.set(23, 28, "E")
        g.set(24, 28, "E")
        g.set(26, 31, "O")
        g.set(27, 31, "P")
    elif kind == "yuck":     # 嫌棄瞇眼 + 吐舌
        g.set(23, 29, "E")
        g.set(24, 30, "E")
        g.set(23, 31, "E")
        g.set(26, 32, "P")
        g.set(27, 32, "P")
        g.set(27, 33, "O")
        g.set(26, 33, "O")
    elif kind == "dizzy":    # X 眼
        for x, y in ((23, 28), (25, 28), (24, 29), (23, 30), (25, 30)):
            g.set(x, y, "E")
    return g


EXPRESSIONS = ["happy", "excited", "yuck", "dizzy"]

# ---------------- 正面貓臉、探頭小臉、肉球 ---------------- #
FACE = [
    "..OO........OO..",
    ".OMMO......OMMO.",
    ".OMPMO....OMPMO.",
    ".OMPMMOOOOMMPMO.",
    "OMMMMMMMMMMMMMMO",
    "OMMMLLLLLLLLMMMO",
    "OMLLFELLLLFELLMO",
    "OMLLEELLLLEELLMO",
    "OMRRLLLPPLLLRRMO",
    "ODLLLLLOOLLLLLDO",
    "ODMLLLOLLOLLLMDO",
    ".ODMLLLLLLLLMDO.",
    "..ODDMMMMMMDDO..",
    "...OOOOOOOOOO...",
]
PEEK = [
    ".O......O.",
    "OMO....OMO",
    "OPMOOOOMPO",
    "OMMMMMMMMO",
    "OMFMMMMFMO",
    "OMELLLLEMO",
    "OLLLPPLLLO",
    ".OLLLLLLO.",
]
PAW = [
    ".OOOO.",
    "OPLLPO",
    "OLPPLO",
    "OLPPLO",
    ".OOOO.",
]


def face_sheet():
    g = Grid(32, 14)
    g.art(0, 0, FACE)
    g.art(16, 0, PEEK)
    g.art(26, 0, PAW)
    save_semantic([g], os.path.join(SPRITES, "base_face.png"), cell=(32, 14))


# ---------------- 特效與罐頭（固定顏色）---------------- #
FX_COLORS = {
    "K": INK, "W": (255, 255, 255), "R": (217, 72, 59), "P": (238, 150, 160), "Y": (250, 214, 90),
    "y": (236, 168, 56), "B": (120, 180, 235), "b": (70, 120, 200), "S": (176, 180, 190),
    "G": (120, 178, 72), "g": (72, 122, 52), "O": (236, 150, 64), "o": (200, 100, 60),
    "V": (150, 110, 190), "v": (100, 70, 140), "C": (250, 241, 218),
}
HEART = [" KK KK ", "KRRKPPK", "KRPPPPK", " KRPPK ", "  KPK  ", "   K   "]
ZZZ = ["KKKKK", "   K ", "  K  ", " K   ", "KKKKK"]
SPARKLE = ["   K   ", "  KYK  ", " KYWYK ", "KYWWWYK", " KYWYK ", "  KYK  ", "   K   "]
SWEAT = ["  K  ", " KBK ", " KBK ", "KBWBK", "KBBBK", "KbBbK", " KKK "]
NOTE = ["  KKKK", "  KKKK", "  K  K", "  K  K", "KKK KK", "KKKKKK", "KK KK "]
CAN = [
    " KKKKKKKK ",
    "KSSSSSSSSK",
    "K11111111K",
    "K12233221K",
    "K12233221K",
    "K11111111K",
    "KSSSSSSSSK",
    " KKKKKKKK ",
]
# 口味：(標籤主色, 圖案色, 底色)
FLAVORS = {
    "tuna":    ("B", "W", "b"),
    "chicken": ("Y", "o", "y"),
    "salmon":  ("P", "W", "R"),
    "catnip":  ("G", "W", "g"),
    "bitter":  ("V", "G", "v"),
}
FX_POS = {"heart": (0, 0), "zzz": (8, 0), "sparkle": (14, 0), "sweat": (22, 0), "note": (28, 0)}


def draw_art(img, ox, oy, lines, colors, unit=1):
    for y, line in enumerate(lines):
        for x, ch in enumerate(line):
            if ch in (" ", "."):
                continue
            rgb = colors[ch]
            for dy in range(unit):
                for dx in range(unit):
                    img.putpixel((ox + x * unit + dx, oy + y * unit + dy), rgb + (255,))


def effects_sheet():
    img = Image.new("RGBA", (56, 16), (0, 0, 0, 0))
    for name, art in (("heart", HEART), ("zzz", ZZZ), ("sparkle", SPARKLE), ("sweat", SWEAT),
                      ("note", NOTE)):
        draw_art(img, *FX_POS[name], art, FX_COLORS)
    for i, (flavor, (c1, c2, c3)) in enumerate(FLAVORS.items()):
        colors = dict(FX_COLORS)
        colors.update({"1": FX_COLORS[c1], "2": FX_COLORS[c3], "3": FX_COLORS[c2]})
        draw_art(img, i * 11, 8, CAN, colors)
    img.save(os.path.join(SPRITES, "effects.png"))


# ---------------- 貓屋 ---------------- #
HOUSE_COLORS = {
    "K": INK,
    # 屋頂
    "R": (238, 104, 94), "r": (200, 70, 80), "h": (255, 156, 132), "e": (172, 58, 74),
    # 煙囪（磚）
    "B": (222, 128, 98), "b": (178, 88, 76), "m": (246, 204, 176), "c": (124, 112, 140),
    # 牆（奶油黃木板）
    "T": (255, 222, 148), "t": (238, 188, 112), "l": (255, 242, 200),
    "C": (255, 251, 242), "H": (88, 58, 76),
    # 百葉窗、門框（薄荷綠）
    "Q": (98, 200, 190), "q": (56, 150, 152),
    # 門牌、門墊
    "Y": (255, 214, 84), "y": (232, 170, 56), "M": (246, 124, 150), "n": (206, 86, 118),
    # 花叢、草地
    "G": (108, 198, 96), "g": (64, 150, 84), "j": (172, 228, 112),
    "P": (255, 132, 176), "p": (226, 88, 140), "V": (182, 146, 244), "W": (255, 255, 255),
    "O": (255, 168, 64), "S": (214, 208, 222), "s": (164, 158, 182),
    # 關起來的玻璃窗、門
    "U": (186, 228, 255), "u": (132, 190, 240), "v": (98, 156, 222), "X": (232, 248, 255),
    "Z": (246, 136, 160), "z": (214, 98, 132), "N": (255, 232, 214),
}
DOOR_PAW = [
    "..XX..XX..",
    "..XX..XX..",
    "XX......XX",
    "XX..XX..XX",
    "...XXXX...",
    "..XXXXXX..",
    "..XXXXXX..",
    "...XXXX...",
]
HOUSE_W, HOUSE_H = 56, 56
HOUSE_GROUND = 52
# 開口（給貓咪探頭）：(x, y, w, h) 內部範圍
HOUSE_SLOTS = {"door": (22, 38, 12, 14), "left": (11, 31, 9, 7), "right": (36, 31, 9, 7),
               "attic": (23, 12, 10, 6)}

BUSH = [  # 花叢 18x9：. 透明，其餘是 HOUSE_COLORS
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


def house():
    img = Image.new("RGBA", (HOUSE_W, HOUSE_H), (0, 0, 0, 0))

    def px(x, y, c):
        if 0 <= x < HOUSE_W and 0 <= y < HOUSE_H:
            img.putpixel((x, y), HOUSE_COLORS[c] + (255,))

    def rect(x0, y0, w, h, c):
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                px(x, y, c)

    # 煙囪：先畫到屋頂下面，等一下屋頂蓋上去，就會像從屋頂長出來
    cx, cy, cw = 38, 4, 7
    rect(cx, cy, cw, 22, "K")
    rect(cx + 1, cy + 2, cw - 2, 20, "B")
    for y in range(cy + 3, cy + 22, 3):            # 磚縫
        rect(cx + 1, y, cw - 2, 1, "m")
        off = 2 if (y // 3) % 2 else 4
        px(cx + off, y + 1, "m")
    rect(cx + 1, cy + 2, 1, 20, "b")
    rect(cx - 1, cy - 1, cw + 2, 3, "K")           # 煙囪帽
    rect(cx, cy, cw, 1, "c")

    # 牆（木板）
    wx0, wx1, wy0 = 6, 49, 25
    rect(wx0, wy0, wx1 - wx0 + 1, HOUSE_GROUND - wy0, "K")
    rect(wx0 + 1, wy0, wx1 - wx0 - 1, HOUSE_GROUND - wy0, "T")
    for y in range(wy0 + 3, HOUSE_GROUND, 4):
        rect(wx0 + 1, y, wx1 - wx0 - 1, 1, "t")
        for x in range(wx0 + 3 + (y % 8), wx1 - 1, 9):     # 木板接縫
            px(x, y - 1, "t")
    rect(wx0 + 1, wy0 + 1, wx1 - wx0 - 1, 1, "l")

    # 屋頂（三角形 + 屋簷 + 魚鱗瓦）
    top, bottom = 3, 25
    for y in range(top, bottom + 1):
        half = int((y - top) * 26 / (bottom - top)) + 1
        x0, x1 = 28 - half, 27 + half
        for x in range(x0, x1 + 1):
            row = y - top
            if x in (x0, x1) or y == bottom or (x in (x0 + 1, x1 - 1) and row > 1 and False):
                px(x, y, "K")
            elif y == bottom - 1:
                px(x, y, "e")
            elif row % 4 == 3:
                px(x, y, "r" if (x + row) % 4 else "e")
            elif row % 4 == 0 and (x + row // 4 * 2) % 4 == 0:
                px(x, y, "r")
            elif x - x0 < 3 and x < 28:
                px(x, y, "h")
            elif row % 4 == 1 and (x + row // 4 * 2) % 4 == 2:
                px(x, y, "h")
            else:
                px(x, y, "R")
    px(27, top - 1, "K"); px(28, top - 1, "K")
    px(27, top, "h"); px(28, top, "R")

    # 閣樓圓窗（圓角）
    ax, ay, aw, ah = HOUSE_SLOTS["attic"]
    rect(ax - 2, ay - 2, aw + 4, ah + 4, "K")
    rect(ax - 1, ay - 1, aw + 2, ah + 2, "C")
    rect(ax, ay, aw, ah, "H")
    for x, y in ((ax - 2, ay - 2), (ax + aw + 1, ay - 2), (ax - 2, ay + ah + 1), (ax + aw + 1, ay + ah + 1)):
        px(x, y, "R")
    for x, y in ((ax - 1, ay - 1), (ax + aw, ay - 1), (ax - 1, ay + ah), (ax + aw, ay + ah)):
        px(x, y, "K")

    # 左右窗 + 百葉窗 + 窗台
    for key in ("left", "right"):
        x, y, w, h = HOUSE_SLOTS[key]
        rect(x - 2, y - 2, w + 4, h + 4, "K")
        rect(x - 1, y - 1, w + 2, h + 2, "C")
        rect(x, y, w, h, "H")
        rect(x + w // 2, y, 1, h, "C") if False else None
        for sx in (x - 5, x + w + 2):                 # 百葉窗
            rect(sx, y - 1, 3, h + 2, "K")
            rect(sx + 1, y, 1, h, "Q")
            for yy in range(y + 1, y + h, 2):
                px(sx + 1, yy, "q")
        rect(x - 3, y + h + 1, w + 6, 2, "K")         # 窗台
        rect(x - 2, y + h + 1, w + 4, 1, "l")

    # 門（拱形，薄荷綠門框）
    dx, dy, dw, dh = HOUSE_SLOTS["door"]
    rect(dx - 3, dy - 1, dw + 6, dh + 1, "K")
    rect(dx - 2, dy, dw + 4, dh, "Q")
    rect(dx - 2, dy, 1, dh, "q")
    rect(dx, dy, dw, dh, "H")
    rect(dx - 2, dy - 2, dw + 4, 1, "K")
    rect(dx - 1, dy - 1, dw + 2, 1, "Q")
    rect(dx, dy - 3, dw, 1, "K")
    rect(dx, dy - 2, dw, 1, "Q")
    for x in (dx - 3, dx + dw + 2):
        px(x, dy - 1, "T")
    px(dx - 2, dy - 1, "K"); px(dx + dw + 1, dy - 1, "K")
    px(dx - 1, dy - 2, "K"); px(dx + dw, dy - 2, "K")
    # 門上的黃色貓掌門牌
    sx, sy = dx + dw // 2 - 3, dy - 11
    rect(sx, sy, 6, 5, "K")
    rect(sx + 1, sy + 1, 4, 3, "Y")
    rect(sx + 1, sy + 3, 4, 1, "y")
    px(sx + 2, sy + 2, "p"); px(sx + 3, sy + 2, "p"); px(sx + 1, sy + 1, "p"); px(sx + 4, sy + 1, "p")
    # 門墊
    rect(dx - 1, HOUSE_GROUND - 1, dw + 2, 1, "M")
    for x in range(dx, dx + dw + 1, 2):
        px(x, HOUSE_GROUND - 1, "n")

    # 地面草皮 + 石板路
    rect(0, HOUSE_GROUND, HOUSE_W, 4, "K")
    rect(1, HOUSE_GROUND, HOUSE_W - 2, 3, "G")
    rect(1, HOUSE_GROUND + 2, HOUSE_W - 2, 1, "g")
    for x in range(2, HOUSE_W - 2, 3):
        px(x, HOUSE_GROUND, "j")
    for i, x in enumerate(range(dx - 1, dx + dw + 2, 4)):
        rect(x, HOUSE_GROUND + 1, 3, 1, "S")
        px(x + 2, HOUSE_GROUND + 1, "s")
    for x, c in ((3, "P"), (13, "Y"), (44, "V"), (52, "W")):
        px(x, HOUSE_GROUND, c)

    # 門口兩側的花叢（一直都在）
    def bush(ox, oy, flip=False):
        for y, row in enumerate(BUSH):
            row = row[::-1] if flip else row
            for x, ch in enumerate(row):
                if ch != ".":
                    px(ox + x, oy + y, ch)
    bush(2, HOUSE_GROUND - 8)
    bush(HOUSE_W - 2 - len(BUSH[0]), HOUSE_GROUND - 8, flip=True)

    # 第二格：沒有貓咪在家時，門窗都關起來
    closed = img.copy()
    open_img = img
    img = closed

    def glass(x, y, w, h, cross=True):
        for yy in range(h):
            t = yy / max(1, h - 1)
            c = "U" if t < 0.45 else ("u" if t < 0.85 else "v")
            rect(x, y + yy, w, 1, c)
        for k in range(-h, w):                     # 兩道斜斜的反光
            for yy in range(h):
                xx = k + (h - 1 - yy)
                if 0 <= xx < w and k in (1, 2, 5):
                    px(x + xx, y + yy, "X" if k != 5 else "U")
        if cross:                                  # 窗格
            rect(x + w // 2, y, 1, h, "C")
            rect(x, y + h // 2, w, 1, "C")
    for key in ("left", "right"):
        glass(*HOUSE_SLOTS[key])
    ax, ay, aw, ah = HOUSE_SLOTS["attic"]
    glass(ax, ay, aw, ah, cross=False)
    rect(ax + aw // 2, ay, 1, ah, "C")
    # 門：粉紅色木門 + 奶油色肉球 + 金色門把
    dx, dy, dw, dh = HOUSE_SLOTS["door"]
    rect(dx, dy, dw, dh, "Z")
    for x in range(dx + 2, dx + dw, 3):
        rect(x, dy + 1, 1, dh - 1, "z")
    rect(dx, dy, dw, 1, "z")
    for y, row in enumerate(DOOR_PAW):
        for x, ch in enumerate(row):
            if ch != ".":
                px(dx + 1 + x, dy + 2 + y, "N")
    rect(dx + dw - 3, dy + 9, 2, 2, "K")
    px(dx + dw - 3, dy + 9, "Y")
    rect(dx - 1, HOUSE_GROUND - 1, dw + 2, 1, "M")   # 門墊（被門蓋住的部分補回來）
    for x in range(dx, dx + dw + 1, 2):
        px(x, HOUSE_GROUND - 1, "n")

    sheet = Image.new("RGBA", (HOUSE_W * 2, HOUSE_H), (0, 0, 0, 0))
    sheet.paste(open_img, (0, 0))
    sheet.paste(closed, (HOUSE_W, 0))
    sheet.save(os.path.join(SPRITES, "house.png"))


# ---------------- App 圖示：四隻貓把臉貼在窗戶上 ---------------- #
def recolor(lines, spec):
    out = []
    for line in lines:
        row = []
        for ch in line:
            if ch == ".":
                row.append(None)
            elif ch == "W":
                row.append((255, 255, 255))
            else:
                row.append(spec[ch])
        out.append(row)
    return out


PRESSED_FACE = [
    ".OO..............OO.",
    "OMMO............OMMO",
    "OMPMO..........OMPMO",
    "OMPPMOOOOOOOOOOMPPMO",
    "OMMMMMMMMMMMMMMMMMMO",
    "OMMMLLLLLLLLLLLLMMMO",
    "OMLLLOOLLLLLLOOLLLMO",
    "OMLLOWEOLLLLOWEOLLMO",
    "OMLLOEEOLLLLOEEOLLMO",
    "OMRRLOOLLLLLLOOLRRMO",
    "OMRRLLLLPPPPLLLLRRMO",
    "OLLLLLLLPWWPLLLLLLLO",
    "OLLLLLLOLOOLOLLLLLLO",
    "ODLLLLLLOLLOLLLLLLDO",
    ".ODMLLLLLLLLLLLLMDO.",
    "..OOOOOOOOOOOOOOOO..",
]
PRESSED_PAW = [
    ".OO..OO.",
    "OPPOOPPO",
    "OLOPPOLO",
    "OLPPPPLO",
    "OLLPPLLO",
    ".OOOOOO.",
]


def _derive(fur, eye):
    """和 src/sprites.derive_spec 同一套：從毛色推出整組調色盤。"""
    import colorsys

    def shift(rgb, dl=0.0, ds=0.0, dh=0.0):
        h, l, s_ = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
        r, g, b = colorsys.hls_to_rgb((h + dh) % 1, max(0, min(1, l + dl)), max(0, min(1, s_ + ds)))
        return int(r * 255), int(g * 255), int(b * 255)
    lum = colorsys.rgb_to_hls(*(c / 255 for c in fur))[1]
    return dict(O=INK, R=(236, 112, 132) if lum > 0.35 else (177, 78, 69), D=shift(fur, -0.13, 0, -0.01),
                P=(240, 138, 158), M=fur, L=shift(fur, 0.10, 0.02), E=eye, F=eye)


ICON_CATS = [  # 繽紛的四隻貓：草莓粉、薄荷綠、薰衣草紫、蜂蜜橘
    ((250, 160, 196), (64, 120, 210)),
    ((132, 214, 186), INK),
    ((178, 150, 240), (210, 150, 30)),
    ((255, 186, 92), (40, 140, 70)),
]
ICON_HEART = [".KK.KK.", "KPPKhPK", "KPPPPPK", ".KPPPK.", "..KPK..", "...K..."]
ICON_STAR = ["..K..", ".KYK.", "KYWYK", ".KYK.", "..K.."]


def app_icon():
    N, U = 64, 16                       # 64 格 × 16px = 1024
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 背景：糖果色斜向漸層（粉紅 → 蜜桃 → 奶油黃）
    bg = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bg)
    stops = [(255, 150, 190), (255, 186, 160), (255, 226, 150)]
    for y in range(N):
        for x in range(N):
            t = (x * 0.45 + y * 0.55) / N
            if t < 0.5:
                c0, c1, k = stops[0], stops[1], t / 0.5
            else:
                c0, c1, k = stops[1], stops[2], (t - 0.5) / 0.5
            bd.point((x, y), fill=tuple(int(a + (b_ - a) * k) for a, b_ in zip(c0, c1)) + (255,))
    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).rounded_rectangle([6, 6, N - 7, N - 7], 11, fill=255)
    d.rounded_rectangle([5, 5, N - 6, N - 6], 12, fill=INK + (255,))
    img.paste(bg, (0, 0), mask)
    # 背景上的小圓點
    for x, y in ((10, 9), (52, 10), (9, 50), (54, 53), (31, 7), (7, 30)):
        d.point((x, y), fill=(255, 255, 255, 200))
    # 窗框（薄荷綠，有亮邊）
    fx0, fy0, fx1, fy1 = 10, 10, N - 11, N - 11
    d.rounded_rectangle([fx0, fy0, fx1, fy1], 7, fill=INK + (255,))
    d.rounded_rectangle([fx0 + 1, fy0 + 1, fx1 - 1, fy1 - 1], 6, fill=(112, 210, 196, 255))
    d.rounded_rectangle([fx0 + 1, fy0 + 1, fx1 - 1, fy1 - 2], 6, fill=(150, 232, 214, 255))
    d.rounded_rectangle([fx0 + 2, fy0 + 3, fx1 - 2, fy1 - 2], 5, fill=(112, 210, 196, 255))
    # 玻璃（天空漸層）
    gx0, gy0, gx1, gy1 = 14, 14, N - 15, N - 15
    d.rectangle([gx0 - 1, gy0 - 1, gx1 + 1, gy1 + 1], fill=INK + (255,))
    for y in range(gy0, gy1 + 1):
        t = (y - gy0) / (gy1 - gy0)
        c = tuple(int(a + (b_ - a) * t) for a, b_ in zip((156, 212, 255), (232, 246, 255)))
        d.line([(gx0, y), (gx1, y)], fill=c + (255,))

    def stamp(lines, spec, ox, oy, clip=True):
        for y, row in enumerate(recolor(lines, spec)):
            for x, rgb in enumerate(row):
                X, Y = ox + x, oy + y
                if rgb and (not clip or (gx0 <= X <= gx1 and gy0 <= Y <= gy1)):
                    img.putpixel((X, Y), rgb + (255,))

    specs = [_derive(f, e) for f, e in ICON_CATS]
    # 四隻貓擠在窗戶上（臉頰互相擠在一起）
    spots = [(gx0 - 2, gy0 + 0), (gx0 + 17, gy0 - 1), (gx0 - 2, gy0 + 16), (gx0 + 17, gy0 + 17)]
    for sp, (ox, oy) in zip(specs, spots):
        stamp(PRESSED_FACE, sp, ox, oy)
    for sp, (ox, oy) in zip(specs[2:], spots[2:]):   # 前排兩隻的肉球貼在玻璃上
        stamp(PRESSED_PAW, sp, ox + 1, oy + 14)
        stamp(PRESSED_PAW, sp, ox + 11, oy + 14)
    # 鼻子呼出的霧氣 + 玻璃反光
    fog = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fog)
    for ox, oy in spots:
        fd.ellipse([ox + 6, oy + 9, ox + 13, oy + 13], fill=(255, 255, 255, 80))
    for k in range(6):
        fd.point((gx1 - 2 - k, gy0 + 1 + k), fill=(255, 255, 255, 190))
        fd.point((gx1 - 1 - k, gy0 + 1 + k), fill=(255, 255, 255, 120))
    img = Image.alpha_composite(img, fog)
    # 窗框上的小愛心和星星
    pal = {"K": INK, "P": (255, 104, 150), "h": (255, 200, 220), "Y": (255, 214, 70), "W": (255, 255, 255)}

    def deco(lines, ox, oy):
        for y, row in enumerate(lines):
            for x, ch in enumerate(row):
                if ch != ".":
                    img.putpixel((ox + x, oy + y), pal[ch] + (255,))
    deco(ICON_HEART, fx1 - 8, fy1 - 6)
    deco(ICON_STAR, fx0 - 2, fy0 - 2)
    deco(ICON_STAR, fx1 - 3, fy0 + 3)
    img.resize((N * U, N * U), Image.NEAREST).save(os.path.join(ASSETS, "icon.png"))


def tray_icon():
    """選單列用的單色貓臉（macOS 會依深淺色模式自動上色）。"""
    sil = [
        "OO........OO",
        "OOO......OOO",
        "OOOOOOOOOOOO",
        "OOOOOOOOOOOO",
        "OO..OOOO..OO",
        "OO..OOOO..OO",
        "OOOOO..OOOOO",
        "OOOOOOOOOOOO",
        ".OOOOOOOOOO.",
        "..OOOOOOOO..",
    ]
    img = Image.new("RGBA", (18, 18), (0, 0, 0, 0))
    for y, row in enumerate(sil):
        for x, ch in enumerate(row):
            if ch == "O":
                img.putpixel((3 + x, 4 + y), (0, 0, 0, 255))
    img.resize((36, 36), Image.NEAREST).save(os.path.join(ASSETS, "tray.png"))


def main():
    base_walk()
    save_semantic([sleep_frame(0), sleep_frame(1)], os.path.join(SPRITES, "base_sleep.png"))
    save_semantic([expression(k) for k in EXPRESSIONS], os.path.join(SPRITES, "base_expr.png"))
    face_sheet()
    effects_sheet()
    house()
    app_icon()
    tray_icon()
    print("done")


if __name__ == "__main__":
    main()
