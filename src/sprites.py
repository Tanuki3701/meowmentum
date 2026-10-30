"""載入精靈圖、換上毛色，並預先放大快取（每張圖只處理一次）。

所有貓咪圖都存成「語意索引」（外框、陰影、中間色、亮色、粉紅、腮紅、眼睛…），
執行時換上任何毛色：內建四色和原圖逐像素相同，使用者也可以自訂顏色。
"""
import colorsys
import os
import sys

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPixmap, QTransform

FRAME_W, FRAME_H = 32, 48
FRAMES_PER_DIR = 3
FOOT_GAP = 5  # 腳下方的透明像素列數（原圖第 43~47 列是空的）

SEM = ".ORDPMLEFW"     # base 圖的索引順序
INK = (58, 55, 55)
EXPRESSIONS = ["happy", "excited", "yuck", "dizzy"]

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
CUSTOM = {}            # id -> spec，由 controller 從設定載入

# effects.png 裡每個特效的範圍 (x, y, w, h)
EFFECTS = {"heart": (0, 0, 7, 6), "zzz": (8, 0, 5, 5), "sparkle": (14, 0, 7, 7),
           "sweat": (22, 0, 5, 7), "note": (28, 0, 6, 7)}
FLAVORS = ["tuna", "chicken", "salmon", "catnip", "bitter"]
for _i, _f in enumerate(FLAVORS):
    EFFECTS["can_" + _f] = (_i * 11, 8, 10, 8)
EFFECTS["can"] = EFFECTS["can_tuna"]

# 貓屋開口（house.png 座標）：(x, y, w, h)
HOUSE_W, HOUSE_H, HOUSE_GROUND = 56, 56, 52
HOUSE_CHIMNEY = (41, 2)
HOUSE_SLOTS = {"door": (22, 38, 12, 14), "left": (11, 31, 9, 7), "right": (36, 31, 9, 7),
               "attic": (23, 12, 10, 6)}
SLOT_ORDER = ["door", "left", "right", "attic"]

_cache = {}

# 花紋分組：(格子們, 是否左右鏡像)。走路圖第 0 列背面、1 右、2 正面、3 左（左 = 右的鏡像）
WALK_GROUPS = [([(f * FRAME_W, d * FRAME_H, FRAME_W, FRAME_H) for f in range(FRAMES_PER_DIR)], d == 3)
               for d in range(4)]
SLEEP_GROUPS = [([(i * FRAME_W, 0, FRAME_W, FRAME_H) for i in range(2)], False)]
EXPR_GROUPS = [([(i * FRAME_W, 0, FRAME_W, FRAME_H)], False) for i in range(len(EXPRESSIONS))]
# 新動作（base_pose.png 的順序，和 tools/make_sprites.py 的 POSE_ORDER 一樣）
POSES = [("sit", 2), ("stretch", 1), ("wash", 2), ("yawn", 1), ("loaf", 2), ("belly", 2)]
POSE_HEAD = {"sit": (-3, 0), "stretch": (2, 8), "wash": (-3, 0), "yawn": (-3, 0), "loaf": (-2, 8),
             "belly": (-1, 9)}
POSE_GROUPS = []
_i = 0
for _name, _n in POSES:
    POSE_GROUPS.append(([((_i + k) * FRAME_W, 0, FRAME_W, FRAME_H) for k in range(_n)], False))
    _i += _n
FACE_GROUPS = [([(0, 0, 16, 14)], False), ([(16, 0, 10, 8)], False), ([(26, 0, 6, 5)], False)]


def resource_path(*parts):
    """同時支援直接執行原始碼與 PyInstaller 打包後的 .app。"""
    base = getattr(sys, "_MEIPASS", None) or os.path.join(os.path.dirname(__file__), "..")
    return os.path.join(base, *parts)


def _dpr():
    return max((s.devicePixelRatio() for s in QGuiApplication.screens()), default=1.0)


def _image(name):
    key = ("img", name)
    if key not in _cache:
        path = resource_path("assets", "sprites", name)
        img = QImage(path)
        if img.isNull():
            raise FileNotFoundError(f"找不到圖檔: {path}")
        _cache[key] = img
    return _cache[key]


# ---------------- 毛色 ---------------- #
def _shift(rgb, dl=0.0, ds=0.0, dh=0.0):
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    r, g, b = colorsys.hls_to_rgb((h + dh) % 1, max(0, min(1, l + dl)), max(0, min(1, s + ds)))
    return int(r * 255), int(g * 255), int(b * 255)


