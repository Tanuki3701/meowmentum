"""新增的像素圖：飾品、禮物、玩具、家具、節慶裝飾、商店圖示。

全部用格子字串畫（和 pixel.ICONS 同一套寫法），執行時才轉成圖並快取，
不需要額外的圖檔。顏色字元見 COLORS。
"""
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap, QTransform

import pixel

COLORS = dict(pixel.PALETTE)
COLORS.update({
    "V": (156, 104, 214), "v": (112, 72, 168), "N": (44, 52, 96), "n": (70, 82, 140),
    "Q": (98, 200, 190), "q": (56, 150, 152), "A": (214, 168, 112), "a": (170, 124, 78),
    "E": (238, 204, 152), "H": (255, 200, 214), "U": (186, 228, 255), "u": (132, 190, 240),
    "X": (255, 226, 140), "x": (255, 180, 90), "F": (170, 220, 110), "Z": (232, 92, 140),
    "D": (96, 70, 52), "I": (250, 250, 250), "J": (120, 200, 240), "j": (70, 150, 210),
})

_cache = {}


# ---------------- 飾品 ---------------- #
# 帽子：以「兩耳中間」為底部中心；dx 是往臉的方向偏移（側面時）
HATS = {
    "party": ["...KWK...", "....K....", "...KYK...", "...KRK...", "..KRYRK..",
              "..KYRYK..", ".KRYRYRK.", "KKKKKKKKK"],
    "crown": ["K...K...K", "KK.KYK.KK", "KYKYYYKYK", "KYYYRYYYK", "KKKKKKKKK"],
    "flower": [".K.K.", "KPKPK", ".KYK.", "KPKPK", ".K.K."],
    "beanie": ["...KWK...", "..KKBKK..", ".KBBBBBK.", "KBBBBBBBK", "KWBWBWBWK", "KKKKKKKKK"],
    "witch": ["......KK...", ".....KVK...", "....KVVK...", "....KVVK...", "...KVVVVK..",
              "...KOOOOK..", "KKKKKKKKKKK"],
    "santa": [".......KWK", ".....KKRK.", "...KKRRRK.", "..KRRRRRK.", ".KRRRRRRK.",
              "KWWWWWWWWK", "KKKKKKKKKK"],
    "star": ["...K...", "..KYK..", "KKYXYKK", ".KYYYK.", "..KYK..", ".KYKYK.", ".KK.KK."],
    "halo": [".KKKKK.", "KXYYYXK", ".KKKKK."],
}
HAT_SINK = {"party": 1, "crown": 1, "flower": -1, "beanie": 2, "witch": 1, "santa": 2, "star": -1, "halo": -3}
HAT_DX = {"flower": 3}

# 脖子：front（正面／背面）和 side（側面，面向右）兩種
NECKS = {
    "collar": {"front": ["KRRRRRRRK", "KKKKYKKKK", "...KYK...", "....K...."],
               "side": ["KR....", "KRR...", ".KRR..", "..KRRK", "...KYK", "....K."]},
    "scarf": {"front": ["KQQQQQQQK", "KqQQQQQqK", ".KKQQKKK.", "...KQK...", "...KqK...", "....K...."],
              "side": ["KQ.....", "KQQ....", "KQQQ...", ".KQQQK.", "..KQQK.", "..KQK..", "..KqK..", "...K..."]},
    "bowtie": {"front": ["KK...KK", "KPKKKPK", "KPPYPPK", "KPKKKPK", "KK...KK"],
               "side": [".KK", "KPK", "KYK", "KPK", ".KK"]},
    "medal": {"front": ["KBK.KRK", ".KBKRK.", "..KBK..", ".KYYYK.", ".KYXYK.", ".KYYYK.", "..KKK.."],
              "side": ["KB....", ".KB...", "..KBK.", "..KYYK", "..KYXK", "...KK."]},
    "bandana": {"front": ["KRRRRRRRK", ".KRWRWRK.", "..KRRRK..", "...KRK...", "....K...."],
                "side": ["KR....", "KRR...", ".KRWR.", "..KRRK", "...KK."]},
}

