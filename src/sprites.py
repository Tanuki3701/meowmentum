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


def derive_spec(fur, eye=None):
    """從一個毛色（和眼睛顏色）推出整組像素調色盤。"""
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


def _recolor(img, sp):
    out = QImage(img)            # 複製一份，換掉調色盤
    table = [0]
    for ch in SEM[1:]:
        rgb = (255, 255, 255) if ch == "W" else sp[ch]
        table.append(QColor(*rgb).rgba())
    table += [0] * (out.colorCount() - len(table))
    out.setColorTable(table)
    return out


def _scaled(img, scale):
    dpr = _dpr()
    pm = QPixmap.fromImage(img.scaled(round(img.width() * scale * dpr), round(img.height() * scale * dpr),
                                      Qt.IgnoreAspectRatio, Qt.FastTransformation))
    pm.setDevicePixelRatio(dpr)
    return pm


def _sp_key(color):
    return tuple(sorted(spec(color).items()))


# ---------------- 貓咪 ---------------- #
def cat_frames(color, scale):
    """回傳 dict：walk[方向][格]、sleep[0=面右/1=面左][格]、expr[名稱][0=右/1=左]。"""
    key = ("cat", _sp_key(color), scale)
    if key not in _cache:
        sp = spec(color)
        walk_img = _recolor(_image("base_walk.png"), sp)
        walk = [[_scaled(walk_img.copy(f * FRAME_W, d * FRAME_H, FRAME_W, FRAME_H), scale)
                 for f in range(FRAMES_PER_DIR)] for d in range(4)]
        mirror = QTransform().scale(-1, 1)

        def both(img, n):
            right = [img.copy(i * FRAME_W, 0, FRAME_W, FRAME_H) for i in range(n)]
            return [[_scaled(x, scale) for x in right],
                    [_scaled(x.transformed(mirror), scale) for x in right]]

        sleep = both(_recolor(_image("base_sleep.png"), sp), 2)
        ex = both(_recolor(_image("base_expr.png"), sp), len(EXPRESSIONS))
        expr = {name: [ex[0][i], ex[1][i]] for i, name in enumerate(EXPRESSIONS)}
        _cache[key] = {"walk": walk, "sleep": sleep, "expr": expr}
    return _cache[key]


def face(color, kind="face", scale=1.0):
    """正面貓臉 face(16x14)、探頭小臉 peek(10x8)、肉球 paw(6x5)。"""
    key = ("face", _sp_key(color), kind, scale)
    if key not in _cache:
        x, w, h = {"face": (0, 16, 14), "peek": (16, 10, 8), "paw": (26, 6, 5)}[kind]
        img = _recolor(_image("base_face.png"), spec(color)).copy(x, 0, w, h)
        _cache[key] = _scaled(img, scale)
    return _cache[key]


def preview_image(sp, scale):
    """調色盤預覽：直接用一組顏色畫出側面站姿。"""
    img = _recolor(_image("base_walk.png"), sp).copy(FRAME_W, FRAME_H, FRAME_W, FRAME_H)
    return _scaled(img, scale)


# ---------------- 特效 / 貓屋 ---------------- #
def effect(kind, scale):
    key = ("fx", kind, scale)
    if key not in _cache:
        x, y, w, h = EFFECTS[kind]
        _cache[key] = _scaled(_image("effects.png").copy(QRect(x, y, w, h)), scale)
    return _cache[key]


def house(scale):
    key = ("house", scale)
    if key not in _cache:
        _cache[key] = _scaled(_image("house.png"), scale)
    return _cache[key]
