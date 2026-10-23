"""像素風格的共用工具：像素字型、像素圖示、會變色的番茄、遊戲風對話框。"""
import colorsys

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QImage, QPainter, QPixmap

import sprites

INK = QColor(58, 55, 55)          # 和貓咪外框同色
PAPER = QColor(255, 248, 231)
PAPER_HI = QColor(255, 255, 250)
GOLD = QColor(233, 200, 120)
GOLD_DARK = QColor(195, 151, 83)
SHADOW = QColor(30, 25, 25, 70)

_family = None
_cache = {}

PALETTE = {
    "K": (58, 55, 55), "W": (255, 255, 255), "C": (250, 241, 218), "S": (160, 160, 170),
    "s": (110, 110, 122), "R": (217, 72, 59), "r": (160, 45, 40), "G": (120, 178, 72),
    "g": (72, 122, 52), "Y": (236, 196, 88), "y": (198, 150, 62), "B": (98, 150, 214),
    "b": (60, 98, 162), "P": (238, 150, 160), "T": (153, 107, 74), "t": (120, 80, 55),
    "O": (236, 150, 64), "L": (217, 183, 92), "M": (195, 151, 83),
}

ICONS = {
    "note": [
        ".KKKKKKKK...",
        ".KCCCCCCKK..",
        ".KCSSSSCKCK.",
        ".KCCCCCCKKKK",
        ".KCSSSSSSSCK",
        ".KCCCCCCCCCK",
        ".KCSSSSSSSCK",
        ".KCCCCCCCCCK",
        ".KCSSSSCCCCK",
        ".KCCCCCCCCCK",
        ".KKKKKKKKKKK",
    ],
    "can": [
        "............",
        "..KKKKKKKK..",
        ".KSSSSSSSSK.",
        ".KWWWWWWWWK.",
        ".KRRRRRRRRK.",
        ".KRWWRRWWRK.",
        ".KRWWRRWWRK.",
        ".KRRRRRRRRK.",
        ".KSSSSSSSSK.",
        "..KKKKKKKK..",
    ],
    "paw": [
        "...KK..KK...",
        "..KPPKKPPK..",
        "..KPPKKPPK..",
        "KK.KK..KK.KK",
        "KPK......KPK",
        "KPK.KKKK.KPK",
        ".K.KPPPPK.K.",
        "..KPPPPPPK..",
        "..KPPPPPPK..",
        "...KPPPPK...",
        "....KKKK....",
    ],
    "palette": [
        "...KKKKKK...",
        "..KCCCCCCK..",
        ".KCRRCCBBCK.",
        "KCCRRCCBBCCK",
        "KCCCCCCCCCCK",
        "KCGGCCKKCYYK",
        "KCGGCK..KYYK",
        "KCCCCK..KCCK",
        ".KCCCCKKCCK.",
        "..KCCCCCCK..",
        "...KKKKKK...",
    ],
    "facing": [
        "............",
        "...K....K...",
        "..KBK..KBK..",
        ".KBBKKKKBBK.",
        "KBBBBBBBBBBK",
        ".KBBKKKKBBK.",
        "..KBK..KBK..",
        "...K....K...",
    ],
    "size": [
        "..KKKK......",
        ".KWWWWK.....",
        "KWBWWWWK....",
        "KWBWWWWK....",
        "KWWWWWWK....",
        "KWWWWWWK....",
        ".KWWWWK.....",
        "..KKKKKK....",
        "......KsK...",
        ".......KsK..",
        "........KsK.",
        ".........KK.",
    ],
    "home": [
        ".....KK.....",
        "....KRRK....",
        "...KRRRRK...",
        "..KRRRRRRK..",
        ".KRRRRRRRRK.",
        "KKKKKKKKKKKK",
        ".KCCCCCCCCK.",
        ".KCBBCCTTCK.",
        ".KCBBCCTTCK.",
        ".KCCCCCTTCK.",
        ".KKKKKKKKKK.",
    ],
    "gear": [
        "....KKKK....",
        ".KK.KSSK.KK.",
        ".KSKKSSKKSK.",
        "..KSSSSSSK..",
        "KKKSSKKSSKKK",
        "KSSSK..KSSSK",
        "KSSSK..KSSSK",
        "KKKSSKKSSKKK",
        "..KSSSSSSK..",
        ".KSKKSSKKSK.",
        ".KK.KSSK.KK.",
        "....KKKK....",
    ],
    "globe": [
        "...KKKKKK...",
        "..KBGGBBBK..",
        ".KBGGGGBGGK.",
        ".KBBGGBBGGK.",
        "KBBBBGBBBGBK",
        "KBBBBBBBBBBK",
        "KBGGBBBBBBBK",
        "KBGGGBBBGBBK",
        ".KBGGBBGGGK.",
        ".KBBBBBGGBK.",
        "..KBBBBBBK..",
        "...KKKKKK...",
    ],
    "power": [
        ".....KK.....",
        "..KK.KRK.KK.",
        ".KRK.KRK.KRK",
        "KRK..KRK..KR",
        "KR...KRK...K",
        "KR....K....K",
        "KR.........K",
        ".KR.......KR",
        "..KRR...RRK.",
        "...KKRRRKK..",
        ".....KKK....",
    ],
    "check": [
        "..........K",
        ".........KG",
        "........KGK",
        ".K.....KGK.",
        "KGK...KGK..",
        ".KGK.KGK...",
        "..KGKGK....",
        "...KGK.....",
        "....K......",
    ],
    "dot": [
        "............",
        "............",
        "....KKKK....",
        "...KGGGGK...",
        "...KGGGGK...",
        "...KGGGGK...",
        "...KGGGGK...",
        "....KKKK....",
    ],
    "plus": [
        "..KKK..",
        "..KGK..",
        "KKKGKKK",
        "KGGGGGK",
        "KKKGKKK",
        "..KGK..",
        "..KKK..",
    ],
    "pencil": [
        ".........KK.",
        "........KRRK",
        ".......KYKRK",
        "......KYYYK.",
        ".....KYYYK..",
        "....KYYYK...",
        "...KYYYK....",
        "..KYYYK.....",
        ".KCYYK......",
        ".KCCK.......",
        "KKKK........",
    ],
    "minus": [
        "KKKKKKK",
        "KWWWWWK",
        "KKKKKKK",
    ],
    "cup": [
        "..S..S......",
        "...S..S.....",
        "..S..S......",
        "KKKKKKKKK...",
        "KCCCCCCCKKK.",
        "KTTTTTTTK.K.",
        "KTTTTTTTKKK.",
        "KTTTTTTTK...",
        ".KTTTTTK....",
        "..KKKKK.....",
    ],
    "close": [
        "KK...KK",
        "KKK.KKK",
        ".KKKKK.",
        "..KKK..",
        ".KKKKK.",
        "KKK.KKK",
        "KK...KK",
    ],
}