# ---------------- 禮物、玩具 ---------------- #
GIFTS = {
    "fishbone": [".K..K..K...KK.", "KWKKWKKWKKKWWK", ".KWWWWWWWWWWKK", "KWKKWKKWKKKWWK",
                 ".K..K..K...KK."],
    "leaf": ["....KKK.", "..KKGGFK", ".KGGgFGK", "KGgGFGK.", "KgFGGK..", "KKKK...."],
    "feather": ["......KK.", "...KKKBUK", ".KKBUBUK.", "KBUBUKK..", "K.KK....."],
    "flower": [".KK.KK.", "KPPKPPK", "KPHYHPK", ".KYYYK.", "KPHYHPK", "KPPKPPK", ".KK.KK.",
               "...K...", "..KGK..", "...K..."],
    "mouse": ["..KK.....", ".KSSK....", "KSSSSKKK.", "KSKSSSSSK", ".KKKKKKKK", "........K"],
}

WAND = [
    ["K.........", ".K........", "..K.......", "...K......", "....K.....", ".....K....",
     "......K...", "......K...", "......K...", ".....KVK..", "....KVHVK.", "....KVHVK.",
     ".....KVK..", "......K...", "......K..."],
    ["K.........", ".K........", "..K.......", "...K......", "....K.....", ".....K....",
     "......K...", ".......K..", ".......K..", "......KVK.", ".....KVHVK", ".....KVHVK",
     "......KVK.", ".......K..", "......K..."],
]
YARN = [
    ["..KKKK..", ".KPPHPK.", "KPHPPHPK", "KPPHPPPK", "KHPPPHPK", "KPPHPPPK", ".KPPPHK.",
     "..KKKKKK"],
    ["..KKKK..", ".KPHPPK.", "KPPHPPHK", "KHPPPHPK", "KPPHPPPK", "KPHPPPHK", ".KPHPPK.",
     "KKKKKK.."],
]

DOOR_PAW = ["..I..I...", ".III.III.", "..I..I...", "I.......I", "II.III.II", "..IIIII..",
            ".IIIIIII.", "..IIIII.."]

# ---------------- 節慶 ---------------- #
PUMPKIN = ["...gK...", "..KKgKK.", ".KOxOxOK", "KOxKOxKK", "KOxOxOxK", "KOKKKKOK",
           ".KOxOxK.", "..KKKK.."]
WREATH = ["..KKK..", ".KGRGK.", "KGK.KGK", "KR...RK", "KGK.KGK", ".KGRGK.", "..KRK..",
          "..R.R.."]
LANTERN = ["..K..", ".KYK.", "KRRRK", "KRYRK", "KRRRK", ".KYK.", "..Y..", "..Y.."]
COUPLET = ["KK", "KR", "RY", "RR", "RY", "RR", "RY", "RR", "RY", "KK"]

