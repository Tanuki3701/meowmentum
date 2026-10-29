"""產生 README 用的動圖（每一項功能都有一張）。

執行：QT_QPA_PLATFORM="offscreen:configfile=screens.json" QT_SCALE_FACTOR=2 python3 tools/make_gifs.py [名稱...]
有文字的動圖會各做一張英文 (-en) 和繁體中文 (-zh)。
"""
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import make_screenshots as ms  # noqa: E402  (建立 app、controller 和共用的小工具)
from make_screenshots import (DPR, ROOT, ctrl, desktop, fake_window, glass_paste, paste,  # noqa: E402
                              reset, to_pil)
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402


PURGE = {"on": False}


def flush():
    """處理完畫面更新；PURGE 開著時也把 deleteLater 的舊元件真的刪掉（商店重畫時才不會疊在一起）。"""
    for _ in range(4):
        ms.app.processEvents()
        if PURGE["on"]:
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    ms.app.processEvents()


ms.flush = flush
from PySide6.QtCore import QPoint  # noqa: E402

import art  # noqa: E402
import glassmenu  # noqa: E402
import i18n  # noqa: E402
import interior  # noqa: E402
import pixel  # noqa: E402
import seasons  # noqa: E402
import sprites  # noqa: E402
from i18n import tr  # noqa: E402

S = int(DPR)
OUT = ms.OUT
cat = ctrl.main_cat
SC = 3                                    # 貓咪大小
FOOT = sprites.FOOT_GAP * SC
CW, CH = sprites.FRAME_W * SC, sprites.FRAME_H * SC
INK = (58, 55, 55)
FONT = ImageFont.truetype(os.path.join(ROOT, "assets", "fonts", "fusion-pixel.ttf"), 12 * S)
BIG = ImageFont.truetype(os.path.join(ROOT, "assets", "fonts", "fusion-pixel.ttf"), 16 * S)