TOMATO = [
    ".....gg.....",
    "...gGGGGg...",
    "..KKgGGgKK..",
    ".KHBKggKBBK.",
    "KHHBBBBBBBDK",
    "KHBBBBBBBBDK",
    "KBBBBBBBBBDK",
    "KBBBBBBBBDDK",
    "KBBBBBBBDDDK",
    ".KBBBBBDDDK.",
    "..KDDDDDDK..",
    "...KKKKKK...",
]


def _dpr():
    return max((s.devicePixelRatio() for s in QGuiApplication.screens()), default=1.0)


# ---------------- 字型 ---------------- #
def font_family():
    global _family
    if _family is None:
        fid = QFontDatabase.addApplicationFont(sprites.resource_path("assets", "fonts", "fusion-pixel.ttf"))
        fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
        _family = fams[0] if fams else ""
    return _family


def font(px=12):
    f = QFont(font_family()) if font_family() else QFont()
    f.setPixelSize(px)
    f.setStyleStrategy(QFont.NoAntialias)
    f.setHintingPreference(QFont.PreferNoHinting)
    return f


# ---------------- 像素圖 ---------------- #
def _grid_pixmap(grid, unit, colors=None, size=None):
    colors = colors or {}
    gh = len(grid)
    gw = max(len(r) for r in grid)
    w, h = size or (gw, gh)
    ox, oy = (w - gw) // 2, (h - gh) // 2
    dpr = _dpr()
    img = QImage(int(w * unit * dpr), int(h * unit * dpr), QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    cell = unit * dpr
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            rgb = colors.get(ch) or PALETTE.get(ch)
            if rgb is None:
                continue
            p.fillRect(QRect(int((x + ox) * cell), int((y + oy) * cell), int(cell + 0.99), int(cell + 0.99)),
                       QColor(*rgb) if isinstance(rgb, tuple) else rgb)
    p.end()
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(dpr)
    return pm


def icon_pixmap(name, unit=2, size=(12, 12)):
    key = ("icon", name, unit, size)
    if key not in _cache:
        _cache[key] = _grid_pixmap(ICONS[name], unit, size=size)
    return _cache[key]


MENU_UNIT = 1.5   # 選單圖示：12 格 × 1.5 = 18pt，Retina 上剛好每格 3 個實體像素


def icon(name):
    return QIcon(icon_pixmap(name, MENU_UNIT))


def blank_icon():
    key = ("blank",)
    if key not in _cache:
        pm = QPixmap(int(18 * _dpr()), int(18 * _dpr()))
        pm.fill(Qt.transparent)
        pm.setDevicePixelRatio(_dpr())
        _cache[key] = QIcon(pm)
    return _cache[key]


def cat_head_icon(color, plus=False, check=False):
    """從原始精靈圖裁出貓咪正面的頭當圖示。"""
    key = ("cathead", sprites._sp_key(color), plus, check)
    if key not in _cache:
        walk = sprites._recolor(sprites._image("base_walk.png"), sprites.spec(color))
        head = walk.copy(32 + 17, 48 + 23, 12, 12)               # 側臉的頭（含耳朵）
        dpr = _dpr()
        img = QImage(int(18 * dpr), int(18 * dpr), QImage.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(Qt.transparent)
        p = QPainter(img)                       # 以下座標都是邏輯像素
        p.drawImage(QRect(0, 0, 18, 18), head)
        if plus:
            p.drawPixmap(8, 8, icon_pixmap("plus", 1.5, (7, 7)))
        if check:
            p.drawPixmap(7, 9, icon_pixmap("check", 1.0, (11, 9)))
        p.end()
        pm = QPixmap.fromImage(img)
        _cache[key] = QIcon(pm)
    return _cache[key]


def _lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def tomato_color(progress):
    """0 → 黃綠、0.5 → 黃橘、1 → 紅。"""
    stops = [(0.0, (150, 192, 64)), (0.5, (236, 168, 56)), (1.0, (215, 62, 50))]
    progress = max(0.0, min(1.0, progress))
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if progress <= p1:
            return _lerp(c0, c1, (progress - p0) / (p1 - p0))
    return stops[-1][1]


def _shade(rgb, dl):
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    r, g, b = colorsys.hls_to_rgb(h, max(0, min(1, l + dl)), s)
    return int(r * 255), int(g * 255), int(b * 255)


def tomato(progress, unit=2):
    """依專注進度變色的像素番茄（快取成 24 段）。"""
    step = round(max(0.0, min(1.0, progress)) * 24)
    key = ("tomato", step, unit)
    if key not in _cache:
        base = tuple(int(c) for c in tomato_color(step / 24))
        colors = {"B": base, "H": _shade(base, 0.16), "D": _shade(base, -0.14)}
        _cache[key] = _grid_pixmap(TOMATO, unit, colors)
    return _cache[key]


# ---------------- 遊戲風對話框 ---------------- #
def draw_box(p, rect, u=2, fill=PAPER, ink=INK, light=PAPER_HI, shadow=True):
    """畫一個像素風的框：缺角外框、內側亮邊、右下陰影。"""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

    def notched(x, y, w, h, color, cut=u):
        p.fillRect(QRect(x + cut, y, w - 2 * cut, h), color)
        p.fillRect(QRect(x, y + cut, w, h - 2 * cut), color)

    if shadow:
        notched(x + u, y + u, w, h, SHADOW)
    notched(x, y, w, h, ink)
    notched(x + u, y + u, w - 2 * u, h - 2 * u, fill, cut=0)
    if light is not None:
        p.fillRect(QRect(x + 2 * u, y + u, w - 4 * u, u), light)
        p.fillRect(QRect(x + u, y + 2 * u, u, h - 4 * u), light)


def draw_tail(p, cx, top, u=2, fill=PAPER, ink=INK):
    """對話框下方的階梯狀小尾巴（top = 框的底邊外框所在 y）。"""
    p.fillRect(QRect(cx - 3 * u, top, 6 * u, u), fill)          # 蓋掉框底邊
    rows = [(4, 3), (3, 2), (2, 1), (1, 0)]
    for i, (outer, inner) in enumerate(rows):
        y = top + i * u
        p.fillRect(QRect(cx - outer * u, y, 2 * outer * u, u), ink)
        if inner:
            p.fillRect(QRect(cx - inner * u, y, 2 * inner * u, u), fill)
    p.fillRect(QRect(cx - 4 * u, top, u, u), ink)
    p.fillRect(QRect(cx + 3 * u, top, u, u), ink)