# ---------------- 商店、選單小圖示（12x12）---------------- #
ICONS = {
    "fish": ["............", "............", "........K...", "..KKKK.KBK..", ".KBBBBKBBK..",
             "KBWKBBBBBK..", "KBBBBBBBBK..", ".KBBBBKBBK..", "..KKKK.KBK..", "........K...",
             "............", "............"],
    "shop": ["............", "..KKKKKKKK..", ".KRWRWRWRWK.", "KRWRWRWRWRWK", "KKKKKKKKKKKK",
             ".KCCCCCCCCK.", ".KCKKKCCCCK.", ".KCKBKCCCCK.", ".KCKBKCKKCK.", ".KCKBKCKKCK.",
             ".KKKKKKKKKK.", "............"],
    "chart": ["............", "..........K.", ".........KGK", "..K......KGK", ".KGK..K..KGK",
              ".KGK.KGK.KGK", ".KGK.KGK.KGK", ".KGK.KGK.KGK", ".KGK.KGK.KGK", ".KGK.KGK.KGK",
              "KKKKKKKKKKKK", "............"],
    "eye": ["............", "............", "...KKKKKK...", "..KWWWWWWK..", ".KWWKKKKWWK.",
            "KWWKBBWBKWWK", "KWWKBBBBKWWK", ".KWWKKKKWWK.", "..KWWWWWWK..", "...KKKKKK...",
            "............", "............"],
    "toy": ["K...........", ".K..........", "..K.........", "...K........",
            "....K.......", ".....K......", "......K.....", ".....KVK....",
            "....KVHVK...", "....KVHVK...", ".....KVK....", "............"],
    "box": ["............", "............", "KK........KK", "KEKKKKKKKKEK", ".KEAaaaaaAK.",
            ".KAAAAAAAAK.", ".KAAAEAAAAK.", ".KAAAEAAAAK.", ".KAAAAAAAAK.", ".KaaaaaaaaK.",
            ".KKKKKKKKKK.", "............"],
    "tree": ["...KKKKKK...", "..KPPPPPPK..", "..KKKKKKKK..", ".....KAK....", ".....KaK....",
             ".KKKKKAKKK..", ".KTTTTTTTK..", ".KKKKAKKKK..", ".....KaK....", ".....KAK....",
             "..KKKKKKKK..", "..KTTTTTTK.."],
    "hide": ["............", "...KKKKKK...", "..KWWWWWWK..", ".KWKKWWKKWK.", "KWWWWWWWWWWK",
             "KWWWWKKWWWWK", "KWWWWWWWWWWK", ".KWKWKWKWK..", "..K.K.K.K...", "............",
             "............", "............"],
    "crown": ["............", "............", "K....K....K.", "KK..KYK..KK.", "KYK.KYK.KYK.",
              "KYYKYYYKYYK.", "KYYYYRYYYYK.", "KYYYYYYYYYK.", "KKKKKKKKKKK.", "............",
              "............", "............"],
    "update": ["............", ".....KK.....", "....KGGK....", "...KGGGGK...", "..KGGGGGGK..",
               ".KKKKGGKKKK.", "....KGGK....", "....KGGK....", "....KGGK....", "....KKKK....",
               "............", "............"],
    "name": ["............", "............", "KKKKKKKKKK..", "KYYYYYYYYKK.", "KYKKKKYYYYKK",
             "KYYYYYYYKYYK", "KYKKKKKYYYYK", "KYYYYYYYYYKK", "KKKKKKKKKKK.", "............",
             "............", "............"],
    "up": ["............", ".....KK.....", "....KGGK....", "...KGGGGK...", "..KGGGGGGK..",
           ".KKKKGGKKKK.", "....KGGK....", "....KGGK....", "....KGGK....", "....KKKK....",
           "............", "............"],
    "down": ["............", "............", "....KKKK....", "....KBBK....", "....KBBK....",
             "....KBBK....", ".KKKKBBKKKK.", "..KBBBBBBK..", "...KBBBBK...", "....KBBK....",
             ".....KK.....", "............"],
    "sofa": ["............", "............", "..KKKKKKKK..", ".KPPPPPPPPK.", ".KPHPPPPHPK.",
             "KKKKKKKKKKKK", "KPKPPPPPPKPK", "KPKHHHHHHKPK", "KPPPPPPPPPPK", "KKKKKKKKKKKK",
             ".KK......KK.", "............"],
    "shirt": ["............", "..KKK..KKK..", ".KVVKKKKVVK.", "KVVVVWWVVVVK", "KVKVVVVVVKVK",
              "KKKVVVVVVKKK", "..KVVVVVVK..", "..KVHVVHVK..", "..KVVVVVVK..", "..KKKKKKKK..",
              "............", "............"],
    "cloud": ["............", "............", "....KKK.....", "...KWWWKK...", ".KKWWWWWWK..",
              "KWWWWWWWWWK.", "KWWWWWWWWWWK", ".KKKKKKKKKK.", "..u..u..u...", ".u..u..u....",
              "............", "............"],
    "badge": ["............", "..KKK..KKK..", "..KRK..KBK..", "...KRKKBK...", "....KKKK....",
              "...KYYYYK...", "..KYXYYXYK..", "..KYYXXYYK..", "..KYXYYXYK..", "...KYYYYK...",
              "....KKKK....", "............"],
    "diary": ["............", ".KKKKKKKKK..", ".KHKWWWWWWK.", ".KHKWKKKKWK.", ".KHKWWWWWWK.",
              ".KHKWKKKWWK.", ".KHKWWWWWWK.", ".KHKWKKKKWK.", ".KHKWWWWWWK.", ".KKKKKKKKKK.",
              "............", "............"],
    "sound": ["............", ".....K......", "....KK...K..", "KKKKWK.K..K.", "KWWWWK..K.K.",
              "KWWWWK..K.K.", "KWWWWK..K.K.", "KKKKWK.K..K.", "....KK...K..", ".....K......",
              "............", "............"],
    "heart": ["............", "............", ".KKK...KKK..", "KRRRK.KRRRK.", "KRWRRKRRRRK.",
              "KRRRRRRRRRK.", ".KRRRRRRRK..", "..KRRRRRK...", "...KRRRK....", "....KRK.....",
              ".....K......", "............"],
    "calendar": ["............", "..K.....K...", ".KKKKKKKKKK.", ".KRRRRRRRRK.", ".KKKKKKKKKK.",
                 ".KWWWWWWWWK.", ".KWKWKWKWWK.", ".KWWWWWWWWK.", ".KWKWKWRWWK.", ".KWWWWWWWWK.",
                 ".KKKKKKKKKK.", "............"],
}