PATTERNS = ["solid", "tabby", "tuxedo", "calico", "spots"]    # 舊版的花紋名稱（設定檔相容用）
BASES = ["solid", "calico", "spots"]     # 底色花紋（三選一）
EXTRAS = ["stripes", "white"]            # 可以疊在任何底色上的：虎斑條紋、賓士白
DETAILS = ["points", "gradient", "ears", "tail"]   # 細節：重點色（暹羅貓）、漸層、耳朵顏色、尾巴顏色
DETAIL_DEFAULTS = {"points": (92, 64, 52), "gradient": None, "ears": (70, 60, 66), "tail": (70, 60, 66)}
PATTERN_DEFAULTS = {          # 花紋的預設顏色（p1、p2）
    "tabby": ((110, 70, 50), None),
    "tuxedo": ((246, 244, 240), None),
    "calico": ((222, 130, 60), (60, 52, 56)),
    "spots": ((60, 52, 56), None),
}
WHITE_DEFAULT = (246, 244, 240)


def stripe_default(fur):
    """虎斑條紋的預設顏色：比毛色深一階。"""
    return _shift(tuple(fur), -0.26, 0.02, -0.01)


def normalize_look(pattern="solid", p1=None, p2=None, stripes=None, white=None):
    """把舊的單一花紋（tabby / tuxedo）轉成新的「底色花紋 + 條紋 + 白色」組合。"""
    base = pattern
    if pattern == "tabby":
        base, stripes = "solid", stripes or p1 or PATTERN_DEFAULTS["tabby"][0]
        p1 = p2 = None
    elif pattern == "tuxedo":
        base, white = "solid", white or p1 or WHITE_DEFAULT
        p1 = p2 = None
    if base not in BASES:
        base = "solid"
    return base, p1, p2, stripes, white