# ---------------- 存檔 ---------------- #
def _palette(rgb):
    """一組給整張動圖用的調色盤：背景漸層一半，前景（貓咪、對話框、選單）的顏色一半。

    像素圖的顏色很少，盡量原色保留，小東西（紅綠燈、眼睛）的顏色才不會跑掉。
    """
    from PIL import ImageChops
    base = rgb[0]
    step = max(1, len(rgb) // 16)
    samples = rgb[::step][:18]
    fg = []
    for f in samples:
        diff = ImageChops.difference(f, base).convert("L").point(lambda v: 255 if v > 0 else 0)
        if f is base:
            continue
        fg.append(Image.composite(f, Image.new("RGB", f.size, (0, 0, 0)), diff).getdata())
    counts = {}
    for f, data in zip(samples[1:], fg):
        for px in data:
            if px != (0, 0, 0):
                counts[px] = counts.get(px, 0) + 1
    # 前景顏色：出現夠多次的原色優先（像素圖的色塊），剩下的再交給 median cut
    common = sorted(counts.items(), key=lambda kv: -kv[1])
    exact = [c for c, n in common if n >= 40][:110]
    fg_n = 128
    pal = list(exact)
    if len(pal) < fg_n and counts:
        rest = Image.new("RGB", (len(common), 1))
        rest.putdata([c for c, _ in common])
        q = rest.quantize(colors=fg_n - len(pal), method=Image.Quantize.MEDIANCUT).getpalette()
        for i in range(fg_n - len(pal)):
            c = tuple(q[i * 3:i * 3 + 3])
            if c not in pal:
                pal.append(c)
    bg = base.quantize(colors=255 - len(pal), method=Image.Quantize.MEDIANCUT).getpalette()
    for i in range(255 - len(pal)):
        pal.append(tuple(bg[i * 3:i * 3 + 3]))
    pal = pal[:256]
    flat = [v for c in pal for v in c] + [0] * (768 - len(pal) * 3)
    pimg = Image.new("P", (1, 1))
    pimg.putpalette(flat)
    return pimg


def save_gif(frames, name, ms_=90, durations=None):
    rgb = [f.convert("RGB") for f in frames]
    pal = _palette(rgb)
    out = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in rgb]
    path = os.path.join(OUT, name)
    out[0].save(path, save_all=True, append_images=out[1:], duration=durations or ms_,
                loop=0, optimize=True, disposal=1)
    print("saved", name, len(frames), "frames", os.path.getsize(path) // 1024, "KB", flush=True)


# ---------------- 小工具 ---------------- #
def frames_of(color, hat=None, neck=None, scale=SC):
    return sprites.cat_frames(color, scale, hat, neck)


def pm_alpha(pm, a):
    im = to_pil(pm) if not isinstance(pm, Image.Image) else pm.copy()
    if a < 1:
        r, g, b, al = im.split()
        al = al.point(lambda v: int(v * a))
        im = Image.merge("RGBA", (r, g, b, al))
    return im


def put(img, pm, x, y, a=1.0):
    paste(img, pm_alpha(pm, a) if a < 1 else pm, x, y)


def walk_pm(color, d, t, hat=None, neck=None, every=2):
    """走路的那一格：每 every 張動圖換一次腳。"""
    return frames_of(color, hat, neck)["walk"][d][(t // every) % 3]


def stand_pm(color, d=2, hat=None, neck=None):
    return frames_of(color, hat, neck)["walk"][d][1]


def sleep_pm(color, side=0, t=0):
    return frames_of(color)["sleep"][side][(t // 8) % 2]


def expr_pm(color, name, side=0, hat=None, neck=None):
    return frames_of(color, hat, neck)["expr"][name][side]


def ground_y(H, pad=8):
    """貓咪站在畫面底部時，貓咪圖的 y。"""
    return H - pad - CH + FOOT


class Fx:
    """跟 overlay 一樣的小特效（愛心、Zzz、星星…），自己一格一格推進。"""

    def __init__(self):
        self.items = []

    def add(self, kind, x, y, life=9):
        self.items.append([kind, x, y, life])

    def burst(self, kind, x, y, n=3, rnd=random.Random(1)):
        for _ in range(n):
            self.add(kind, x + rnd.uniform(-30, 30), y - rnd.uniform(0, 10), rnd.randint(7, 10))

    def step(self, n=3):
        k = 33 / 140
        for _ in range(n):
            for fx in self.items:
                fx[2] -= (6 if fx[0] == "heart" else 5) * k
                if fx[0] == "zzz":
                    fx[1] += 3 * k
                fx[3] -= k
            self.items = [f for f in self.items if f[3] > 0]

    def draw(self, img, scale=2, lift=0):
        """lift：上面有對話泡泡時，特效往上移到泡泡上方（和 app 一樣）。"""
        for kind, x, y, life in self.items:
            y -= lift
            pm = sprites.effect(kind, scale)
            a = min(1.0, life / 3)
            w = pm.width() / pm.devicePixelRatio()
            h = pm.height() / pm.devicePixelRatio()
            put(img, pm, x - w / 2, y - h, a)


def bubble(img, cx, cat_y, text=None, label=None, sleeping=False):
    """貓咪頭上的對話泡泡（用 app 裡同一個 overlay 畫出來）。"""
    ov = cat.overlay
    ov.text, ov.label, ov.effects, ov.tag = text, label, [], None
    ov.show()
    ov.update()
    flush()
    pm = ov.grab()
    ov.hide()
    ov.text = ov.label = None
    top = cat_y + (29 if sleeping else 20) * SC
    paste(img, pm, cx - ov.W / 2, top - ov.H + 4)
    ov.text, ov.label = text, label
    box, _rows = ov._layout()
    ov.text = ov.label = None
    return box.height() + 8 if box else 0


def cursor(img, x, y, click=0.0):
    """macOS 的箭頭游標；click > 0 時畫一圈點擊的漣漪。"""
    d = ImageDraw.Draw(img)
    if click > 0:
        r = (6 + 14 * click) * S
        a = int(160 * (1 - click))
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).ellipse([x * S - r, y * S - r, x * S + r, y * S + r],
                                      outline=(80, 120, 230, a), width=2 * S)
        img.alpha_composite(layer)
    pts = [(0, 0), (0, 17), (4, 13), (7, 19.5), (9.5, 18.5), (6.6, 12.4), (12, 12.4)]
    poly = [((x + px) * S, (y + py) * S) for px, py in pts]
    d.polygon(poly, fill=(20, 20, 20))
    inner = [(0.9, 2.3), (0.9, 14.9), (4.3, 11.5), (7.4, 17.9), (8.4, 17.5), (5.3, 11.2), (9.8, 11.2)]
    d.polygon([((x + px) * S, (y + py) * S) for px, py in inner], fill=(255, 255, 255))


def chip(img, text, x, y, anchor="tl", big=False, fill=(255, 250, 236), alpha=1.0):
    """像素風的小標籤（說明現在示範的是什麼）。"""
    font = BIG if big else FONT
    d = ImageDraw.Draw(img)
    tw = d.textlength(text, font=font)
    pad = 8 * S
    w, h = int(tw + pad * 2), int((26 if big else 22) * S)
    x0, y0 = int(x * S), int(y * S)
    if anchor == "tc":
        x0 -= w // 2
    elif anchor == "tr":
        x0 -= w
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    a = int(255 * alpha)
    u = 2 * S
    ld.rectangle([x0 + u, y0 + h, x0 + w + u - 1, y0 + h + u - 1], fill=(0, 0, 0, int(40 * alpha)))
    ld.rectangle([x0 + w, y0 + u, x0 + w + u - 1, y0 + h + u - 1], fill=(0, 0, 0, int(40 * alpha)))
    ld.rectangle([x0, y0 + u, x0 + w - 1, y0 + h - u - 1], fill=INK + (a,))
    ld.rectangle([x0 + u, y0, x0 + w - u - 1, y0 + h - 1], fill=INK + (a,))
    ld.rectangle([x0 + u, y0 + u, x0 + w - u - 1, y0 + h - u - 1], fill=fill + (a,))
    ld.text((x0 + pad, y0 + (h - font.size) // 2 - S), text, font=font, fill=INK + (a,))
    img.alpha_composite(layer)
    return w / S


def menubar(img, battery=None, low_power=False, tray_hl=False):
    """畫面最上方的選單列：小貓圖示（可以亮起來）、電池。"""
    W = img.width // S
    bar = Image.new("RGBA", (img.width, 26 * S), (246, 246, 248, 215))
    img.alpha_composite(bar, (0, 0))
    tx = W - 150
    if tray_hl:
        hl = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(hl).rounded_rectangle([(tx - 4) * S, 3 * S, (tx + 22) * S, 23 * S], 5 * S, fill=(0, 0, 0, 38))
        img.alpha_composite(hl)
    tray = Image.open(os.path.join(ROOT, "assets", "tray.png")).convert("RGBA").resize((18 * S, 18 * S),
                                                                                      Image.NEAREST)
    img.alpha_composite(tray, (tx * S, 4 * S))
    if battery is not None:
        level, charging = battery
        bx, by = W - 70, 8
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([bx * S, by * S, (bx + 24) * S, (by + 11) * S], 3 * S, outline=(40, 40, 40), width=S)
        d.rectangle([(bx + 25) * S, (by + 3) * S, (bx + 26) * S, (by + 8) * S], fill=(40, 40, 40))
        col = (255, 204, 0) if low_power else ((230, 60, 50) if level < 0.21 and not charging else (40, 40, 40))
        if charging:
            col = (52, 199, 89)
        d.rounded_rectangle([(bx + 2) * S, (by + 2) * S, (bx + 2 + max(1, 20 * level)) * S, (by + 9) * S],
                            1 * S, fill=col)
        if charging:
            bolt = [(bx + 13, by + 1), (bx + 9, by + 6), (bx + 12, by + 6), (bx + 11, by + 10), (bx + 15, by + 5),
                    (bx + 12, by + 5)]
            d.polygon([(px * S, py * S) for px, py in bolt], fill=(255, 255, 255))
        d.text(((bx - 34) * S, (by - 2) * S), f"{int(level * 100)}%", font=FONT, fill=(40, 40, 40))
    return tx


def dock(img, y, x0, x1):
    """示意的 Dock：半透明的長條和幾個彩色的 App 圖示。"""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([x0 * S, y * S, x1 * S, (y + 56) * S], 16 * S, fill=(255, 255, 255, 120),
                        outline=(255, 255, 255, 170), width=S)
    cols = [(90, 160, 250), (250, 120, 90), (110, 200, 120), (250, 200, 80), (190, 120, 230), (240, 110, 160),
            (90, 200, 210), (150, 150, 160)]
    n = int((x1 - x0 - 16) // 52)
    for i in range(n):
        ix = x0 + 12 + i * 52
        d.rounded_rectangle([ix * S, (y + 7) * S, (ix + 42) * S, (y + 49) * S], 10 * S, fill=cols[i % len(cols)] + (255,))
        d.rounded_rectangle([(ix + 10) * S, (y + 17) * S, (ix + 32) * S, (y + 39) * S], 5 * S,
                            fill=(255, 255, 255, 110))
    img.alpha_composite(layer)


def grab_menu(build, active=None):
    menu = glassmenu.GlassMenu()
    build(menu)
    menu.popup(QPoint(0, 0))
    flush()
    if active is not None:
        acts = [a for a in menu.actions() if not a.isSeparator()]
        menu.setActiveAction(acts[active])
        flush()
    im = to_pil(menu.grab())
    return menu, im


def ease(t):
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


CAP = {                                   # 只在動圖上用的說明文字
    "phase_morning": {"en": "Morning  6-11", "zh": "早上 6-11 點"},
    "phase_day": {"en": "Day  11-17", "zh": "白天 11-17 點"},
    "phase_dusk": {"en": "Dusk  17-19", "zh": "傍晚 17-19 點"},
    "phase_night": {"en": "Night  19-6", "zh": "晚上 19-6 點"},
    "phase_late": {"en": "Late at night", "zh": "深夜"},
    "deco_halloween": {"en": "Halloween", "zh": "萬聖節"},
    "deco_xmas": {"en": "Christmas and winter snow", "zh": "聖誕節和冬天的積雪"},
    "deco_lny": {"en": "Lunar New Year", "zh": "農曆新年"},
    "deco_spring": {"en": "Spring petals", "zh": "春天的花瓣"},
    "lowpower_on": {"en": "Low Power Mode is on", "zh": "低耗電模式開啟中"},
}


def cap(key):
    return CAP[key][i18n.lang()]


def langs(fn):
    """有文字的動圖：英文、中文各做一張。"""
    fn.multi = True
    return fn


GIFS = {}


def gif(name, multi=False):
    def deco(fn):
        GIFS[name] = (fn, multi)
        return fn
    return deco


def out_name(name, lang, multi):
    return f"{name}-{lang}.gif" if multi else f"{name}.gif"


# =====================================================================
# 陪伴
# =====================================================================
@gif("modes", multi=True)
def g_modes(lang):
    W, H = 640, 300
    base = desktop(W, H, seed=61)
    frames = []
    g = ground_y(H)
    names = ["mode_idle", "mode_random", "mode_follow", "mode_windows", "mode_dock", "mode_sleep"]
    n = 20
    win = base.copy()
    fake_window(win, 300, 120, 300, 170)
    dk = base.copy()
    dock(dk, H - 64, 120, 560)
    fx = Fx()
    for mi, key in enumerate(names):
        for t in range(n):
            if key == "mode_windows":
                img = win.copy()
            elif key == "mode_dock":
                img = dk.copy()
            else:
                img = base.copy()
            if key == "mode_idle":
                d = [2, 2, 1, 1, 2, 2, 3, 3, 2, 2][t // 2]
                put(img, stand_pm("brown", d), 300, g)
            elif key == "mode_random":
                x = 140 + t * 9 if t < 13 else 140 + 12 * 9 - (t - 12) * 9
                put(img, walk_pm("brown", 1 if t < 13 else 3, t), x, g)
            elif key == "mode_follow":
                cx_, cy_ = 220 + t * 14, 150 + 50 * math.sin(t / 3)
                catx = 120 + t * 12.5
                put(img, walk_pm("brown", 1, t), catx, g)
                cursor(img, cx_, cy_)
            elif key == "mode_windows":
                put(img, walk_pm("brown", 1, t), 320 + t * 9, 120 - (CH - FOOT))
            elif key == "mode_dock":
                put(img, walk_pm("brown", 3, t), 480 - t * 11, H - 64 - (CH - FOOT))
            else:
                if t % 6 == 0:
                    fx.add("zzz", 300 + CW / 2 + 22, g + 29 * SC - 6)
                put(img, sleep_pm("brown", 0, t), 300, g)
                fx.step()
                fx.draw(img)
            chip(img, tr(key), 16, 14, big=True)
            dots = "".join("●" if i == mi else "○" for i in range(len(names)))
            ImageDraw.Draw(img).text(((W - 90) * S, 18 * S), dots, font=FONT, fill=INK)
            frames.append(img)
    save_gif(frames, out_name("modes", lang, True), 110)


@gif("windows")
def g_windows(lang):
    """在視窗上散步、拖視窗時跟著走、視窗關掉就掉下來。"""
    W, H = 640, 340
    base = desktop(W, H, seed=11)
    frames = []
    g = ground_y(H)
    wx, wy, ww, wh = 120, 150, 320, 160
    x = wx + 40
    for t in range(70):
        img = base.copy()
        a = 1.0
        if t < 24:                                     # 在標題列上散步
            pass
        elif t < 44:                                   # 游標拖著視窗往右上
            k = ease((t - 24) / 19)
            wx, wy = lerp(120, 250, k), lerp(150, 110, k)
        if t >= 50:                                    # 視窗關掉
            a = max(0.0, 1 - (t - 50) / 4)
        if a > 0:
            layer = base.copy()
            fake_window(layer, wx, wy, ww, wh)
            img = Image.blend(base, layer, a) if a < 1 else layer
        if t < 24:
            x = wx + 40 + t * 7
            put(img, walk_pm("orange", 1, t), x, wy - (CH - FOOT))
        elif t < 50:
            off = x - 120 - 0
            put(img, stand_pm("orange", 2), wx + (off if t < 44 else off), wy - (CH - FOOT))
            if t < 46:
                cursor(img, wx + 200, wy + 12, click=0.3 if t < 26 else 0)
        else:
            px = wx + (x - 120)
            fall = min(1.0, (t - 52) / 7) if t >= 52 else 0
            y = lerp(wy - (CH - FOOT), g, fall * fall)
            pm = expr_pm("orange", "excited", 0) if 52 <= t < 60 else stand_pm("orange", 2)
            put(img, pm, px, y)
        frames.append(img)
    save_gif(frames, out_name("windows", lang, False), 90)


@gif("naps")
def g_naps(lang):
    """一段時間沒碰電腦就睡著；睡覺模式下點一下只會摸摸頭。"""
    W, H = 560, 260
    base = desktop(W, H, seed=9)
    g = ground_y(H)
    fx = Fx()
    frames = []
    cx = 240
    for t in range(64):
        img = base.copy()
        if t < 10:
            put(img, stand_pm("black", 2), cx, g)
        elif t < 14:
            put(img, expr_pm("black", "happy", 0), cx, g)
        else:
            if t % 7 == 0:
                fx.add("zzz", cx + CW / 2 + 22, g + 29 * SC - 6)
            put(img, sleep_pm("black", 0, t), cx, g)
        if 40 <= t < 56:
            k = ease(min(1.0, (t - 40) / 6))
            mx, my = lerp(470, cx + CW / 2, k), lerp(70, g + 34 * SC, k)
            if t == 47:
                fx.burst("heart", cx + CW / 2, g + 30 * SC, 3)
            cursor(img, mx, my, click=(t - 47) / 4 if 47 <= t < 51 else 0)
        fx.step()
        fx.draw(img)
        frames.append(img)
    save_gif(frames, out_name("naps", lang, False), 100)


@gif("petting", multi=True)
def g_petting(lang):
    W, H = 600, 300
    base = desktop(W, H, seed=71)
    g = ground_y(H)
    fx = Fx()
    frames = []
    cx = 220
    say = tr("say_pet")[0]
    grr = tr("say_annoyed")[0]
    for t in range(76):
        img = base.copy()
        if t < 34:                                    # 來回摸
            pm = expr_pm("orange", "happy", 0) if t > 8 else stand_pm("orange", 2)
            put(img, pm, cx, g)
            lift = bubble(img, cx + CW / 2, g, say) if t > 8 else 0
            if t % 6 == 3:
                fx.burst("heart", cx + CW / 2, g + 24 * SC, 2)
            mx = cx + CW / 2 - 26 + 52 * (0.5 + 0.5 * math.sin(t / 2.2))
            fx.step()
            fx.draw(img, lift=lift)
            cursor(img, mx, g + 34 * SC)
        elif t < 56:                                  # 連續戳五下
            k = t - 34
            pm = expr_pm("orange", "yuck", 0) if k >= 14 else stand_pm("orange", 2)
            put(img, pm, cx, g)
            if k >= 14:
                bubble(img, cx + CW / 2, g, grr)
            click = (k % 3) / 3 if k < 15 else 0
            fx.step()
            fx.draw(img)
            cursor(img, cx + CW / 2 + 4, g + 32 * SC, click=click)
        else:                                         # 不耐煩地走開
            k = t - 56
            put(img, walk_pm("orange", 1, k), cx + k * 12, g)
            if k < 8:
                bubble(img, cx + k * 12 + CW / 2, g, grr)
            cursor(img, cx + CW / 2 + 4, g + 32 * SC)
        frames.append(img)
    save_gif(frames, out_name("petting", lang, True), 100)


@gif("flavors", multi=True)
def g_flavors(lang):
    W, H = 620, 320
    base = desktop(W, H, seed=17)
    g = ground_y(H)
    plan = [("tuna", "orange", "happy", "heart", "react_tuna"),
            ("chicken", "white", "happy", "note", "react_chicken"),
            ("salmon", "brown", "excited", "sparkle", "react_salmon"),
            ("catnip", "black", "dizzy", "sparkle", "react_dizzy"),
            ("bitter", "orange", "yuck", "sweat", "react_bitter")]
    frames = []
    for flavor, color, ex, efx, text in plan:
        fx = Fx()
        can = sprites.effect("can_" + flavor, 3)
        canw = can.width() / can.devicePixelRatio()
        canh = can.height() / can.devicePixelRatio()
        target = 400
        for t in range(30):
            img = base.copy()
            chip(img, tr("flavor_" + flavor), 16, 14, big=True)
            cy = min(H - 8 - canh, -canh + t * 38)
            landed = cy >= H - 8 - canh
            catx = 120 + min(t, 14) * ((target - CW + 10 - 120) / 14)
            if t < 16:
                put(img, can, target, cy)
                put(img, walk_pm(color, 1, t), catx, g)
            else:
                k = t - 16
                if k == 0:
                    fx.burst(efx, catx + CW / 2, g + 22 * SC, 3)
                if k == 6:
                    fx.burst(efx, catx + CW / 2, g + 22 * SC, 2)
                jump = -math.sin(min(1, k / 6) * math.pi) * 26 if ex == "excited" else 0
                put(img, expr_pm(color, ex, 0), catx, g + jump)
                lift = bubble(img, catx + CW / 2, g + jump, tr(text))
            fx.step()
            fx.draw(img, lift=lift if t >= 16 else 0)
            del landed
            frames.append(img)
    save_gif(frames, out_name("flavors", lang, True), 100)


@gif("toys")
def g_toys(lang):
    W, H = 660, 300
    base = desktop(W, H, seed=53)
    g = ground_y(H)
    frames = []
    cats_ = [("white", 60), ("black", 140), ("orange", 520)]
    pos = [x for _, x in cats_]
    pounce = [0, 0, 0]
    for t in range(70):
        img = base.copy()
        wx = 330 + 200 * math.sin(t / 9)
        wy = 150 + 30 * math.sin(t / 4)
        tip = wx + 22
        for i, (color, _) in enumerate(cats_):
            dx = tip - (pos[i] + CW / 2) + (i - 1) * 40
            if pounce[i] > 0:
                k = 1 - pounce[i] / 7
                put(img, frames_of(color)["walk"][1 if dx > 0 else 3][0], pos[i], g - math.sin(k * math.pi) * 40)
                pounce[i] -= 1
                pos[i] += 4 if dx > 0 else -4
            elif abs(dx) > 30:
                step = max(-9, min(9, dx * 0.2))
                pos[i] += step
                put(img, walk_pm(color, 1 if step > 0 else 3, t + i), pos[i], g)
            else:
                put(img, expr_pm(color, "excited", 0 if dx > 0 else 1), pos[i], g)
                if (t + i * 5) % 14 == 0:
                    pounce[i] = 7
        put(img, art.pix(art.WAND[(t // 4) % 2], 3), wx, wy)
        cursor(img, wx + 2, wy + 2)
        frames.append(img)
    save_gif(frames, out_name("toys", lang, False), 90)


@gif("friends", multi=True)
def g_friends(lang):
    W, H = 620, 300
    base = desktop(W, H, seed=73)
    g = ground_y(H)
    frames = []
    fx = Fx()
    chase, sniff = tr("say_chase")[0], tr("say_sniff")[0]
    for t in range(84):
        img = base.copy()
        lift = 0
        if t < 30:                                      # 追著跑
            a = 60 + t * 14
            b = a - 110
            put(img, walk_pm("white", 1, t), a, g)
            put(img, walk_pm("brown", 1, t + 1), b, g)
            bubble(img, b + CW / 2, g, chase)
        elif t < 54:                                    # 停下來聞聞
            k = t - 30
            put(img, frames_of("white")["walk"][3][1], 440, g)
            put(img, stand_pm("brown", 1), 360, g)
            if k > 3:
                lift = bubble(img, 360 + CW / 2, g, sniff)
            if k == 10:
                fx.burst("heart", 440 + CW / 2, g + 22 * SC, 3)
        else:                                           # 擠在一起睡
            if t % 8 == 0:
                fx.add("zzz", 400 + CW / 2 + 20, g + 29 * SC - 6)
            put(img, sleep_pm("brown", 0, t), 360, g)
            put(img, sleep_pm("white", 1, t + 3), 420, g)
        fx.step()
        fx.draw(img, lift=0 if t >= 54 else lift)
        frames.append(img)
    save_gif(frames, out_name("friends", lang, True), 100)


@gif("names", multi=True)
def g_names(lang):
    W, H = 600, 420
    base = desktop(W, H, seed=3)
    g = ground_y(H)
    frames = []
    reset(cat, "white", 2)
    cat.name = "Mochi" if lang == "en" else "麻糬"
    menu, mimg = grab_menu(lambda m: ctrl.build_menu(cat, m))
    menu.hide()
    cx = 80
    for t in range(52):
        img = base.copy()
        put(img, stand_pm("white", 2), cx, g)
        if t < 10:
            k = ease(t / 9)
            cursor(img, lerp(400, cx + CW / 2, k), lerp(120, g + 34 * SC, k))
        elif t < 38:
            glass_paste(img, mimg, cx + CW / 2 + 10, 30)
            cursor(img, cx + CW / 2, g + 34 * SC, click=(t - 10) / 3 if t < 13 else 0)
        else:
            put(img, expr_pm("white", "happy", 0), cx, g)
            bubble(img, cx + CW / 2, g, tr("say_named", n=cat.name))
        frames.append(img)
    cat.name = ""
    save_gif(frames, out_name("names", lang, True), 100)


@gif("gift", multi=True)
def g_gift(lang):
    W, H = 600, 300
    base = desktop(W, H, seed=79)
    g = ground_y(H)
    frames = []
    fx = Fx()
    kind = sorted(art.GIFTS)[0]
    gp = art.pix(art.GIFTS[kind], 2)
    gw = gp.width() / gp.devicePixelRatio()
    gh = gp.height() / gp.devicePixelRatio()
    cx = 200
    gx, gy = cx + CW + 4, H - 8 - gh
    for t in range(56):
        img = base.copy()
        if t < 34:
            put(img, stand_pm("orange", 2), cx, g)
            bubble(img, cx + CW / 2, g, tr("say_gift"))
            put(img, gp, gx, gy)
            if (t // 5) % 2 == 0:
                put(img, sprites.effect("sparkle", 2), gx + gw - 4, gy - 12)
            k = ease(min(1, max(0, (t - 14) / 12)))
            cursor(img, lerp(520, gx + gw / 2, k), lerp(80, gy + gh / 2, k), click=(t - 28) / 4 if t >= 28 else 0)
        else:
            if t == 34:
                fx.burst("sparkle", cx + CW / 2, g + 22 * SC, 3)
            put(img, expr_pm("orange", "happy", 0), cx, g)
            lift = bubble(img, cx + CW / 2, g, tr("say_gift_thanks", n=3))
            cursor(img, gx + gw / 2, gy + gh / 2)
        fx.step()
        fx.draw(img, lift=lift if t >= 34 else 0)
        frames.append(img)
    save_gif(frames, out_name("gift", lang, True), 100)


# =====================================================================
# 貓屋
# =====================================================================
def _house_frame(house):
    house._animate()
    house.update()
    flush()
    return house.grab()


def _prep_house(view="outside", seed=5):
    house = ctrl.house
    house.show()
    house.set_view(view, animate=False)
    house.setWindowOpacity(1.0)
    random.seed(seed)
    for i in range(30):
        if i % 10 == 0:
            house._puff()
        house._animate()
    return house


@gif("house")
def g_house(lang):
    """貓咪走到門口、門打開、走進去，接著從窗戶探出頭來。"""
    ms._freeze((2026, 6, 10), 14)
    W, H = 560, 320
    base = desktop(W, H, seed=19)
    house = _prep_house()
    hx, hy = W - house.width() - 40, H - house.height() - 6
    U = house.U
    door_x = hx + (8 + 28) * U - CW / 2
    g = hy + (18 + sprites.HOUSE_GROUND) * U - (CH - FOOT)
    others = []
    for color in ("white",):
        o = ctrl._spawn(ctrl.next_id, color)
        ctrl.next_id += 1
        others.append(o)
    frames = []
    for t in range(72):
        if t % 11 == 0:
            house._puff()
        if t % 18 == 4:
            house._gust()
        if 14 <= t < 22:
            house._door_until = time.monotonic() + 1
        if t == 22:
            house.residents.append(cat)
            house.state[cat] = {"slot": "left", "mode": "peek", "rise": 0}
        if t == 40:
            house.residents.append(others[0])
            house.state[others[0]] = {"slot": "door", "mode": "peek", "rise": 0}
        img = base.copy()
        cat.color = "orange"
        paste(img, _house_frame(house), hx, hy)
        if t < 14:
            put(img, walk_pm("orange", 1, t), 20 + t * ((door_x - 20) / 13), g)
        elif t < 22:
            put(img, frames_of("orange")["walk"][0][1], door_x, g, 1 - (t - 14) / 8)
        frames.append(img)
    house.gust.stop()
    house.anim.stop()
    for c in [cat] + others:
        if c in house.residents:
            house.residents.remove(c)
        house.state.pop(c, None)
    for o in others:
        ctrl.cats.remove(o)
        o.dispose()
    house.petals.clear()
    house.smoke.clear()
    house.hide()
    ms._unfreeze()
    save_gif(frames, out_name("house", lang, False), 90)


def _room_cats(house, specs):
    """房間裡的貓咪：[(color, hat, neck, x(房間座標), 動作)]。"""
    return [dict(color=c, hat=h, neck=n, x=x, kind=k, d=1, t0=i * 3) for i, (c, h, n, x, k) in enumerate(specs)]


def _draw_room_cats(img, house, ox, oy, cats_, t, fx):
    U = house.U
    floor = oy + (18 + interior.IG) * U - (CH - FOOT)
    for c in cats_:
        x = ox + (8 + c["x"]) * U - CW / 2
        if c["kind"] == "sleep":
            if (t + c["t0"]) % 9 == 0:
                fx.add("zzz", x + CW / 2 + 20, floor + 29 * SC - 6)
            put(img, frames_of(c["color"], c["hat"], c["neck"])["sleep"][0][((t + c["t0"]) // 8) % 2], x, floor)
        elif c["kind"] == "walk":
            lo, hi = c.get("lo", 26), c.get("hi", 60)
            span = (hi - lo) * 2
            ph = (t * 1.3 + c["t0"] * 4) % span
            ax, d = (lo + ph, 1) if ph < hi - lo else (hi - (ph - (hi - lo)), 3)
            x = ox + (8 + ax) * U - CW / 2
            put(img, frames_of(c["color"], c["hat"], c["neck"])["walk"][d][((t + c["t0"]) // 2) % 3], x, floor)
        elif c["kind"] == "eat":
            pm = frames_of(c["color"], c["hat"], c["neck"])["expr"]["happy"][1] if (t // 6) % 2 else \
                frames_of(c["color"], c["hat"], c["neck"])["walk"][3][1]
            put(img, pm, x, floor)
        else:
            put(img, frames_of(c["color"], c["hat"], c["neck"])["walk"][2][1], x, floor)


@gif("inside")
def g_inside(lang):
    """在貓屋上按兩下：原地變成娃娃屋剖面，貓咪在裡面走來走去、吃飯、睡覺。"""
    ms._freeze((2026, 6, 10), 15)
    W, H = 600, 360
    base = desktop(W, H, seed=27)
    pr = ctrl.progress
    pr.owned |= {"rug", "plant", "lamp", "painting", "fishtank", "yarn"}
    house = _prep_house("outside")
    hx_out, hy_out = (W - house.width()) // 2, H - house.height() - 6
    anchor_x = hx_out + house.width() / 2
    frames = []
    fx = Fx()
    cats_ = _room_cats(house, [("orange", "beanie", None, 0, "walk"), ("black", None, "scarf", 57, "eat"),
                               ("white", None, None, 78, "sleep")])
    cats_[0].update(lo=22, hi=42)
    for t in range(84):
        img = base.copy()
        if t % 10 == 0:
            house._puff()
        if t < 16:
            paste(img, _house_frame(house), hx_out, hy_out)
            k = ease(min(1, t / 10))
            cursor(img, lerp(560, anchor_x, k), lerp(60, hy_out + house.height() * 0.6, k),
                   click=((t - 11) % 3) / 3 if 11 <= t < 16 else 0)
            frames.append(img)
            continue
        if t == 16:
            house.set_view("inside", animate=False)
            house.setWindowOpacity(1.0)
        hx, hy = anchor_x - house.width() / 2, H - house.height() - 6
        a = min(1.0, (t - 16) / 4)
        layer = base.copy()
        paste(layer, _house_frame(house), hx, hy)
        _draw_room_cats(layer, house, hx, hy, cats_, t, fx)
        fx.step()
        fx.draw(layer)
        img = Image.blend(base, layer, a) if a < 1 else layer
        frames.append(img)
    house.anim.stop()
    house.smoke.clear()
    house.set_view("outside", animate=False)
    house.hide()
    ms._unfreeze()
    save_gif(frames, out_name("inside", lang, False), 90)


@gif("daynight", multi=True)
def g_daynight(lang):
    """早上、白天、傍晚、晚上：屋外的窗戶和屋裡的天空、燈光都跟著變，深夜貓咪會打哈欠。"""
    W, H = 760, 360
    base = desktop(W, H, seed=81)
    pr = ctrl.progress
    pr.owned |= {"rug", "plant", "lamp", "painting", "fishtank", "yarn"}
    house = ctrl.house
    house.show()
    frames = []
    phases = [("morning", 8, "phase_morning"), ("day", 14, "phase_day"), ("dusk", 18, "phase_dusk"),
              ("night", 22, "phase_night"), ("night", 1, "phase_late")]
    fx = Fx()
    for ph, hour, key in phases:
        ms._freeze((2026, 6, 10), hour)
        house.set_view("outside", animate=False)
        house.setWindowOpacity(1.0)
        out_pm = _house_frame(house)
        house.set_view("inside", animate=False)
        in_pm = _house_frame(house)
        hy_in = H - house.height() - 6
        cats_ = _room_cats(house, [("orange", None, None, 0, "walk"), ("white", None, None, 76, "sleep")])
        for t in range(22):
            img = base.copy()
            if t % 10 == 0:
                house._puff()
            house.set_view("outside", animate=False)
            out_pm = _house_frame(house)
            paste(img, out_pm, 20, H - house.height() - 6)
            house.set_view("inside", animate=False)
            in_pm = _house_frame(house)
            paste(img, in_pm, W - house.width() - 20, hy_in)
            if key == "phase_late":
                cats_[0]["kind"] = "stand"
                _draw_room_cats(img, house, W - house.width() - 20, hy_in, cats_[1:], t, fx)
                cx = 140
                g = ground_y(H)
                put(img, expr_pm("orange", "happy" if t % 10 < 5 else "excited", 0) if False else
                    stand_pm("orange", 2), cx + 190, g)
                bubble(img, cx + 190 + CW / 2, g, tr("say_late")[1])
            else:
                _draw_room_cats(img, house, W - house.width() - 20, hy_in, cats_, t, fx)
            fx.step()
            fx.draw(img)
            chip(img, cap(key), 16, 14, big=True)
            frames.append(img)
    ms._unfreeze()
    house.anim.stop()
    house.smoke.clear()
    house.set_view("outside", animate=False)
    house.hide()
    save_gif(frames, out_name("daynight", lang, True), 110)


@gif("seasons", multi=True)
def g_seasons(lang):
    W, H = 560, 320
    base = desktop(W, H, seed=47)
    house = _prep_house("outside")
    ctrl.seasonal = True
    frames = []
    shots = [((2026, 10, 29), 20, "deco_halloween"), ((2026, 12, 20), 21, "deco_xmas"),
             ((2027, 2, 6), 15, "deco_lny"), ((2026, 4, 2), 13, "deco_spring")]
    hx = (W - house.width()) // 2
    for date, hour, key in shots:
        ms._freeze(date, hour)
        house.petals.clear()
        for t in range(24):
            if t % 10 == 0:
                house._puff()
            if t % 8 == 1:
                house._gust()
            img = base.copy()
            paste(img, _house_frame(house), hx, H - house.height() - 6)
            chip(img, cap(key), 16, 14, big=True)
            frames.append(img)
    ms._unfreeze()
    house.gust.stop()
    house.anim.stop()
    house.petals.clear()
    house.smoke.clear()
    house.hide()
    save_gif(frames, out_name("seasons", lang, True), 110)


# =====================================================================
# 打扮你的貓
# =====================================================================
def _child_center(top, child):
    p = child.mapTo(top, QPoint(child.width() // 2, child.height() // 2))
    return p.x(), p.y()


@gif("palette", multi=True)
def g_palette(lang):
    W, H = 880, 720
    base = desktop(W, H, seed=23)
    frames = []
    reset(cat, "orange", 1)
    ctrl.open_palette(cat)
    pal = ctrl.palette
    pal._reset_look()
    pal._pick_fur((150, 150, 158))
    pal.name_edit.setText("Mochi" if lang == "en" else "麻糬")
    px, py = 300, 20
    # 每一步：(要點的按鈕, 動作)
    steps = [
        (lambda: pal.rows["fur"]["btns"][4], lambda: pal._pick_fur((110, 70, 50))),
        (lambda: pal.rows["fur"]["btns"][0], lambda: pal._pick_fur((150, 150, 158))),
        (lambda: pal.extra_btns["stripes"], lambda: pal._toggle_extra("stripes")),
        (lambda: pal.rows["stripes"]["btns"][6], lambda: pal._pick("stripes", pal.PATCHES[6])),
        (lambda: pal.extra_btns["white"], lambda: pal._toggle_extra("white")),
        (lambda: pal.base_btns["calico"], lambda: pal._pick_base("calico")),
        (lambda: pal.rows["eye"]["btns"][3], lambda: pal._pick_eye((80, 150, 230))),
        (lambda: pal.odd_btn, lambda: pal._toggle_odd()),
        (lambda: pal.rows["eye2"]["btns"][2], lambda: pal._pick("eye2", pal.EYES[2])),
    ]
    pal._refresh()
    flush()
    cur = (W - 40, H - 40)
    for btn_fn, act in steps:
        flush()
        target = _child_center(pal, btn_fn())
        tx, ty = px + target[0], py + target[1]
        dlg = to_pil(pal.grab())
        for t in range(8):
            img = base.copy()
            img.alpha_composite(dlg, (px * S, py * S))
            k = ease(t / 7)
            cursor(img, lerp(cur[0], tx, k), lerp(cur[1], ty, k))
            frames.append(img)
        act()
        flush()
        dlg = to_pil(pal.grab())
        for t in range(6):
            img = base.copy()
            img.alpha_composite(dlg, (px * S, py * S))
            cursor(img, tx, ty, click=t / 4 if t < 4 else 0)
            frames.append(img)
        cur = (tx, ty)
    for _ in range(14):
        frames.append(frames[-1])
    pal.hide()
    save_gif(frames, out_name("palette", lang, True), 90)


@gif("patterns", multi=True)
def g_patterns(lang):
    W, H = 780, 230
    base = desktop(W, H, seed=31)
    looks = [
        (dict(fur=(245, 245, 245), eye=(40, 140, 70), pattern="calico"), ["pat_calico"]),
        (dict(fur=(60, 52, 56), eye=(230, 190, 60), white=sprites.WHITE_DEFAULT), ["pat_white"]),
        (dict(fur=(150, 150, 158), eye=(60, 160, 80), stripes=(90, 90, 100)), ["pat_stripes"]),
        (dict(fur=(236, 170, 80), eye=(58, 55, 55), stripes=(186, 96, 46), white=sprites.WHITE_DEFAULT),
         ["pat_stripes", "pat_white"]),
        (dict(fur=(245, 245, 245), eye=(80, 150, 230), pattern="calico", stripes=(120, 90, 70)),
         ["pat_calico", "pat_stripes"]),
        (dict(fur=(245, 245, 245), eye=(80, 150, 230), eye2=(230, 190, 60)), ["odd_eyes"]),
    ]
    ids = []
    for lk, _ in looks:
        lk = dict(lk)
        fur, eye = lk.pop("fur"), lk.pop("eye")
        ids.append(ctrl.add_custom_color(fur, eye, "", **lk))
    frames = []
    gap = W / len(ids)
    for t in range(24):
        img = base.copy()
        for i, cid in enumerate(ids):
            d = [1, 2, 3, 2][(t // 6 + i) % 4]
            pm = walk_pm(cid, d, t + i) if d != 2 else stand_pm(cid, 2)
            x = gap * i + gap / 2 - CW / 2
            put(img, pm, x, H - 40 - CH + FOOT)
            label = " + ".join(tr(k) for k in looks[i][1])
            d_ = ImageDraw.Draw(img)
            tw = d_.textlength(label, font=FONT) / S
            d_.text(((gap * i + gap / 2 - tw / 2) * S, (H - 30) * S), label, font=FONT, fill=INK)
        frames.append(img)
    for cid in ids:
        ctrl.delete_custom_color(cid)
    save_gif(frames, out_name("patterns", lang, True), 150)


@gif("accessories")
def g_accessories(lang):
    W, H = 560, 240
    base = desktop(W, H, seed=83)
    g = ground_y(H)
    looks = [("party", None), ("crown", "bowtie"), ("beanie", "scarf"), ("flower", "collar"), ("witch", None),
             ("santa", "scarf")]
    ctrl.progress.owned |= {"party", "crown", "beanie", "flower", "bowtie", "scarf", "collar"}
    frames = []
    fx = Fx()
    for i, (hat, neck) in enumerate(looks):
        for t in range(10):
            img = base.copy()
            if t == 0:
                fx.burst("sparkle", 170 + CW / 2, g + 16 * SC, 2)
            put(img, stand_pm("white", 2, hat, neck), 170, g)
            put(img, walk_pm("brown", 1 if (i % 2 == 0) else 3, t + i * 10, looks[(i + 2) % 6][0],
                             looks[(i + 3) % 6][1]), 330, g)
            fx.step()
            fx.draw(img)
            frames.append(img)
    save_gif(frames, out_name("accessories", lang, False), 120)


@gif("furniture")
def g_furniture(lang):
    from toys import Spot
    W, H = 640, 320
    base = desktop(W, H, seed=53)
    g = ground_y(H)
    box = Spot(ctrl, "box")
    tree = Spot(ctrl, "tree")
    flush()
    bx, tx = 120, 400
    box_pm = to_pil(box.grab())
    tree_pm = to_pil(tree.grab())
    box.occupant = cat
    cat.color = "orange"
    flush()
    box_in = to_pil(box.grab())
    box.occupant = None
    top = H - 6 - tree.height() + (art.TREE_TOP - 2) * 3 - (CH - FOOT)
    frames = []
    for t in range(60):
        img = base.copy()
        # 紙箱：橘貓走過去鑽進去
        if t < 14:
            img.alpha_composite(box_pm, (bx * S, int((H - 6 - box.height()) * S)))
            put(img, walk_pm("orange", 1, t), 10 + t * ((bx + box.width() / 2 - CW / 2 - 10) / 13), g)
        else:
            img.alpha_composite(box_in, (bx * S, int((H - 6 - box.height()) * S)))
        # 貓跳台：黑貓跳上去坐好
        img.alpha_composite(tree_pm, (tx * S, int((H - 6 - tree.height()) * S)))
        sx = tx + tree.width() / 2 - CW / 2
        if t < 20:
            put(img, walk_pm("black", 3, t), W - 20 - t * ((W - 20 - (tx + tree.width())) / 19) - CW / 2, g)
        elif t < 30:
            k = (t - 20) / 9
            x = lerp(tx + tree.width() - CW / 2, sx, k)
            y = lerp(g, top, k) - math.sin(k * math.pi) * 40
            put(img, frames_of("black")["walk"][3][0], x, y)
        else:
            put(img, stand_pm("black", 2), sx, top)
        frames.append(img)
    box.dispose()
    tree.dispose()
    save_gif(frames, out_name("furniture", lang, False), 90)


@gif("cats")
def g_cats(lang):
    W, H = 700, 260
    base = desktop(W, H, seed=89)
    g = ground_y(H)
    cid = ctrl.add_custom_color((245, 245, 245), (40, 140, 70), "", "calico")
    cid2 = ctrl.add_custom_color((150, 150, 158), (60, 160, 80), "", stripes=(90, 90, 100),
                                 white=sprites.WHITE_DEFAULT)
    walkers = [("orange", 40, 1, 8, "party", None), ("white", 600, 3, 6, None, "scarf"),
               ("black", 300, 1, 5, None, "bowtie"), (cid, 460, 3, 7, "flower", None), (cid2, 160, 1, 6, None, None),
               ("brown", 520, 1, 4, "beanie", None)]
    frames = []
    for t in range(40):
        img = base.copy()
        for i, (color, x0, d, sp, hat, neck) in enumerate(walkers):
            span = W - CW
            x = (x0 + (t * sp if d == 1 else -t * sp)) % (span * 2)
            dd = d
            if x > span:
                x = span * 2 - x
                dd = 4 - d
            put(img, walk_pm(color, dd, t + i, hat, neck), x, g - (i % 2) * 18)
        frames.append(img)
    ctrl.delete_custom_color(cid)
    ctrl.delete_custom_color(cid2)
    save_gif(frames, out_name("cats", lang, False), 90)


# =====================================================================
# 實用
# =====================================================================
@gif("pomodoro", multi=True)
def g_pomodoro(lang):
    W, H = 600, 300
    base = desktop(W, H, seed=5)
    g = ground_y(H)
    frames = []
    total = 25 * 60
    n = 46
    for t in range(n):
        img = base.copy()
        prog = min(1.0, t / (n - 12))
        left = int(total * (1 - prog))
        if prog < 1:
            put(img, walk_pm("orange", 1 if (t // 12) % 2 == 0 else 3, t),
                120 + (t % 24 if (t // 12) % 2 == 0 else 24 - t % 24) * 8, g)
            bubble(img, 120 + (t % 24 if (t // 12) % 2 == 0 else 24 - t % 24) * 8 + CW / 2, g,
                   label=(pixel.tomato(prog, 2), "%02d:%02d" % (left // 60, left % 60)))
        else:
            put(img, expr_pm("orange", "happy", 0), W / 2 - CW / 2, g)
            bubble(img, W / 2, g, tr("say_focus_done", m=5), label=(pixel.tomato(1.0, 2), "00:00"))
        frames.append(img)
    save_gif(frames, out_name("pomodoro", lang, True), 120)


@gif("fish", multi=True)
def g_fish(lang):
    PURGE["on"] = True
    ms._freeze((2026, 10, 29))
    W, H = 760, 600
    base = desktop(W, H, seed=37)
    g = ground_y(H)
    pr = ctrl.progress
    pr.coins = 42
    pr.owned = {"collar", "box", "rug", "yarn"}
    reset(cat, "orange", 1)
    cat.hat = cat.neck = None
    fx = Fx()
    frames = []
    for t in range(14):
        img = base.copy()
        if t == 0:
            fx.burst("sparkle", 60 + CW / 2, g + 22 * SC, 3)
        put(img, expr_pm("orange", "happy", 0), 60, g)
        lift = bubble(img, 60 + CW / 2, g, tr("say_reward", n=5))
        fx.step()
        fx.draw(img, lift=lift)
        frames.append(img)
    ctrl.open_shop(cat)
    flush()
    shop = ctrl._shop
    sx, sy = 260, 20
    btn = next(b for b in shop.findChildren(type(ctrl.palette.save_btn)) if b.text() == tr("buy_n", n=25))
    bx, by = _child_center(shop, btn)
    before = to_pil(shop.grab())
    for t in range(12):
        img = base.copy()
        put(img, stand_pm("orange", 1), 60, g)
        img.alpha_composite(before, (sx * S, sy * S))
        k = ease(t / 11)
        cursor(img, lerp(200, sx + bx, k), lerp(H - 60, sy + by, k))
        frames.append(img)
    shop._buy("crown")
    flush()
    after = to_pil(shop.grab())
    for t in range(22):
        img = base.copy()
        if t == 0:
            fx.burst("heart", 60 + CW / 2, g + 22 * SC, 3)
        put(img, stand_pm("orange", 1, "crown"), 60, g)
        img.alpha_composite(after, (sx * S, sy * S))
        cursor(img, sx + bx, sy + by, click=t / 4 if t < 4 else 0)
        fx.step()
        fx.draw(img)
        frames.append(img)
    shop.hide()
    cat.set_hat(None)
    ms._unfreeze()
    PURGE["on"] = False
    save_gif(frames, out_name("fish", lang, True), 100)


@gif("stats", multi=True)
def g_stats(lang):
    W, H = 720, 420
    base = desktop(W, H, seed=41)
    pr = ctrl.progress
    rnd = random.Random(3)
    import datetime as dt
    today = dt.date.today()
    full = {}
    for d in range(110):
        day = today - dt.timedelta(days=d)
        if rnd.random() < (0.75 if d < 9 else 0.55):
            n = rnd.randint(1, 5)
            full[day.isoformat()] = [n * 25, n]
    keys = sorted(full)
    frames = []
    steps = 18
    for i in range(steps + 10):
        k = min(1.0, i / steps)
        pr.log = {kk: full[kk] for kk in keys[:int(len(keys) * k)]}
        ctrl.open_stats(cat)
        flush()
        img = base.copy()
        put(img, stand_pm("white", 1), 30, H - 6 - CH + FOOT)
        paste(img, ctrl._stats.grab(), 180, 30)
        frames.append(img)
    ctrl._stats.hide()
    save_gif(frames, out_name("stats", lang, True), 110)


@gif("quiet", multi=True)
def g_quiet(lang):
    """專注時其他貓咪回家，只留一隻顯示倒數；休息時再一起出來。"""
    ms._freeze((2026, 6, 10), 14)
    W, H = 680, 320
    base = desktop(W, H, seed=97)
    house = _prep_house()
    hx, hy = W - house.width() - 30, H - house.height() - 6
    U = house.U
    door_x = hx + (8 + 28) * U - CW / 2
    g = hy + (18 + sprites.HOUSE_GROUND) * U - (CH - FOOT)
    frames = []
    helpers = []
    for color in ("white", "black"):
        o = ctrl._spawn(ctrl.next_id, color)
        ctrl.next_id += 1
        helpers.append(o)
    start = [(200, "white"), (300, "black")]
    for t in range(64):
        if t % 11 == 0:
            house._puff()
        prog = t / 63
        img = base.copy()
        if 12 <= t < 22:
            house._door_until = time.monotonic() + 1
        if t == 22:
            for i, o in enumerate(helpers):
                house.residents.append(o)
                house.state[o] = {"slot": ("left", "right")[i], "mode": "peek", "rise": 0}
        paste(img, _house_frame(house), hx, hy)
        left = int(25 * 60 * (1 - prog))
        put(img, stand_pm("orange", 2), 40, g)
        bubble(img, 40 + CW / 2, g, label=(pixel.tomato(prog * 0.6, 2), "%02d:%02d" % (left // 60, left % 60)))
        for i, (x0, color) in enumerate(start):
            if t < 18:
                k = min(1, t / 14)
                put(img, walk_pm(color, 1, t + i), lerp(x0, door_x, k), g)
            elif t < 22:
                put(img, frames_of(color)["walk"][0][1], door_x, g, 1 - (t - 18) / 4)
        frames.append(img)
    house.anim.stop()
    for o in helpers:
        house.residents.remove(o)
        house.state.pop(o, None)
        ctrl.cats.remove(o)
        o.dispose()
    house.smoke.clear()
    house.hide()
    ms._unfreeze()
    save_gif(frames, out_name("quiet", lang, True), 100)


@gif("custom-time", multi=True)
def g_custom_time(lang):
    W, H = 640, 380
    base = desktop(W, H, seed=13)
    g = ground_y(H)
    ctrl.recent["focus"] = [37, 15]
    ctrl.picker.open("focus", cat)
    pk = ctrl.picker
    pk._set(25)
    flush()
    px, py = 240, 40
    plus = [b for b in pk.findChildren(type(ctrl.palette.save_btn)) if b._icon is not None][1]
    bx, by = _child_center(pk, plus)
    frames = []
    for t in range(40):
        if 8 <= t < 30:
            pk._bump(2 if t < 28 else 1)
        flush()
        img = base.copy()
        m = pk._minutes()
        put(img, stand_pm("orange", 1), 50, g)
        bubble(img, 50 + CW / 2, g, label=(pixel.tomato(0.05, 2), "%02d:00" % m))
        paste(img, pk.grab(), px, py)
        k = ease(min(1, t / 7))
        cursor(img, lerp(600, px + bx, k), lerp(340, py + by, k), click=(t % 2) * 0.5 if 8 <= t < 30 else 0)
        frames.append(img)
    pk.hide()
    save_gif(frames, out_name("custom-time", lang, True), 110)


@gif("todo", multi=True)
def g_todo(lang):
    W, H = 640, 440
    base = desktop(W, H, seed=7)
    g = ground_y(H)
    todo = ctrl.todo
    for r in todo._rows():
        r.setParent(None)
    items = (["Finish the design review", "Reply to emails", "Study for the midterm", "Water the plants"]
             if lang == "en" else ["完成設計審查", "回覆信件", "準備期中考", "幫植物澆水"])
    for t_ in items:
        todo._append(t_, False)
    todo._resize()
    todo.retranslate()
    todo.show()
    flush()
    px, py = 220, 40
    frames = []
    cur = (600, 400)
    rows = todo._rows()
    fx = Fx()
    for i, row in enumerate(rows):
        x, y = _child_center(todo, row)
        x = row.mapTo(todo, QPoint(14, 0)).x()
        tx, ty = px + x, py + y
        for t in range(6):
            img = base.copy()
            put(img, stand_pm("white", 1), 50, g)
            paste(img, todo.grab(), px, py)
            k = ease(t / 5)
            cursor(img, lerp(cur[0], tx, k), lerp(cur[1], ty, k))
            frames.append(img)
        row.done = True
        row.update()
        todo._update_count()
        flush()
        for t in range(4):
            img = base.copy()
            put(img, stand_pm("white", 1), 50, g)
            paste(img, todo.grab(), px, py)
            cursor(img, tx, ty, click=t / 3)
            frames.append(img)
        cur = (tx, ty)
    for t in range(24):
        img = base.copy()
        if t % 6 == 0:
            fx.burst("sparkle", 50 + CW / 2, g + 22 * SC, 2)
        put(img, stand_pm("white", [1, 2, 3, 0][t % 4]), 50, g)
        lift = bubble(img, 50 + CW / 2, g, tr("say_all_done"))
        paste(img, todo.grab(), px, py)
        fx.step()
        fx.draw(img, lift=lift)
        cursor(img, *cur)
        frames.append(img)
    todo.hide()
    for r in todo._rows():
        r.setParent(None)
    save_gif(frames, out_name("todo", lang, True), 100)


@gif("reminders", multi=True)
def g_reminders(lang):
    W, H = 560, 260
    base = desktop(W, H, seed=101)
    g = ground_y(H)
    frames = []
    msgs = tr("say_remind")
    for i, m in enumerate(msgs[:3]):
        for t in range(18):
            img = base.copy()
            pm = expr_pm("brown", "happy", 0) if t % 8 < 4 else stand_pm("brown", 2)
            put(img, pm, 230, g)
            bubble(img, 230 + CW / 2, g, m)
            chip(img, "%02d:%02d" % (10 + i, 30 if i % 2 else 0), 16, 14, big=True)
            frames.append(img)
    save_gif(frames, out_name("reminders", lang, True), 120)


@gif("battery", multi=True)
def g_battery(lang):
    W, H = 600, 300
    base = desktop(W, H, seed=103)
    g = ground_y(H)
    frames = []
    for t in range(48):
        img = base.copy()
        charging = t >= 26
        menubar(img, battery=(0.18 if not charging else 0.2, charging))
        if not charging:
            put(img, sleep_pm("white", 0, t) if t > 6 else stand_pm("white", 2), 240, g)
            bubble(img, 240 + CW / 2, g, tr("say_batt_low", p=18), sleeping=t > 6)
        else:
            put(img, expr_pm("white", "happy", 0), 240, g)
            bubble(img, 240 + CW / 2, g, tr("say_batt_thanks"))
        frames.append(img)
    save_gif(frames, out_name("battery", lang, True), 110)


# =====================================================================
# 和 macOS 好好相處
# =====================================================================
@gif("menubar", multi=True)
def g_menubar(lang):
    W, H = 720, 620
    base = desktop(W, H, seed=29)
    frames = []
    real = getattr(ctrl, "tray_menu", None)

    def build(m):
        ctrl.tray_menu = m
        ctrl._build_tray_menu()
    probe = Image.new("RGBA", base.size)
    tx = menubar(probe)
    acts_idx = [0, 2, 4, 6, 8]
    menu, mimg = grab_menu(build)
    acts = [a for a in menu.actions() if not a.isSeparator()]
    sub_act = next(a for a in acts if a.menu() and a.text() == tr("all_mode"))
    sub_i = acts.index(sub_act)
    mw = menu.width()
    menu.hide()
    mx = min(tx - 4, W - mw - 160)
    for t in range(10):
        img = base.copy()
        menubar(img)
        k = ease(t / 9)
        cursor(img, lerp(400, tx + 9, k), lerp(300, 13, k))
        frames.append(img)
    for step, i in enumerate(acts_idx + [sub_i]):
        i = min(i, len(acts) - 1)
        menu, mimg = grab_menu(build, active=i)
        now = [a for a in menu.actions() if not a.isSeparator()]
        geo = menu.actionGeometry(now[i])
        subimg = None
        if i == sub_i:
            sub = now[i].menu()
            sub.popup(QPoint(0, 0))
            flush()
            subimg = to_pil(sub.grab())
            sub.hide()
        menu.hide()
        for t in range(6 if i != sub_i else 18):
            img = base.copy()
            menubar(img, tray_hl=True)
            glass_paste(img, mimg, mx, 30)
            if subimg is not None:
                glass_paste(img, subimg, mx + menu.width() - 6, 30 + geo.top() - 6)
            cursor(img, mx + 60, 30 + geo.center().y(), click=0.4 if step == 0 and t < 2 else 0)
            frames.append(img)
    ctrl.tray_menu = real
    save_gif(frames, out_name("menubar", lang, True), 110)


@gif("hide", multi=True)
def g_hide(lang):
    W, H = 640, 280
    base = desktop(W, H, seed=107)
    g = ground_y(H)
    frames = []
    looks = [("orange", 80, 1), ("white", 280, 3), ("black", 460, 2)]
    for t in range(60):
        img = base.copy()
        if t < 14:
            a = 1.0
        elif t < 20:
            a = 1 - (t - 14) / 6
        elif t < 36:
            a = 0.0
        elif t < 42:
            a = (t - 36) / 6
        else:
            a = 1.0
        for i, (c, x, d) in enumerate(looks):
            pm = stand_pm(c, d)
            if a > 0:
                put(img, pm, x, g, a)
        if 10 <= t < 22 or 32 <= t < 44:
            chip(img, "Control + Option + M", W / 2, 30, anchor="tc", big=True)
        chip(img, tr("hide_all"), 16, 14)
        frames.append(img)
    save_gif(frames, out_name("hide", lang, True), 100)


@gif("login", multi=True)
def g_login(lang):
    import macos
    W = 720
    frames = []
    state = {"on": False}
    macos.login_item_enabled = lambda: state["on"]
    reset(cat, "orange", 1)

    def shots():
        menu, mimg = grab_menu(lambda m: ctrl.build_menu(cat, m))
        acts = [a for a in menu.actions() if not a.isSeparator()]
        sa = next(a for a in acts if a.menu() and a.text() == tr("settings"))
        menu.setActiveAction(sa)
        flush()
        mimg = to_pil(menu.grab())
        geo = menu.actionGeometry(sa)
        sub = sa.menu()
        sub.popup(QPoint(0, 0))
        flush()
        sacts = [a for a in sub.actions() if not a.isSeparator()]
        la = next(a for a in sacts if a.text() == tr("login_item"))
        sub.setActiveAction(la)
        flush()
        simg = to_pil(sub.grab())
        lgeo = sub.actionGeometry(la)
        sub.hide()
        menu.hide()
        return mimg, geo, simg, lgeo, menu.width()
    mx, my = 140, 40
    _m, geo0, simg0, _l, _w = shots()
    H = int(max(560, my + geo0.top() + simg0.height / S + 30))
    base = desktop(W, H, seed=3)
    g = ground_y(H)
    for phase in (0, 1):
        state["on"] = bool(phase)
        mimg, geo, simg, lgeo, mw = shots()
        for t in range(14 if phase == 0 else 20):
            img = base.copy()
            put(img, stand_pm("orange", 1), 30, g)
            glass_paste(img, mimg, mx, my)
            sxp, syp = mx + mw - 6, my + geo.top() - 6
            glass_paste(img, simg, sxp, syp)
            cursor(img, sxp + 60, syp + lgeo.center().y(), click=t / 4 if phase == 1 and t < 4 else 0)
            frames.append(img)
    save_gif(frames, out_name("login", lang, True), 110)


@gif("lowpower", multi=True)
def g_lowpower(lang):
    ms._freeze((2026, 4, 2), 13)
    W, H = 640, 320
    base = desktop(W, H, seed=109)
    g = ground_y(H)
    house = _prep_house()
    ctrl.low_power = True
    frames = []
    for t in range(48):
        if t % 12 == 0:
            house._puff()
        if t % 24 == 3:
            house._gust()
        img = base.copy()
        menubar(img, battery=(0.64, False), low_power=True)
        paste(img, _house_frame(house), W - house.width() - 20, H - house.height() - 6)
        put(img, walk_pm("orange", 1, t), 20 + t * 6, g)
        chip(img, cap("lowpower_on"), 16, 36)
        frames.append(img)
    ctrl.low_power = False
    house.gust.stop()
    house.anim.stop()
    house.petals.clear()
    house.smoke.clear()
    house.hide()
    ms._unfreeze()
    save_gif(frames, out_name("lowpower", lang, True), 90)


@gif("displays")
def g_displays(lang):
    W, H = 760, 300
    base = desktop(W, H, seed=113)
    d = ImageDraw.Draw(base)
    screens = [(30, 40, 360, 240), (400, 60, 330, 220)]
    for x, y, w, h in screens:
        d.rounded_rectangle([x * S, y * S, (x + w) * S, (y + h) * S], 10 * S, fill=(40, 40, 46))
        d.rounded_rectangle([(x + 8) * S, (y + 8) * S, (x + w - 8) * S, (y + h - 8) * S], 4 * S,
                            fill=(214, 222, 246))
    frames = []
    for t in range(72):
        img = base.copy()
        x = 60 + t * 9
        if x < 30 + 360 - 8 - CW + 20:
            gy = 40 + 240 - 8
        else:
            gy = 60 + 220 - 8
        put(img, walk_pm("white", 1, t), x, gy - CH + FOOT)
        frames.append(img)
    save_gif(frames, out_name("displays", lang, False), 90)


@gif("update", multi=True)
def g_update(lang):
    W, H = 720, 360
    base = desktop(W, H, seed=127)
    g = ground_y(H)
    frames = []
    v = "4.3.0"
    real = getattr(ctrl, "tray_menu", None)
    ctrl.updater.latest = (v, "https://github.com/Tanuki3701/meowmentum/releases/latest")

    def build(m):
        ctrl.tray_menu = m
        ctrl._build_tray_menu()
    menu, mimg = grab_menu(build, active=0)
    menu.hide()
    for t in range(50):
        img = base.copy()
        tx = menubar(img, tray_hl=t >= 30)
        if t < 14:
            put(img, stand_pm("black", 2), 200, g)
            bubble(img, 200 + CW / 2, g, tr("say_checking"))
        else:
            put(img, expr_pm("black", "excited" if t < 22 else "happy", 0), 200, g)
            bubble(img, 200 + CW / 2, g, tr("say_update", v=v))
        if t >= 30:
            mx = min(tx - 4, W - mimg.width / S - 10)
            glass_paste(img, mimg, mx, 30)
            cursor(img, mx + 60, 44)
        frames.append(img)
    ctrl.updater.latest = None
    ctrl.tray_menu = real
    save_gif(frames, out_name("update", lang, True), 110)


# =====================================================================
# 設計
# =====================================================================
@gif("icon")
def g_icon(lang):
    W, H = 300, 220
    base = desktop(W, H, seed=131)
    icon = Image.open(os.path.join(ROOT, "assets", "icon.png")).convert("RGBA").resize((160 * S, 160 * S),
                                                                                      Image.LANCZOS)
    frames = []
    rnd = random.Random(4)
    spots = [(rnd.uniform(40, 260), rnd.uniform(20, 200), rnd.randint(0, 11)) for _ in range(7)]
    for t in range(24):
        img = base.copy()
        bob = math.sin(t / 24 * 2 * math.pi) * 4
        img.alpha_composite(icon, (70 * S, int((30 + bob) * S)))
        for x, y, ph in spots:
            if (t + ph) % 12 < 5:
                put(img, sprites.effect("sparkle", 2), x, y)
        frames.append(img)
    save_gif(frames, out_name("icon", lang, False), 110)


@gif("glassmenu", multi=True)
def g_glassmenu(lang):
    W, H = 640, 580
    base = desktop(W, H, seed=3)
    g = ground_y(H)
    reset(cat, "orange", 1)
    frames = []
    menu, _ = grab_menu(lambda m: ctrl.build_menu(cat, m))
    acts = [a for a in menu.actions() if not a.isSeparator()]
    menu.hide()
    subs = [i for i, a in enumerate(acts) if a.menu()][:4]
    mx, my = 160, 30
    for i in [0, 1, 2] + subs:
        menu, mimg = grab_menu(lambda m: ctrl.build_menu(cat, m), active=i)
        a = [x for x in menu.actions() if not x.isSeparator()][i]
        geo = menu.actionGeometry(a)
        simg = None
        if a.menu():
            a.menu().popup(QPoint(0, 0))
            flush()
            simg = to_pil(a.menu().grab())
            a.menu().hide()
        menu.hide()
        for t in range(5 if not simg else 9):
            img = base.copy()
            put(img, stand_pm("orange", 1), 40, g)
            glass_paste(img, mimg, mx, my)
            if simg is not None:
                glass_paste(img, simg, mx + menu.width() - 6, my + geo.top() - 6)
            cursor(img, mx + 70, my + geo.center().y())
            frames.append(img)
    save_gif(frames, out_name("glassmenu", lang, True), 110)


@gif("dialogs", multi=True)
def g_dialogs(lang):
    PURGE["on"] = True
    W, H = 760, 560
    base = desktop(W, H, seed=137)
    shots = []
    todo = ctrl.todo
    for r in todo._rows():
        r.setParent(None)
    for t_, d in ([("Finish the design review", True), ("Reply to emails", False)] if lang == "en"
                  else [("完成設計審查", True), ("回覆信件", False)]):
        todo._append(t_, d)
    todo._resize()
    todo.retranslate()
    todo.show()
    flush()
    shots.append(to_pil(todo.grab()))
    todo.hide()
    ctrl.open_shop(cat)
    flush()
    shots.append(to_pil(ctrl._shop.grab()))
    ctrl._shop.hide()
    ctrl.open_stats(cat)
    flush()
    shots.append(to_pil(ctrl._stats.grab()))
    ctrl._stats.hide()
    ctrl.picker.open("focus", cat)
    flush()
    shots.append(to_pil(ctrl.picker.grab()))
    ctrl.picker.hide()
    frames = []
    for i, sh in enumerate(shots):
        for t in range(14):
            img = base.copy()
            a = min(1, t / 3)
            x = (W * S - sh.width) // 2
            y = (H * S - sh.height) // 2
            layer = img.copy()
            layer.alpha_composite(sh, (x, max(0, y)))
            img = Image.blend(img, layer, a) if a < 1 else layer
            frames.append(img)
    for r in todo._rows():
        r.setParent(None)
    PURGE["on"] = False
    save_gif(frames, out_name("dialogs", lang, True), 110)


@gif("language")
def g_language(lang):
    W, H = 640, 560
    base = desktop(W, H, seed=3)
    g = ground_y(H)
    reset(cat, "orange", 1)
    shots = []
    for lg in ("en", "zh"):
        i18n.set_lang(lg)
        menu, mimg = grab_menu(lambda m: ctrl.build_menu(cat, m))
        menu.hide()
        shots.append(mimg)
    frames = []
    for mimg in shots + shots:
        for t in range(14):
            img = base.copy()
            put(img, stand_pm("orange", 1), 40, g)
            glass_paste(img, mimg, 160, 30)
            frames.append(img)
    i18n.set_lang("en")
    save_gif(frames, out_name("language", lang, False), 110)


@gif("hero")
def g_hero(lang):
    """首頁：在視窗上散步、帶著番茄鐘走路、貓屋冒煙、睡覺的貓。"""
    ms._freeze((2026, 6, 10), 14)
    W, H = 900, 340
    base = desktop(W, H, seed=1)
    fake_window(base, 330, 120, 330, 200)
    house = _prep_house()
    g = ground_y(H)
    fx = Fx()
    cid = ctrl.add_custom_color((245, 245, 245), (40, 140, 70), "", "calico")
    frames = []
    for t in range(60):
        if t % 11 == 0:
            house._puff()
        if t % 20 == 5:
            house._gust()
        img = base.copy()
        paste(img, _house_frame(house), W - house.width() - 10, H - house.height() - 6)
        x1 = 350 + (t * 4.5) % 250
        put(img, walk_pm(cid, 1, t), x1, 120 - (CH - FOOT))
        x2 = 30 + t * 4
        put(img, walk_pm("orange", 1, t), x2, g)
        bubble(img, x2 + CW / 2, g, label=(pixel.tomato(0.35 + t / 300, 2), "16:%02d" % (12 - t // 10)))
        if t % 8 == 0:
            fx.add("zzz", 260 + CW / 2 + 22, g + 29 * SC - 6)
        put(img, sleep_pm("black", 0, t), 260, g)
        fx.step()
        fx.draw(img)
        frames.append(img)
    ctrl.delete_custom_color(cid)
    house.gust.stop()
    house.anim.stop()
    house.petals.clear()
    house.smoke.clear()
    house.hide()
    ms._unfreeze()
    save_gif(frames, out_name("hero", lang, False), 90)


if __name__ == "__main__":
    want = sys.argv[1:] or list(GIFS)
    for name in want:
        fn, multi = GIFS[name]
        for lg in (("en", "zh") if multi else ("en",)):
            i18n.set_lang(lg)
            t0 = time.time()
            fn(lg)
            print("  ", name, lg, "%.1fs" % (time.time() - t0), flush=True)
    i18n.set_lang("en")
    ctrl.quit()