def pix(grid, unit, flip=False):
    """格子字串 → QPixmap（Retina 清晰）。"""
    key = ("grid", tuple(grid), unit, flip)
    if key not in _cache:
        pm = pixel._grid_pixmap(grid, unit, COLORS)
        if flip:
            pm = pm.transformed(QTransform().scale(-1, 1))
            pm.setDevicePixelRatio(pixel._dpr())
        _cache[key] = pm
    return _cache[key]


def icon_pm(name, unit=1.5):
    return pix(ICONS[name], unit)


def size_of(grid):
    return max(len(r) for r in grid), len(grid)


# ---------------- 用矩形畫的大型圖（家具、房間）---------------- #
class Canvas:
    """以「格」為單位畫圖，最後輸出成 QPixmap。"""

    def __init__(self, w, h, unit, bg=None):
        self.w, self.h, self.u = w, h, unit
        self.dpr = pixel._dpr()
        self.img = QImage(int(w * unit * self.dpr), int(h * unit * self.dpr),
                          QImage.Format_ARGB32_Premultiplied)
        self.img.fill(QColor(*bg) if bg else Qt.transparent)
        self.p = QPainter(self.img)

    def c(self, col):
        if isinstance(col, str):
            col = COLORS[col]
        return QColor(*col) if isinstance(col, tuple) else col

    def rect(self, x, y, w, h, col):
        if w <= 0 or h <= 0:
            return
        k = self.u * self.dpr
        self.p.fillRect(QRect(int(round(x * k)), int(round(y * k)), int(round(w * k)), int(round(h * k))),
                        self.c(col))

    def px(self, x, y, col):
        self.rect(x, y, 1, 1, col)

    def box(self, x, y, w, h, fill, ink="K"):
        self.rect(x, y, w, h, ink)
        self.rect(x + 1, y + 1, w - 2, h - 2, fill)

    def grid(self, x, y, grid, flip=False):
        for gy, row in enumerate(grid):
            row = row[::-1] if flip else row
            for gx, ch in enumerate(row):
                if ch != ".":
                    self.px(x + gx, y + gy, ch)

    def pixmap(self):
        self.p.end()
        pm = QPixmap.fromImage(self.img)
        pm.setDevicePixelRatio(self.dpr)
        return pm