def derive_spec(fur, eye=None, pattern="solid", p1=None, p2=None, stripes=None, white=None, eye2=None,
                points=None, gradient=None, ears=None, tail=None):
    """從毛色、眼睛顏色（可以兩眼不同）和花紋推出整組像素調色盤。

    花紋可以自由組合：底色花紋（純色 / 三花 / 斑點）上面還能再加虎斑條紋和賓士白。
    """
    sp = _derive_base(fur, eye)
    base, p1, p2, stripes, white = normalize_look(pattern, p1, p2, stripes, white)
    layers = []
    if base in PATTERN_DEFAULTS:
        d1, d2 = PATTERN_DEFAULTS[base]
        p1 = tuple(p1) if p1 else d1
        p2 = tuple(p2) if p2 else d2
        layers.append(base)
        sp["A"], sp["a"] = p1, _shift(p1, 0.08, 0.02)
        if p2:
            sp["B"], sp["b"] = p2, _shift(p2, 0.08, 0.02)
    if stripes:
        layers.append("stripes")
        sp["S"] = tuple(stripes)
    if white:
        layers.append("white")
        sp["T"], sp["t"] = tuple(white), _shift(tuple(white), 0.05, 0.0)
    if gradient:                                  # 漸層：背上的顏色慢慢接到原本的毛色
        layers.append("gradient")
        g = tuple(gradient)
        sp["Ga"] = g
        sp["Gb"] = tuple((a + b) // 2 for a, b in zip(g, sp["M"]))
    if points:
        layers.append("points")
        pt = tuple(points)
        sp["Pt"], sp["Pl"], sp["Pd"] = pt, _shift(pt, 0.08, 0.02), _shift(pt, -0.12)
    if ears:
        layers.append("ears")
        sp["Er"], sp["Ed"] = tuple(ears), _shift(tuple(ears), -0.12)
    if tail:
        layers.append("tail")
        sp["Tl"], sp["Td"] = tuple(tail), _shift(tuple(tail), -0.12)
    if layers:
        sp["pattern"] = tuple(layers)
    if eye2 and tuple(eye2) != tuple(eye or INK):
        eye2 = tuple(eye2)
        sp["E2"], sp["F2"] = eye2, (_shift(eye2, 0.15) if eye2 != INK else INK)
    return sp


def swap_eyes(sp):
    """左右相反的圖（鏡像）要把兩隻眼睛的顏色對調，異色瞳才不會換邊。"""
    if "E2" not in sp:
        return sp
    sp = dict(sp)
    sp["E"], sp["E2"], sp["F"], sp["F2"] = sp["E2"], sp["E"], sp["F2"], sp["F"]
    return sp


def _derive_base(fur, eye=None):
    fur = tuple(fur)
    light = _shift(fur, 0.10, 0.02)
    dark = _shift(fur, -0.24, 0.0, -0.01)
    lum = colorsys.rgb_to_hls(*(c / 255 for c in fur))[1]
    pink = (214, 150, 140) if lum > 0.35 else (186, 108, 96)
    blush = (222, 120, 110) if lum > 0.35 else (177, 78, 69)
    eye = tuple(eye) if eye else INK
    return dict(O=INK, R=blush, D=dark, P=pink, M=fur, L=light,
                E=eye, F=_shift(eye, 0.15) if eye != INK else INK)


def spec(color):
    return BUILTIN.get(color) or CUSTOM.get(color) or BUILTIN["orange"]


def _recolor(img, sp, groups=None):
    out = QImage(img)            # 複製一份，換掉調色盤
    table = [0]
    for ch in SEM[1:]:
        rgb = (255, 255, 255) if ch == "W" else sp[ch]
        table.append(QColor(*rgb).rgba())
    for ch in "AaBbSTt":         # 花紋用的額外顏色（索引 10~16）
        table.append(QColor(*sp.get(ch, sp["M"])).rgba())
    table.append(QColor(*sp.get("E2", sp["E"])).rgba())      # 17、18：另一隻眼睛
    table.append(QColor(*sp.get("F2", sp["F"])).rgba())
    for ch, fb in (("Pt", "M"), ("Pl", "L"), ("Pd", "D"), ("Ga", "M"), ("Gb", "M"),
                   ("Er", "M"), ("Ed", "D"), ("Tl", "M"), ("Td", "D")):   # 19~27：細節
        table.append(QColor(*sp.get(ch, sp[fb])).rgba())
    if (sp.get("pattern") or "E2" in sp) and groups:
        out = _apply_pattern(out, sp, groups)
    table += [0] * (max(out.colorCount(), 256) - len(table))
    out.setColorTable(table[:max(out.colorCount(), 256)])
    return out


# ---------------- 花紋 ---------------- #
_M, _L = SEM.index("M"), SEM.index("L")
_E, _F = SEM.index("E"), SEM.index("F")
_A, _Aa, _B, _Bb, _S, _T, _Tt, _E2, _F2 = 10, 11, 12, 13, 14, 15, 16, 17, 18
_Pt, _Pl, _Pd, _Ga, _Gb, _Er, _Ed, _Tl, _Td = 19, 20, 21, 22, 23, 24, 25, 26, 27
_D = SEM.index("D")
_PINK = SEM.index("P")


def _regions(img, rx, ry, rw, rh, top, bot):
    """找出一格圖裡的臉、耳朵、腳掌和尾巴（給重點色、耳朵和尾巴顏色用）。"""
    pix = [(x, y) for y in range(rh) for x in range(rw) if img.pixelIndex(rx + x, ry + y)]
    if not pix:
        return set(), set(), set()
    pink = [(x, y) for x, y in pix if img.pixelIndex(rx + x, ry + y) == _PINK and y < rh * 0.8]
    if pink:
        ey = min(y for _, y in pink)
        ear_px = [x for x, y in pink if y <= ey + 2]
        hx, hy = sum(ear_px) / len(ear_px), ey + 5
        ear_top = ey - 2
    else:                                          # 背面：看不到臉，用最上面的那幾排當耳朵
        ear_top = min(y for _, y in pix)
        xs = [x for x, y in pix if y <= ear_top + 3]
        hx, hy = sum(xs) / len(xs), ear_top + 6
    face, ears, tail = set(), set(), set()
    for x, y in pix:
        if ((x - hx) / 5.2) ** 2 + ((y - hy) / 4.6) ** 2 <= 1:
            face.add((x, y))
        if ear_top <= y <= ear_top + 3 and abs(x - hx) <= 6.5:
            ears.add((x, y))
        if 0 <= x < len(top) and bot[x] >= 0 and bot[x] - top[x] <= 6 and abs(x - hx) > 9:
            tail.add((x, y))
    return face, ears, tail


def _noise(x, y, g, salt):
    """平滑的數值雜訊（0~1），同一組座標永遠得到同一個值，花紋才不會閃。"""
    def h(i, j):
        n = (i * 374761393 + j * 668265263 + salt * 2246822519) & 0xFFFFFFFF
        n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF) / 65535
    gx, gy = x / g, y / g
    i, j = int(gx // 1), int(gy // 1)
    fx, fy = gx - i, gy - j
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    top = h(i, j) * (1 - fx) + h(i + 1, j) * fx
    bot = h(i, j + 1) * (1 - fx) + h(i + 1, j + 1) * fx
    return top * (1 - fy) + bot * fy


def _split_eyes(img, rx, ry, rw, rh):
    """異色瞳：把畫面右邊那隻眼睛換成第二個眼睛顏色。

    正面看得到兩隻眼睛，右邊那團換色；側面只看得到一隻，看貓臉朝哪邊決定。
    """
    eyes, body = [], []
    for y in range(rh):
        for x in range(rw):
            idx = img.pixelIndex(rx + x, ry + y)
            if idx:
                body.append(x)
            if idx in (_E, _F):
                eyes.append((x, y, idx))
    if not eyes:
        return
    xs = sorted({x for x, _, _ in eyes})
    cut = None
    for a, b in zip(xs, xs[1:]):
        if b - a > 1:
            cut = b                      # 兩團眼睛中間的空隙
    if cut is None:                      # 側面：眼睛在身體中心的右邊 = 臉朝右
        center = sum(body) / len(body)
        cut = 0 if sum(xs) / len(xs) > center else rw
    for x, y, idx in eyes:
        if x >= cut:
            img.setPixel(rx + x, ry + y, _E2 if idx == _E else _F2)


def _apply_pattern(img, sp, groups):
    """groups：[(rects, mirror)]；同一組的格子（同方向的走路格）共用同一套花紋座標。

    花紋一層一層疊上去：底色花紋（三花 / 斑點）→ 虎斑條紋 → 賓士白（胸口、肚子和腳掌）。
    """
    img = img.convertToFormat(QImage.Format_Indexed8, img.colorTable()) \
        if img.format() != QImage.Format_Indexed8 else QImage(img)
    layers = sp.get("pattern") or ()
    if isinstance(layers, str):
        layers = (layers,)
    detail = any(k in layers for k in ("points", "ears", "tail"))
    for rects, mirror in groups:
        if layers:
            # 每一欄毛的上下範圍（取同組所有格子的聯集，走路時花紋才不會跳）
            w = max(r[2] for r in rects)
            top, bot = [99] * w, [-1] * w
            for rx, ry, rw, rh in rects:
                for x in range(rw):
                    for y in range(rh):
                        if img.pixelIndex(rx + x, ry + y) in (_M, _L):
                            top[x] = min(top[x], y)
                            bot[x] = max(bot[x], y)
            for rx, ry, rw, rh in rects:
                face, ears, tail = _regions(img, rx, ry, rw, rh, top, bot) if detail else (set(), set(), set())
                for x in range(rw):
                    if bot[x] < 0:
                        continue
                    span = max(1, bot[x] - top[x])
                    nx = (rw - 1 - x) if mirror else x
                    for y in range(rh):
                        idx = img.pixelIndex(rx + x, ry + y)
                        if idx == _D and detail:          # 深色的輪廓陰影也跟著換
                            if "tail" in layers and (x, y) in tail:
                                img.setPixel(rx + x, ry + y, _Td)
                            elif "ears" in layers and (x, y) in ears:
                                img.setPixel(rx + x, ry + y, _Ed)
                            elif "points" in layers and ((x, y) in face or (x, y) in ears or (x, y) in tail):
                                img.setPixel(rx + x, ry + y, _Pd)
                            continue
                        if idx not in (_M, _L):
                            continue
                        v = (y - top[x]) / span          # 0 = 這一欄最上面，1 = 最下面（肚子、腳）
                        light = idx == _L
                        new = None
                        if "gradient" in layers:
                            if v < 0.3:
                                new = _Ga
                            elif v < 0.5:
                                new = _Gb
                        if "calico" in layers and v < 0.7:
                            if _noise(nx, y, 5.0, 7) > 0.56:
                                new = _Aa if light else _A
                            elif _noise(nx, y, 4.5, 19) > 0.6:
                                new = _Bb if light else _B
                        if "spots" in layers and _noise(nx, y, 4.0, 31) > 0.62:
                            new = _Aa if light else _A
                        if "stripes" in layers and v < 0.72 and (nx + y // 3) % 3 == 0:
                            new = _S
                        if "points" in layers and ((x, y) in face or (x, y) in ears or (x, y) in tail or v > 0.86):
                            new = _Pl if light else _Pt
                        if "white" in layers and v > 0.58:
                            new = _Tt if light else _T
                        if "ears" in layers and (x, y) in ears:
                            new = _Er
                        if "tail" in layers and (x, y) in tail:
                            new = _Tl
                        if new is not None:
                            img.setPixel(rx + x, ry + y, new)
        if "E2" in sp:
            for rect in rects:
                _split_eyes(img, *rect)
    return img


def _scaled(img, scale):
    dpr = _dpr()
    pm = QPixmap.fromImage(img.scaled(round(img.width() * scale * dpr), round(img.height() * scale * dpr),
                                      Qt.IgnoreAspectRatio, Qt.FastTransformation))
    pm.setDevicePixelRatio(dpr)
    return pm


def _sp_key(color):
    return tuple(sorted(spec(color).items()))


# ---------------- 貓咪 ---------------- #
_P_IDX = SEM.index("P")


def _head_anchor(img, x0, y0, view):
    """從原圖算出頭的位置：(兩耳中間的 x, 耳朵頂端 y)。view：back / right / front / sleep。"""
    pts = [(x, y) for y in range(FRAME_H) for x in range(FRAME_W) if img.pixelIndex(x0 + x, y0 + y)]
    if view == "front":
        # 正面：頭上方會看到身體，用粉紅色的耳朵內側找耳朵
        rows = [y for x, y in pts if img.pixelIndex(x0 + x, y0 + y) == _P_IDX]
        top = min(rows) - 1
        xs = [x for x, y in pts if y == top + 1 and img.pixelIndex(x0 + x, y0 + y) == _P_IDX]
        return (min(xs) + max(xs)) / 2, top
    top = min(y for _, y in pts)
    xs = [x for x, y in pts if y == top]
    return (min(xs) + max(xs)) / 2, top


def _paint_grid(p, grid, x0, y0, flip=False):
    import art
    for gy, row in enumerate(grid):
        row = row[::-1] if flip else row
        for gx, ch in enumerate(row):
            if ch != ".":
                p.fillRect(int(x0 + gx), int(y0 + gy), 1, 1, QColor(*art.COLORS[ch]))


def _dress(frame, anchor, view, hat, neck, face_left=False):
    """把帽子、脖子的飾品畫到一格 32x48 的圖上（原尺寸，之後再放大）。"""
    if not hat and not neck:
        return frame
    import art
    from PySide6.QtGui import QPainter
    img = frame.convertToFormat(QImage.Format_ARGB32)
    p = QPainter(img)
    cx, top = anchor
    if neck and view != "sleep":
        n = art.NECKS[neck]
        if view in ("front", "back"):
            g = n["front"]
            w = max(len(r) for r in g)
            y = top + (8 if view == "front" else 10)
            _paint_grid(p, g, round(cx - w / 2 + 0.01), y)
        else:
            g = n["side"]
            w = max(len(r) for r in g)
            x = cx - 6 if not face_left else cx + 6 - w + 1
            _paint_grid(p, g, round(x), top + 5, flip=face_left)
    if hat:
        g = art.HATS[hat]
        w, h = max(len(r) for r in g), len(g)
        dx = art.HAT_DX.get(hat, 0) * (-1 if face_left else 1)
        y = top + 3 + art.HAT_SINK.get(hat, 0) - h - (1 if view == "front" else 0)
        _paint_grid(p, g, round(cx + dx - w / 2 + 0.01), y, flip=face_left)
    p.end()
    return img


def cat_frames(color, scale, hat=None, neck=None):
    """回傳 dict：walk[方向][格]、sleep[0=面右/1=面左][格]、expr[名稱][0=右/1=左]。"""
    key = ("cat", _sp_key(color), scale, hat, neck)
    if key not in _cache:
        sp = spec(color)
        base_walk = _image("base_walk.png")
        walk_img = _recolor(base_walk, sp, WALK_GROUPS)
        views = {0: "back", 1: "right", 2: "front", 3: "right"}
        walk = []
        for d in range(4):
            row = []
            for f in range(FRAMES_PER_DIR):
                x0, y0 = f * FRAME_W, d * FRAME_H
                fr = walk_img.copy(x0, y0, FRAME_W, FRAME_H)
                anc = _head_anchor(base_walk, x0, y0, views[d])
                fr = _dress(fr, anc, views[d], hat, neck, face_left=(d == 3))
                row.append(_scaled(fr, scale))
            walk.append(row)
        mirror = QTransform().scale(-1, 1)

        def both(name, groups, n, view, anchors=None):
            base = _image(name)
            out = []
            for s_ in (sp, swap_eyes(sp)):       # 鏡像那一組用對調過的眼睛顏色
                img = _recolor(base, s_, groups)
                frames = []
                for i in range(n):
                    fr = img.copy(i * FRAME_W, 0, FRAME_W, FRAME_H)
                    anc = anchors[i] if anchors else _head_anchor(base, i * FRAME_W, 0, view)
                    fr = _dress(fr, anc, view, hat, neck)
                    frames.append(fr)
                out.append(frames)
            return [[_scaled(x, scale) for x in out[0]],
                    [_scaled(x.transformed(mirror), scale) for x in out[1]]]

        sleep = both("base_sleep.png", SLEEP_GROUPS, 2, "sleep")
        ex = both("base_expr.png", EXPR_GROUPS, len(EXPRESSIONS), "right")
        expr = {name: [ex[0][i], ex[1][i]] for i, name in enumerate(EXPRESSIONS)}
        total = sum(n for _, n in POSES)
        side = _head_anchor(base_walk, FRAME_W, FRAME_H, "right")
        anchors = []
        for name, n in POSES:                   # 頭在每個動作裡的位置（帽子、圍巾跟著頭走）
            dx, dy = POSE_HEAD[name]
            anchors += [(side[0] + dx, side[1] + dy)] * n
        po = both("base_pose.png", POSE_GROUPS, total, "right", anchors)
        pose, i = {}, 0
        for name, n in POSES:
            pose[name] = [po[0][i:i + n], po[1][i:i + n]]
            i += n
        _cache[key] = {"walk": walk, "sleep": sleep, "expr": expr, "pose": pose}
    return _cache[key]


def face(color, kind="face", scale=1.0):
    """正面貓臉 face(16x14)、探頭小臉 peek(10x8)、肉球 paw(6x5)。"""
    key = ("face", _sp_key(color), kind, scale)
    if key not in _cache:
        x, w, h = {"face": (0, 16, 14), "peek": (16, 10, 8), "paw": (26, 6, 5)}[kind]
        img = _recolor(_image("base_face.png"), spec(color), FACE_GROUPS).copy(x, 0, w, h)
        _cache[key] = _scaled(img, scale)
    return _cache[key]


def preview_image(sp, scale, front=False):
    """調色盤預覽：直接用一組顏色畫出側面站姿（front=True 時旁邊再加一隻正面，看得到兩隻眼睛）。"""
    walk = _recolor(_image("base_walk.png"), sp, WALK_GROUPS)
    side = walk.copy(FRAME_W, FRAME_H, FRAME_W, FRAME_H)
    if not front:
        return _scaled(side, scale)
    from PySide6.QtGui import QPainter
    both = QImage(FRAME_W * 2, FRAME_H, QImage.Format_ARGB32)
    both.fill(0)
    p = QPainter(both)
    p.drawImage(0, 0, walk.copy(FRAME_W, FRAME_H * 2, FRAME_W, FRAME_H))
    p.drawImage(FRAME_W, 0, side)
    p.end()
    return _scaled(both, scale)


# ---------------- 特效 / 貓屋 ---------------- #
def effect(kind, scale):
    key = ("fx", kind, scale)
    if key not in _cache:
        x, y, w, h = EFFECTS[kind]
        _cache[key] = _scaled(_image("effects.png").copy(QRect(x, y, w, h)), scale)
    return _cache[key]


def house(scale, closed=False):
    """貓屋：第一格門窗打開（有貓咪在家），第二格門窗關著。"""
    key = ("house", scale, closed)
    if key not in _cache:
        img = _image("house.png")
        _cache[key] = _scaled(img.copy(HOUSE_W if closed else 0, 0, HOUSE_W, HOUSE_H), scale)
    return _cache[key]
