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
    "K": INK, "R": (196, 82, 68), "r": (150, 55, 48), "h": (226, 124, 100),
    "T": (182, 130, 88), "t": (146, 100, 66), "l": (210, 166, 116), "C": (250, 241, 218),
    "H": (54, 40, 42), "S": (150, 150, 160), "s": (110, 110, 122), "G": (120, 178, 72),
    "g": (86, 140, 60), "Y": (250, 214, 90),
}
HOUSE_W, HOUSE_H = 48, 46
# 開口（給貓咪探頭）：(x, y, w, h) 內部範圍
HOUSE_SLOTS = {"door": (18, 31, 12, 13), "left": (5, 25, 10, 7), "right": (33, 25, 10, 7),
               "attic": (19, 9, 10, 6)}


def house():
    img = Image.new("RGBA", (HOUSE_W, HOUSE_H), (0, 0, 0, 0))
    px = lambda x, y, c: img.putpixel((x, y), HOUSE_COLORS[c] + (255,))  # noqa: E731

    def rect(x0, y0, w, h, c):
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                px(x, y, c)

    # 煙囪
    rect(34, 2, 6, 10, "K")
    rect(35, 3, 4, 9, "S")
    rect(35, 3, 1, 9, "s")
    rect(33, 1, 8, 2, "K")
    rect(34, 1, 6, 1, "s")
    # 牆（木板）
    rect(2, 20, 44, 24, "K")
    rect(3, 21, 42, 22, "T")
    for y in range(24, 43, 4):
        rect(3, y, 42, 1, "t")
    rect(3, 21, 42, 1, "l")
    # 屋頂（三角形 + 屋簷）
    top, bottom = 2, 21
    for y in range(top, bottom + 1):
        half = int((y - top) * 25 / (bottom - top)) + 1
        x0, x1 = 24 - half, 23 + half
        for x in range(max(0, x0), min(HOUSE_W, x1 + 1)):
            edge = x in (x0, x1) or y == bottom
            if edge:
                px(x, y, "K")
            elif (y - top) % 4 == 3:
                px(x, y, "r")
            elif x < 24 and x - x0 < 2:
                px(x, y, "h")
            else:
                px(x, y, "R")
    # 屋頂閣樓圓窗
    ax, ay, aw, ah = HOUSE_SLOTS["attic"]
    rect(ax - 2, ay - 1, aw + 4, ah + 2, "K")
    rect(ax - 1, ay, aw + 2, ah, "C")
    rect(ax, ay, aw, ah, "H")
    for x in (ax - 2, ax + aw + 1):
        px(x, ay - 1, "R")
    # 左右窗
    for key in ("left", "right"):
        x, y, w, h = HOUSE_SLOTS[key]
        rect(x - 2, y - 2, w + 4, h + 4, "K")
        rect(x - 1, y - 1, w + 2, h + 2, "C")
        rect(x, y, w, h, "H")
        rect(x - 2, y + h + 1, w + 4, 2, "K")       # 窗台
        rect(x - 1, y + h + 1, w + 2, 1, "l")
    # 門（拱形）
    dx, dy, dw, dh = HOUSE_SLOTS["door"]
    rect(dx - 2, dy - 1, dw + 4, dh + 1, "K")
    rect(dx - 1, dy, dw + 2, dh, "C")
    rect(dx, dy, dw, dh, "H")
    for x in (dx - 2, dx - 1, dx + dw, dx + dw + 1):
        px(x, dy - 1, "T" if x in (dx - 2, dx + dw + 1) else "K")
    rect(dx, dy - 2, dw, 1, "K")
    rect(dx + 1, dy - 1, dw - 2, 1, "C")
    # 地面草皮
    rect(0, 43, HOUSE_W, 3, "K")
    rect(1, 43, HOUSE_W - 2, 2, "G")
    for x in range(2, HOUSE_W - 2, 3):
        px(x, 43, "g")
    img.save(os.path.join(SPRITES, "house.png"))


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


def app_icon():
    N, U = 64, 16                       # 64 格 × 16px = 1024
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([5, 5, N - 6, N - 6], 11, fill=INK + (255,))
    d.rounded_rectangle([6, 6, N - 7, N - 7], 10, fill=(176, 124, 82, 255))     # 木框
    d.rounded_rectangle([8, 8, N - 9, N - 9], 8, fill=(196, 146, 100, 255))
    # 玻璃（天空漸層）
    gx0, gy0, gx1, gy1 = 12, 12, N - 13, N - 13
    d.rectangle([gx0 - 1, gy0 - 1, gx1 + 1, gy1 + 1], fill=INK + (255,))
    for y in range(gy0, gy1 + 1):
        t = (y - gy0) / (gy1 - gy0)
        c = tuple(int(a + (b - a) * t) for a, b in zip((150, 198, 240), (222, 238, 252)))
        d.line([(gx0, y), (gx1, y)], fill=c + (255,))

    def stamp(lines, spec, ox, oy):
        for y, row in enumerate(recolor(lines, spec)):
            for x, rgb in enumerate(row):
                if rgb and gx0 <= ox + x <= gx1 and gy0 <= oy + y <= gy1:
                    img.putpixel((ox + x, oy + y), rgb + (255,))

    # 四隻貓擠在窗戶上（後排兩隻、前排兩隻，臉頰互相擠在一起）
    spots = [("black", gx0 - 1, gy0 + 2), ("white", gx0 + 21, gy0 + 1),
             ("orange", gx0 - 1, gy0 + 21), ("brown", gx0 + 21, gy0 + 22)]
    for color, ox, oy in spots:
        stamp(PRESSED_FACE, BUILTIN[color], ox, oy)
    for color, ox, oy in spots:          # 肉球最後畫，貼在最前面
        stamp(PRESSED_PAW, BUILTIN[color], ox + 1, oy + 14)
        stamp(PRESSED_PAW, BUILTIN[color], ox + 11, oy + 14)
    # 鼻子呼出的霧氣 + 玻璃反光
    fog = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fog)
    for _, ox, oy in spots:
        fd.ellipse([ox + 6, oy + 9, ox + 13, oy + 13], fill=(255, 255, 255, 70))
    for k in range(7):                   # 右上角一小段玻璃反光
        fd.point((gx1 - 2 - k, gy0 + 1 + k), fill=(255, 255, 255, 170))
        fd.point((gx1 - 1 - k, gy0 + 1 + k), fill=(255, 255, 255, 110))
    for k in range(4):
        fd.point((gx1 - 1 - k, gy0 + 5 + k), fill=(255, 255, 255, 130))
    img = Image.alpha_composite(img, fog)
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