def cardboard_box(unit, front_only=False):
    """紙箱 26x16：front_only=True 只畫前面的板子（貓咪坐在箱子裡時蓋在貓上）。"""
    key = ("box", unit, front_only)
    if key in _cache:
        return _cache[key]
    c = Canvas(26, 18, unit)
    if not front_only:
        # 打開的蓋子（左右往外翻）
        for i in range(4):
            c.rect(0 + i, 2 + i, 4, 1, "K")
            c.rect(22 - i, 2 + i, 4, 1, "K")
        c.rect(1, 3, 3, 1, "E"); c.rect(2, 4, 3, 1, "E"); c.rect(3, 5, 2, 1, "A")
        c.rect(22, 3, 3, 1, "E"); c.rect(21, 4, 3, 1, "E"); c.rect(21, 5, 2, 1, "A")
        # 箱子裡面（暗）
        c.rect(3, 5, 20, 3, "K")
        c.rect(4, 6, 18, 2, "a")
        c.rect(4, 6, 18, 1, "D")
    # 前面的板子
    c.rect(3, 7, 20, 11, "K")
    c.rect(4, 8, 18, 9, "A")
    c.rect(4, 8, 18, 1, "E")
    c.rect(4, 16, 18, 1, "a")
    c.rect(12, 8, 2, 8, "E")                    # 膠帶
    c.rect(12, 8, 2, 1, "C")
    c.rect(6, 11, 3, 2, "a"); c.px(7, 11, "E")  # 小小的貓掌印章
    c.px(6, 10, "a"); c.px(8, 10, "a")
    _cache[key] = c.pixmap()
    return _cache[key]


BOX_W, BOX_H = 26, 18
TREE_W, TREE_H = 26, 46
TREE_TOP = 6          # 最上層平台的頂端（貓咪腳踩的位置）
TREE_MID = 22         # 中層平台


def cat_tree(unit):
    key = ("tree", unit)
    if key in _cache:
        return _cache[key]
    c = Canvas(TREE_W, TREE_H, unit)

    def platform(x, y, w, fill, light):
        c.rect(x, y, w, 4, "K")
        c.rect(x + 1, y + 1, w - 2, 2, fill)
        c.rect(x + 1, y + 1, w - 2, 1, light)

    def post(x, y0, y1):
        c.rect(x, y0, 6, y1 - y0, "K")
        c.rect(x + 1, y0, 4, y1 - y0, "E")
        for yy in range(y0 + 1, y1, 2):
            c.rect(x + 1, yy, 4, 1, "A")
    post(10, TREE_TOP + 3, TREE_MID + 1)
    post(10, TREE_MID + 3, TREE_H - 4)
    post(3, TREE_MID + 3, TREE_H - 4)
    platform(1, TREE_MID, 24, "Q", (150, 228, 214))
    platform(5, TREE_TOP, 16, "P", "H")
    c.rect(6, TREE_TOP - 2, 14, 2, "K")          # 上層的軟墊
    c.rect(7, TREE_TOP - 2, 12, 2, "H")
    # 吊著的小毛球
    c.rect(22, TREE_MID + 3, 1, 7, "K")
    c.rect(21, TREE_MID + 10, 3, 3, "K"); c.px(22, TREE_MID + 11, "Y")
    # 底座
    c.rect(0, TREE_H - 4, TREE_W, 4, "K")
    c.rect(1, TREE_H - 3, TREE_W - 2, 2, "T")
    c.rect(1, TREE_H - 3, TREE_W - 2, 1, (186, 136, 96))
    _cache[key] = c.pixmap()
    return _cache[key]
