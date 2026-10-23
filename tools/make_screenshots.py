"""產生 README 用的截圖（直接用程式裡的元件繪製，再合成到示意桌面上）。

執行：QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=2 python3 tools/make_screenshots.py
輸出：docs/screenshots/*.png
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ.setdefault("HOME", tempfile.mkdtemp())  # 不要動到真正的設定

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402
from PySide6.QtCore import QBuffer, QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

import macos  # noqa: E402

macos.list_windows = lambda: []
macos.idle_seconds = lambda: 0.0
macos.GLASS_AVAILABLE = True          # 用玻璃版的透明樣式（模糊在合成時模擬）

import glassmenu  # noqa: E402
import i18n  # noqa: E402
import pixel  # noqa: E402
from controller import Controller  # noqa: E402

glassmenu.install(app)
OUT = os.path.join(ROOT, "docs", "screenshots")
os.makedirs(OUT, exist_ok=True)
DPR = app.devicePixelRatio()


def to_pil(pm):
    buf = QBuffer()
    buf.open(QBuffer.ReadWrite)
    pm.save(buf, "PNG")
    import io
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA")


def desktop(w, h, seed=0):
    """柔和漸層的示意桌面。"""
    s = int(DPR)
    img = Image.new("RGBA", (w * s, h * s))
    top, bottom = (196, 206, 240), (250, 214, 196)
    d = ImageDraw.Draw(img)
    for y in range(h * s):
        t = y / (h * s)
        d.line([(0, y), (w * s, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    blobs = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(blobs)
    import random
    rnd = random.Random(seed)
    for _ in range(5):
        cx, cy, r = rnd.randint(0, w * s), rnd.randint(0, h * s), rnd.randint(80 * s, 200 * s)
        col = rnd.choice([(255, 240, 200, 120), (180, 200, 255, 120), (255, 190, 210, 110)])
        bd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    img.alpha_composite(blobs.filter(ImageFilter.GaussianBlur(60 * s)))
    return img


def fake_window(img, x, y, w, h, title=""):
    s = int(DPR)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([(x + 4) * s, (y + 8) * s, (x + w + 4) * s, (y + h + 8) * s], 12 * s, fill=(0, 0, 0, 40))
    layer = layer.filter(ImageFilter.GaussianBlur(10 * s))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x * s, y * s, (x + w) * s, (y + h) * s], 12 * s, fill=(252, 252, 253, 255),
                        outline=(210, 210, 215, 255), width=s)
    d.rectangle([x * s, (y + 28) * s, (x + w) * s, (y + 28) * s + s], fill=(225, 225, 230, 255))
    for i, c in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
        cx, cy = (x + 16 + i * 18) * s, (y + 14) * s
        d.ellipse([cx - 6 * s, cy - 6 * s, cx + 6 * s, cy + 6 * s], fill=c)
    for i in range(4):
        d.rounded_rectangle([(x + 20) * s, (y + 48 + i * 22) * s, (x + w - 40 - i * 30) * s, (y + 58 + i * 22) * s],
                            4 * s, fill=(232, 232, 238, 255))


def paste(img, pm_or_img, x, y):
    layer = pm_or_img if isinstance(pm_or_img, Image.Image) else to_pil(pm_or_img)
    img.alpha_composite(layer, (int(x * DPR), int(y * DPR)))


def glass_paste(img, menu_img, x, y, radius=glassmenu.RADIUS):
    """模擬系統毛玻璃：把底下的桌面模糊後再貼上選單。"""
    s = int(DPR)
    w, h = menu_img.size
    box = (int(x * s), int(y * s), int(x * s) + w, int(y * s) + h)
    region = img.crop(box).filter(ImageFilter.GaussianBlur(14 * s))
    tint = Image.new("RGBA", region.size, (246, 246, 250, 150))
    region.alpha_composite(tint)
    mask = Image.new("L", region.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius * s, fill=255)
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([box[0], box[1] + 6 * s, box[2], box[3] + 6 * s], radius * s,
                                             fill=(0, 0, 0, 55))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(12 * s)))
    img.paste(region, box[:2], mask)
    img.alpha_composite(menu_img, box[:2])


def flush():
    for _ in range(5):
        app.processEvents()


ctrl = Controller()
cat = ctrl.main_cat
ctrl.pulse_timer.stop()
ctrl.battery_timer.stop()


def reset(c, color="orange", direction=1):
    c._stop_all()
    c.activity = None
    c.set_color(color)
    c.direction = direction
    c.frame = 1
    c.overlay.text = None
    c.overlay.label = None
    c.overlay.effects = []
    c.expression = None
    c.update()


def cat_with_overlay(img, c, x, y):
    """把貓咪和頭上的對話框一起貼到 (x, y)（貓咪左上角）。"""
    paste(img, c.grab(), x, y)
    ov = c.overlay
    ov.show()
    flush()
    paste(img, ov.grab(), x + c.width() / 2 - ov.W / 2, y + c.content_top() - ov.H + 4)
    ov.hide()


def save(img, name):
    img.convert("RGB").save(os.path.join(OUT, name), optimize=True)
    print("saved", name)


def shot_menu(lang, name, sub_index=None):
    i18n.set_lang(lang)
    img = desktop(560, 470, seed=3)
    reset(cat, "orange", 1)
    paste(img, cat.grab(), 60, 300)
    menu = glassmenu.GlassMenu()
    ctrl.build_menu(cat, menu)
    menu.popup(QPoint(0, 0))
    flush()
    mimg = to_pil(menu.grab())
    mx, my = 150, 40
    glass_paste(img, mimg, mx, my)
    if sub_index is not None:
        act = [a for a in menu.actions() if a.menu()][sub_index]
        menu.setActiveAction(act)
        sub = act.menu()
        sub.popup(QPoint(0, 0))
        flush()
        geo = menu.actionGeometry(act)
        glass_paste(img, to_pil(sub.grab()), mx + menu.width() - 6, my + geo.top() - 6)
        sub.hide()
    menu.hide()
    save(img, name)


def shot_pomodoro():
    """上排：番茄從黃綠 → 黃橘 → 紅的完整變化；下排：貓咪頭上實際看到的計時泡泡。"""
    from PIL import ImageFont
    i18n.set_lang("en")
    W, H = 760, 350
    img = desktop(W, H, seed=5)
    s = int(DPR)
    font = ImageFont.truetype(os.path.join(ROOT, "assets", "fonts", "fusion-pixel.ttf"), 12 * s)
    d = ImageDraw.Draw(img)
    steps = [(0.0, "25:00"), (0.25, "18:45"), (0.5, "12:30"), (0.75, "06:15"), (1.0, "00:00")]
    gap = 140
    x0 = (W - gap * (len(steps) - 1)) // 2
    for i, (prog, t) in enumerate(steps):
        tom = to_pil(pixel.tomato(prog, 5))
        cx = x0 + i * gap
        img.alpha_composite(tom, (cx * s - tom.width // 2, 40 * s))
        tw = d.textlength(t, font=font)
        d.text((cx * s - tw / 2, 40 * s + tom.height + 8 * s), t, font=font, fill=(58, 55, 55))
        if i < len(steps) - 1:                      # 像素箭頭
            ax, ay = (cx + gap // 2) * s, 40 * s + tom.height // 2
            u = 2 * s
            for k in range(5):
                d.rectangle([ax - 6 * u + k * u * 2, ay - u // 2, ax - 6 * u + k * u * 2 + u - 1, ay + u // 2],
                            fill=(58, 55, 55))
            for k in range(3):
                d.rectangle([ax + 4 * u - k * u, ay - k * u - u // 2, ax + 5 * u - k * u - 1, ay + k * u + u // 2],
                            fill=(58, 55, 55))
    for i, (prog, t) in enumerate([(0.02, "24:31"), (0.5, "12:30"), (0.97, "00:45")]):
        reset(cat, "orange", 2 if i != 1 else 1)
        cat.overlay.label = (pixel.tomato(prog, 2), t)
        cat_with_overlay(img, cat, 90 + i * 230, 190)
    save(img, "pomodoro.png")


def shot_todo():
    i18n.set_lang("en")
    img = desktop(600, 420, seed=7)
    reset(cat, "white", 1)
    cat.overlay.text = None
    paste(img, cat.grab(), 50, 250)
    todo = ctrl.todo
    for r in todo._rows():
        r.setParent(None)
    for t, d in [("Finish the design review", True), ("Reply to emails", True),
                 ("Study for the midterm", False), ("Water the plants", False)]:
        todo._append(t, d)
    todo._resize()
    todo.retranslate()
    todo.show()
    flush()
    paste(img, todo.grab(), 200, 50)
    todo.hide()
    save(img, "todo.png")


def shot_sleep_pet_feed():
    i18n.set_lang("en")
    img = desktop(760, 300, seed=9)
    # 睡覺
    reset(cat, "black", 3)
    cat.sleep()
    cat.overlay.effects = [["zzz", cat.overlay.W / 2 + 34, cat.overlay.H - 22, 5],
                           ["zzz", cat.overlay.W / 2 + 46, cat.overlay.H - 52, 5]]
    cat_with_overlay(img, cat, 40, 150)
    cat.wake(quiet=True)
    # 摸摸
    reset(cat, "orange", 2)
    cat.overlay.text = i18n.tr("say_pet")[0]
    cat.overlay.effects = [["heart", cat.overlay.W / 2 - 30, cat.overlay.H - 20, 5],
                           ["heart", cat.overlay.W / 2 + 24, cat.overlay.H - 36, 5],
                           ["heart", cat.overlay.W / 2 - 4, cat.overlay.H - 52, 5]]
    cat_with_overlay(img, cat, 300, 150)
    # 餵食
    reset(cat, "brown", 1)
    cat.overlay.text = i18n.tr("say_yummy")
    cat_with_overlay(img, cat, 540, 150)
    import sprites
    paste(img, sprites.effect("can", 2), 540 + cat.width() - 6, 150 + cat.height() - 5 * 3 - 16)
    save(img, "sleep-pet-feed.png")


def shot_windows():
    i18n.set_lang("en")
    img = desktop(760, 440, seed=11)
    fake_window(img, 40, 170, 380, 230)
    fake_window(img, 330, 90, 380, 260)
    foot = 5 * 3
    reset(cat, "orange", 1)
    paste(img, cat.grab(), 120, 170 - (cat.height() - foot))
    reset(cat, "white", 3)
    paste(img, cat.grab(), 520, 90 - (cat.height() - foot))
    save(img, "walk-on-windows.png")


def shot_hero():
    i18n.set_lang("en")
    img = desktop(900, 360, seed=1)
    fake_window(img, 520, 120, 330, 220)
    foot = 5 * 3
    reset(cat, "white", 3)
    paste(img, cat.grab(), 640, 120 - (cat.height() - foot))
    reset(cat, "orange", 1)
    cat.overlay.label = (pixel.tomato(0.35, 2), "16:12")
    cat_with_overlay(img, cat, 80, 360 - cat.height() + foot - 40)
    reset(cat, "black", 1)
    cat.sleep()
    cat.overlay.effects = [["zzz", cat.overlay.W / 2 + 34, cat.overlay.H - 22, 5]]
    cat_with_overlay(img, cat, 300, 360 - cat.height() + foot - 40)
    cat.wake(quiet=True)
    save(img, "hero.png")


def shot_picker():
    i18n.set_lang("en")
    img = desktop(620, 360, seed=13)
    reset(cat, "orange", 1)
    cat.overlay.label = (pixel.tomato(0.15, 2), "67:00")
    cat_with_overlay(img, cat, 50, 190)
    ctrl.recent["focus"] = [67, 37, 15]
    ctrl.picker.open("focus", cat)
    flush()
    paste(img, ctrl.picker.grab(), 260, 60)
    ctrl.picker.hide()
    save(img, "custom-time.png")


def shot_flavors():
    i18n.set_lang("en")
    img = desktop(1080, 320, seed=17)
    import sprites
    plan = [("tuna", "orange", "happy", "heart", "react_tuna"),
            ("chicken", "white", "happy", "note", "react_chicken"),
            ("salmon", "brown", "excited", "sparkle", "react_salmon"),
            ("catnip", "black", "dizzy", "sparkle", "react_dizzy"),
            ("bitter", "orange", "yuck", "sweat", "react_bitter")]
    for i, (flavor, color, expr, fx, text) in enumerate(plan):
        reset(cat, color, 1)
        cat.expression, cat._expr_side = expr, 0
        cat.overlay.text = i18n.tr(text)
        cat.overlay.effects = [[fx, cat.overlay.W / 2 - 28, cat.overlay.H - 22, 5],
                               [fx, cat.overlay.W / 2 + 26, cat.overlay.H - 40, 5]]
        cat.update()
        x = 40 + i * 205
        cat_with_overlay(img, cat, x, 160)
        paste(img, sprites.effect("can_" + flavor, 2), x + cat.width() - 2, 160 + cat.height() - 15 - 16)
    save(img, "flavors.png")


def shot_house():
    """左邊：沒有貓在家，門窗關著；右邊：貓咪在家，探頭、睡覺、煙囪冒煙。"""
    import random as _r
    i18n.set_lang("en")
    W, H = 860, 340
    img = desktop(W, H, seed=19)
    house = ctrl.house
    house.show()
    _r.seed(2)
    for i in range(40):                  # 先讓花瓣飄一下
        if i % 18 == 0:
            house._gust()
        house._animate()
    flush()
    paste(img, house.grab(), 30, H - house.height() - 6)
    house.petals.clear()
    others = []
    for color in ("white", "black", "brown"):
        o = ctrl._spawn(ctrl.next_id, color)
        ctrl.next_id += 1
        others.append(o)
    for o, slot, mode in zip(others, ("left", "door", "attic"), ("peek", "peek", "sleep")):
        house.residents.append(o)
        house.state[o] = {"slot": slot, "mode": mode, "rise": 6}
    house._tick_n = 2
    _r.seed(4)
    for i in range(70):                  # 讓煙和花瓣先飄一下再拍
        if i % 9 == 0:
            house._puff()
        if i % 22 == 0:
            house._gust()
        house._animate()
    house.gust.stop()
    house.anim.stop()
    flush()
    paste(img, house.grab(), W - house.width() - 30, H - house.height() - 6)
    reset(cat, "orange", 1)
    cat.overlay.text = i18n.tr("go_home") + "!"
    cat_with_overlay(img, cat, W // 2 - cat.width() // 2 - 10, H - cat.height() + 15 - 6 - 4 * 3)
    house.hide()
    for o in others:
        house.residents.remove(o)
        house.state.pop(o)
        ctrl.cats.remove(o)
        o.dispose()
    save(img, "house.png")


def shot_patterns():
    """花紋：三花、賓士、虎斑、斑點。"""
    i18n.set_lang("en")
    W, H = 760, 260
    img = desktop(W, H, seed=31)
    looks = [((245, 245, 245), (40, 140, 70), "calico", None, None),
             ((60, 52, 56), (230, 190, 60), "tuxedo", None, None),
             ((150, 150, 158), (60, 160, 80), "tabby", (90, 90, 100), None),
             ((236, 170, 80), (58, 55, 55), "tabby", (186, 96, 46), None),
             ((245, 245, 245), (80, 150, 230), "spots", (60, 52, 56), None)]
    ids = []
    for i, (fur, eye, pat, p1, p2) in enumerate(looks):
        cid = ctrl.add_custom_color(fur, eye, "", pat, p1, p2)
        ids.append(cid)
        reset(cat, cid, (1, 2, 3, 1, 3)[i])
        cat.overlay.text = i18n.tr("pat_" + pat)
        cat_with_overlay(img, cat, 30 + i * 145, H - cat.height() - 10)
    reset(cat, "orange", 1)
    for cid in ids:
        ctrl.delete_custom_color(cid)
    save(img, "patterns.png")


def shot_palette():
    i18n.set_lang("en")
    img = desktop(640, 620, seed=23)
    cid = ctrl.add_custom_color((140, 190, 230), (230, 190, 60), "Blueberry")
    cid2 = ctrl.add_custom_color((245, 245, 245), (80, 150, 230), "", "calico")
    reset(cat, cid, 1)
    paste(img, cat.grab(), 40, 300)
    reset(cat, cid2, 3)
    paste(img, cat.grab(), 130, 320)
    reset(cat, "orange", 1)
    ctrl.open_palette(cat)
    ctrl.palette._pick_pattern("tuxedo")
    ctrl.palette._pick_fur((80, 80, 90))
    ctrl.palette._pick_eye((230, 190, 60))
    ctrl.palette.name_edit.setText("Mochi")
    flush()
    paste(img, ctrl.palette.grab(), 250, 40)
    ctrl.palette.hide()
    for c in (cid, cid2):
        ctrl.delete_custom_color(c)
    save(img, "palette.png")


def shot_tray():
    """選單列的選單（macOS 上是系統原生選單，這裡用同樣的內容示意）。"""
    i18n.set_lang("en")
    img = desktop(680, 520, seed=29)
    s = int(DPR)
    bar = Image.new("RGBA", (img.width, 26 * s), (246, 246, 248, 215))
    img.alpha_composite(bar, (0, 0))
    from PIL import ImageDraw as _D
    hl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    _D.Draw(hl).rounded_rectangle([212 * s, 3 * s, 238 * s, 23 * s], 5 * s, fill=(0, 0, 0, 38))
    img.alpha_composite(hl)
    tray = Image.open(os.path.join(ROOT, "assets", "tray.png")).convert("RGBA")
    tray = tray.resize((18 * s, 18 * s), Image.NEAREST)
    img.alpha_composite(tray, (216 * s, 4 * s))
    real = ctrl.tray_menu if ctrl.tray else None
    ctrl.tray_menu = glassmenu.GlassMenu()
    ctrl._build_tray_menu()
    menu = ctrl.tray_menu
    menu.popup(QPoint(0, 0))
    flush()
    glass_paste(img, to_pil(menu.grab()), 212, 30)
    act = [a for a in menu.actions() if a.menu()][2]       # Mode for all cats
    sub = act.menu()
    sub.popup(QPoint(0, 0))
    flush()
    glass_paste(img, to_pil(sub.grab()), 212 + menu.width() - 6, 30 + menu.actionGeometry(act).top() - 6)
    sub.hide()
    menu.hide()
    if real is not None:
        ctrl.tray_menu = real
    save(img, "menubar.png")


shot_hero()
shot_menu("en", "menu-en.png", sub_index=1)
shot_menu("zh", "menu-zh.png")
shot_pomodoro()
shot_todo()
shot_sleep_pet_feed()
shot_windows()
shot_picker()
shot_flavors()
shot_house()
shot_patterns()
shot_palette()
shot_tray()
ctrl.quit()
