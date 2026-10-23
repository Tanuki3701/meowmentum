"""載入精靈圖並預先放大、快取（每張圖只處理一次）。"""
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPixmap, QTransform

FRAME_W, FRAME_H = 32, 48
FRAMES_PER_DIR = 3
FOOT_GAP = 5  # 腳下方的透明像素列數（原圖第 43~47 列是空的）

# effects.png 裡每個特效的實際範圍 (x, y, w, h)
EFFECTS = {"heart": (0, 0, 7, 6), "zzz": (32, 0, 5, 5), "can": (64, 0, 10, 8)}

_cache = {}


def resource_path(*parts):
    """同時支援直接執行原始碼與 PyInstaller 打包後的 .app。"""
    base = getattr(sys, "_MEIPASS", None) or os.path.join(os.path.dirname(__file__), "..")
    return os.path.join(base, *parts)


def _dpr():
    return max((s.devicePixelRatio() for s in QGuiApplication.screens()), default=1.0)


def _load(name):
    path = resource_path("assets", "sprites", name)
    pm = QPixmap(path)
    if pm.isNull():
        raise FileNotFoundError(f"找不到圖檔: {path}")
    return pm


def _scaled(pm, scale):
    dpr = _dpr()
    out = pm.scaled(round(pm.width() * scale * dpr), round(pm.height() * scale * dpr),
                    Qt.IgnoreAspectRatio, Qt.FastTransformation)
    out.setDevicePixelRatio(dpr)
    return out


def cat_frames(color, scale):
    """回傳 dict：walk[方向][格]、sleep[0=面右/1=面左][格]。"""
    key = ("cat", color, scale)
    if key not in _cache:
        sheet = _load(f"cat_{color}-32x48.png")
        walk = [[_scaled(sheet.copy(f * FRAME_W, d * FRAME_H, FRAME_W, FRAME_H), scale)
                 for f in range(FRAMES_PER_DIR)] for d in range(4)]
        sleep_sheet = _load(f"cat_{color}-sleep.png")
        right = [sleep_sheet.copy(f * FRAME_W, 0, FRAME_W, FRAME_H) for f in range(2)]
        mirror = QTransform().scale(-1, 1)
        left = [pm.transformed(mirror) for pm in right]
        sleep = [[_scaled(pm, scale) for pm in right], [_scaled(pm, scale) for pm in left]]
        _cache[key] = {"walk": walk, "sleep": sleep}
    return _cache[key]


def effect(kind, scale):
    key = ("fx", kind, scale)
    if key not in _cache:
        x, y, w, h = EFFECTS[kind]
        _cache[key] = _scaled(_load("effects.png").copy(x, y, w, h), scale)
    return _cache[key]
