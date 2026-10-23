"""管理所有貓咪，以及全域功能：番茄鐘、待辦清單、休息提醒、電量、睡覺、摸摸、餵食、貓屋、選單列。"""
import json
import random
import re
import shutil
import time

from PySide6.QtCore import QObject, QPoint, QProcess, QRect, QSettings, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

import i18n
import macos
import pixel
import sprites
from cat import COLORS, MODES, Cat
from glassmenu import PlainMenu
from house import House
from i18n import tr
from macos import show_on_all_spaces
from panels import Food, PaletteDialog, TimePicker, TodoPanel

PULSE_INTERVAL = 400        # 背景輕量檢查：閒置時間、滑鼠是否在貓咪身上
PET_INTERVAL = 50           # 滑鼠在貓咪身上時，才開始密集偵測「摸摸」
BATTERY_INTERVAL = 120_000  # 每 2 分鐘看一次電量


def _subtract(intervals, cut):
    l, r = cut
    out = []
    for a, b in intervals:
        if r < a or l > b:
            out.append((a, b))
            continue
        if a < l:
            out.append((a, l - 1))
        if r < b:
            out.append((r + 1, b))
    return out


class Controller(QObject):
    def __init__(self):
        super().__init__()
        # 設定沿用舊名稱的儲存位置，改名後貓咪、待辦和設定都會保留
        self.settings = QSettings("DesktopCat", "DesktopCat")
        s = self.settings
        self.tired = False
        i18n.set_lang(str(s.value("lang", "") or i18n.system_default()))

        # ---- 自訂毛色、貓屋 ----
        self._load_custom_colors()
        self.house = House(self)

        # ---- 貓咪們 ----
        self.cats = []
        ids = [int(x) for x in str(s.value("cats", "0")).split(",") if x.strip().isdigit()] or [0]
        self.next_id = max(int(s.value("next_id", 0)), max(ids) + 1)
        for cid in ids:
            self._spawn(cid)

        self.todo = TodoPanel(self)

        # ---- 番茄鐘 ----
        self.pomo_phase = None
        self.pomo_end = 0.0
        self.pomo_total = 1.0
        self.pomo_timer = self._timer(self._pomo_tick, 1000)
        self.break_min = int(s.value("break_min", 5))          # 專注結束後自動休息的分鐘數
        self.recent = {k: self._load_list(f"recent_{k}") for k in ("focus", "break")}
        self.picker = TimePicker(self)
        self.palette = PaletteDialog(self)

        # ---- 休息提醒 ----
        self.remind_min = int(s.value("remind_min", 0))
        self.remind_timer = self._timer(self._remind)
        self._apply_remind()

        # ---- 睡覺 & 摸摸 ----
        self.sleep_min = int(s.value("sleep_min", 3))
        self.sleeping = False
        self._last_pos = QCursor.pos()
        self._last_active = time.monotonic()
        self.pulse_timer = self._timer(self._pulse, PULSE_INTERVAL)
        self.pulse_timer.start()
        self.pet_timer = self._timer(self._pet_step, PET_INTERVAL)
        self._pet_cat = None
        self._pet_flips = []

        # ---- 電量 ----
        self.battery_alert = str(s.value("battery_alert", "1")) == "1"
        self._batt = None
        self.battery_timer = self._timer(self._check_battery, BATTERY_INTERVAL)
        if shutil.which("pmset"):
            self.battery_timer.start()
            QTimer.singleShot(3000, self._check_battery)

        self._win_cache = (0.0, [])
        self._foods = set()

        # ---- 選單列圖示（一次控制全部貓咪）----
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            icon = QIcon(sprites.resource_path("assets", "tray.png"))
            icon.setIsMask(True)                      # macOS：跟著深淺色模式自動變色
            self.tray = QSystemTrayIcon(icon, self)
            self.tray.setToolTip("Meowmentum")
            self.tray_menu = PlainMenu()
            self.tray_menu.aboutToShow.connect(self._build_tray_menu)
            self._build_tray_menu()
            self.tray.setContextMenu(self.tray_menu)
            self.tray.show()
        if str(s.value("house_visible", "0")) == "1":
            self.house.show_house()

    def _timer(self, slot, interval=None):
        t = QTimer(self)
        t.setTimerType(Qt.CoarseTimer)
        t.timeout.connect(slot)
        if interval:
            t.setInterval(interval)
        return t

    @property
    def main_cat(self):
        return self.cats[0]

    # ---------------- 多隻貓 ---------------- #
    def _spawn(self, cid, color=None, near=None):
        cat = Cat(self, cid, color, near)
        cat.show()
        show_on_all_spaces(cat)
        self.cats.append(cat)
        if color:
            cat.set_color(color)
        return cat

    def _save_ids(self):
        self.settings.setValue("cats", ",".join(str(c.cid) for c in self.cats))
        self.settings.setValue("next_id", self.next_id)

    def add_cat(self, near):
        used = {c.color for c in self.cats}
        choices = [c for c in COLORS if c not in used] or list(COLORS)
        cid = self.next_id
        self.next_id += 1
        for key in self.settings.allKeys():  # 清掉同編號的舊資料
            if key.startswith(f"cat{cid}/"):
                self.settings.remove(key)
        cat = self._spawn(cid, random.choice(choices), near)
        cat.set_mode(near.mode)
        self._save_ids()
        cat.overlay.say(tr("say_hello"), 2500)

    def remove_cat(self, cat):
        if len(self.cats) <= 1:
            return
        self.cats.remove(cat)
        for key in self.settings.allKeys():
            if key.startswith(cat.prefix):
                self.settings.remove(key)
        cat.dispose()
        self._save_ids()

    # ---------------- 選單 ---------------- #
    def _pomo_menu(self, menu, cat):
        icon = QIcon(pixel.tomato(self._pomo_progress() if self.pomo_phase == "focus" else 1.0,
                                  pixel.MENU_UNIT))
        pomo = menu.sub(icon, self._pomo_title())
        if self.pomo_phase:
            pomo.item("power", tr("pomo_stop"), self.stop_pomodoro)
            pomo.addSeparator()
        for m in (15, 25, 50):
            pomo.item(None, tr("focus_n", m=m), lambda m=m: self.start_focus(m))
        pomo.item("pencil", tr("custom_focus"), lambda: self.picker.open("focus", cat))
        pomo.addSeparator()
        pomo.item("cup", tr("break_n", m=self.break_min), lambda: self.start_break(self.break_min))
        pomo.item("pencil", tr("custom_break"), lambda: self.picker.open("break", cat))

    def _feed_menu(self, menu, title, handler):
        feed = menu.sub("can", title)
        for f in sprites.FLAVORS:
            feed.item(QIcon(sprites.effect("can_" + f, 2)), tr("flavor_" + f), lambda f=f: handler(f))
        feed.addSeparator()
        feed.item("dot", tr("flavor_random"), lambda: handler("random"))

    def _settings_menu(self, menu):
        settings = menu.sub("gear", tr("settings"))
        settings.sub(pixel.blank_icon(), tr("remind")).choices(
            {0: tr("off"), 30: tr("every_n", m=30), 45: tr("every_n", m=45), 60: tr("every_n", m=60)},
            self.remind_min, self.set_remind)
        settings.sub(pixel.blank_icon(), tr("nap_after")).choices(
            {0: tr("never"), 1: tr("n_min", m=1), 3: tr("n_min", m=3), 5: tr("n_min", m=5),
             10: tr("n_min", m=10)}, self.sleep_min, self.set_sleep_min)
        settings.item("check" if self.battery_alert else None, tr("battery_alert"),
                      lambda: self.set_battery_alert(not self.battery_alert))
        menu.sub("globe", tr("language")).choices(i18n.LANGS, i18n.lang(), self.set_language)

    def build_menu(self, cat, menu):
        """在某一隻貓身上按右鍵的選單。"""
        self._pomo_menu(menu, cat)
        menu.item("note", tr("todo"), lambda: self.toggle_todo(cat))
        self._feed_menu(menu, tr("feed"), lambda f: self.feed(cat, f))
        menu.addSeparator()
        cat.add_own_menus(menu)
        menu.item("home", tr("go_home"), lambda: self.send_home(cat))
        menu.addSeparator()
        menu.item(pixel.cat_head_icon("orange", plus=True), tr("add_cat"), lambda: self.add_cat(cat))
        if len(self.cats) > 1:
            menu.item("close", tr("remove_cat"), lambda: self.remove_cat(cat))
        self._settings_menu(menu)
        menu.addSeparator()
        menu.item("power", tr("quit"), self.quit)

    def _build_tray_menu(self):
        """選單列（螢幕最上方）的選單：一次控制全部貓咪。"""
        m = self.tray_menu
        m.clear()
        self._pomo_menu(m, self.main_cat)
        m.item("note", tr("todo"), lambda: self.toggle_todo(self.main_cat))
        self._feed_menu(m, tr("feed_all"), self.feed_all)
        m.addSeparator()
        modes = {c.mode for c in self.cats}
        m.sub("paw", tr("all_mode")).choices(
            {k: tr("mode_" + k) for k in MODES}, modes.pop() if len(modes) == 1 else None,
            self.set_all_mode)
        hm = m.sub("home", tr("house_menu"))
        self.house.fill_menu(hm)
        hm.addSeparator()
        hm.item("check" if self.house.isVisible() else None, tr("house_show"), self.toggle_house)
        m.addSeparator()
        m.item(pixel.cat_head_icon("orange", plus=True), tr("add_cat"), lambda: self.add_cat(self.main_cat))
        m.item("palette", tr("palette"), lambda: self.open_palette(self.main_cat))
        self._settings_menu(m)
        m.addSeparator()
        m.item("power", tr("quit"), self.quit)

    # ---------------- 全部貓咪 ---------------- #
    def set_all_mode(self, mode):
        for c in self.cats:
            c.set_mode(mode)

    def send_home(self, cat):
        cat.go_home(self.house)

    def go_home_all(self):
        self.house.show_house()
        for i, c in enumerate(self.cats):
            QTimer.singleShot(i * 250, lambda c=c: c in self.cats and c.go_home(self.house))

    def come_out(self):
        for i, c in enumerate(list(self.house.residents)):
            QTimer.singleShot(i * 400, lambda c=c: c.leave_home())

    def toggle_house(self):
        if self.house.isVisible():
            self.house.hide_house()
        else:
            self.house.show_house()

    # ---------------- Dock ---------------- #
    def dock_span(self, cat):
        """「在 Dock 上走」模式：貓咪視窗左上角 x 可以走的範圍。"""
        screen = QGuiApplication.screenAt(cat.geometry().center()) or QGuiApplication.primaryScreen()
        g = screen.geometry()
        left, right = g.left(), g.right() + 1
        info = macos.dock_info()
        if (screen == QGuiApplication.primaryScreen() and info["orientation"] == "bottom"
                and info["width"]):
            w = min(info["width"], g.width())
            left = g.center().x() - w / 2
            right = left + w
        pad = 16
        return (left + pad - cat.width() / 2, max(left + pad, right - pad) - cat.width() / 2)

    # ---------------- 自訂毛色 ---------------- #
    def _load_list(self, key):
        try:
            return [int(x) for x in json.loads(self.settings.value(key, "[]"))]
        except Exception:
            return []

    def _load_custom_colors(self):
        try:
            self.custom_colors = json.loads(self.settings.value("custom_colors", "[]"))
        except Exception:
            self.custom_colors = []
        sprites.CUSTOM.clear()
        for c in self.custom_colors:
            sprites.CUSTOM[c["id"]] = self._spec_of(c)

    @staticmethod
    def _spec_of(c):
        return sprites.derive_spec(c["fur"], c["eye"], c.get("pattern", "solid"), c.get("p1"), c.get("p2"))

    def _save_custom_colors(self):
        self.settings.setValue("custom_colors", json.dumps(self.custom_colors))

    def custom_color_names(self):
        """自訂毛色的顯示名稱：有取名就用名字，沒取名的依序編號（刪掉後自動接續，不跳號）。"""
        names, n = {}, 0
        for c in self.custom_colors:
            if c.get("name"):
                names[c["id"]] = c["name"]
            else:
                n += 1
                names[c["id"]] = tr("custom_n", n=n)
        return names

    def next_default_name(self):
        n = sum(1 for c in self.custom_colors if not c.get("name")) + 1
        return tr("custom_n", n=n)

    def custom_color(self, cid):
        return next((c for c in self.custom_colors if c["id"] == cid), None)

    def open_palette(self, cat):
        self.palette.open_for(cat)

    def add_custom_color(self, fur, eye, name="", pattern="solid", p1=None, p2=None):
        used = {c["id"] for c in self.custom_colors}
        k = 1
        while f"custom{k}" in used:
            k += 1
        cid = f"custom{k}"
        c = {"id": cid, "fur": list(fur), "eye": list(eye), "name": name.strip(),
             "pattern": pattern, "p1": list(p1) if p1 else None, "p2": list(p2) if p2 else None}
        self.custom_colors.append(c)
        sprites.CUSTOM[cid] = self._spec_of(c)
        self._save_custom_colors()
        return cid

    def update_custom_color(self, cid, fur, eye, name="", pattern="solid", p1=None, p2=None):
        c = self.custom_color(cid)
        if not c:
            return self.add_custom_color(fur, eye, name, pattern, p1, p2)
        c.update(fur=list(fur), eye=list(eye), name=name.strip(), pattern=pattern,
                 p1=list(p1) if p1 else None, p2=list(p2) if p2 else None)
        sprites.CUSTOM[cid] = self._spec_of(c)
        self._save_custom_colors()
        for cat in self.cats:
            if cat.color == cid:
                cat.set_color(cid)
        return cid

    def delete_custom_color(self, cid):
        self.custom_colors = [c for c in self.custom_colors if c["id"] != cid]
        self._save_custom_colors()
        for c in self.cats:
            if c.color == cid:
                c.set_color("orange")
        sprites.CUSTOM.pop(cid, None)

    def set_language(self, lang):
        i18n.set_lang(lang)
        self.settings.setValue("lang", lang)
        self.todo.retranslate()
        self.picker.hide()
        self.palette.hide()

    # ---------------- 番茄鐘 ---------------- #
    def _pomo_left(self):
        return max(0, int(self.pomo_end - time.monotonic() + 0.999))

    def _pomo_progress(self):
        if self.pomo_phase != "focus":
            return 0.0
        return 1.0 - (self.pomo_end - time.monotonic()) / self.pomo_total

    def _pomo_title(self):
        if not self.pomo_phase:
            return tr("pomodoro")
        left = self._pomo_left()
        key = "pomo_focus_left" if self.pomo_phase == "focus" else "pomo_break_left"
        return tr(key, t=f"{left // 60:02d}:{left % 60:02d}")

    def start_focus(self, minutes):
        self._start_phase("focus", minutes)
        self.main_cat.overlay.say(tr("say_focus", m=minutes), 3000)

    def start_break(self, minutes):
        self._start_phase("break", minutes)

    def picked(self, kind, minutes):
        """時間選擇器按下「開始」：記住自訂值並開始計時。"""
        self.remember_recent(kind, minutes)
        if kind == "focus":
            self.start_focus(minutes)
        else:
            self.break_min = minutes
            self.settings.setValue("break_min", minutes)
            self.start_break(minutes)

    def remember_recent(self, kind, minutes):
        lst = [m for m in self.recent[kind] if m != minutes]
        self.recent[kind] = ([minutes] + lst)[:4]
        self.settings.setValue(f"recent_{kind}", json.dumps(self.recent[kind]))

    def forget_recent(self, kind, minutes):
        self.recent[kind] = [m for m in self.recent[kind] if m != minutes]
        self.settings.setValue(f"recent_{kind}", json.dumps(self.recent[kind]))

    def _start_phase(self, phase, minutes):
        self.pomo_phase = phase
        self.pomo_total = minutes * 60
        self.pomo_end = time.monotonic() + self.pomo_total
        self.pomo_timer.start()
        self._pomo_tick()

    def stop_pomodoro(self):
        self.pomo_phase = None
        self.pomo_timer.stop()
        self.main_cat.overlay.set_label(None)

    def _pomo_tick(self):
        if self.pomo_end - time.monotonic() <= 0:
            self._pomo_finish()
            return
        left = self._pomo_left()
        if self.pomo_phase == "focus":
            icon = pixel.tomato(self._pomo_progress(), 2)   # 黃綠 → 黃橘 → 紅
        else:
            icon = pixel.icon_pixmap("cup", 2)
        self.main_cat.overlay.set_label((icon, f"{left // 60:02d}:{left % 60:02d}"))

    def _pomo_finish(self):
        cat = self.main_cat
        if self.pomo_phase == "focus":
            self.start_break(self.break_min)
            r = cat.screen_rect()
            x = r.center().x() - cat.width() / 2

            def arrived():
                cat.spin(2)
                cat.overlay.say(tr("say_focus_done", m=self.break_min), 6000)
                cat.overlay.burst("heart", 4)

            cat.go_to(x, cat.ground_y(), then=arrived)
        else:
            self.stop_pomodoro()
            cat.wake(quiet=True)
            cat.overlay.say(tr("say_break_done"), 5000)
            cat.spin(1)

    # ---------------- 待辦清單 ---------------- #
    def toggle_todo(self, cat):
        self.todo.toggle_near(cat)

    def celebrate(self):
        for c in self.cats:
            c.spin(2)
            c.overlay.burst("heart", 5)
        self.main_cat.overlay.say(tr("say_all_done"), 4000)

    # ---------------- 休息提醒 ---------------- #
    def set_remind(self, minutes):
        self.remind_min = minutes
        self.settings.setValue("remind_min", minutes)
        self._apply_remind()

    def _apply_remind(self):
        if self.remind_min > 0:
            self.remind_timer.start(self.remind_min * 60_000)
        else:
            self.remind_timer.stop()

    def _remind(self):
        if self.sleeping or self.pomo_phase == "focus":
            return  # 人不在電腦前，或正在專注，就不打擾
        cat = self.main_cat
        cat.overlay.say(random.choice(tr("say_remind")), 8000)
        cat.overlay.burst("heart", 2)

    # ---------------- 睡覺 & 摸摸 ---------------- #
    def set_sleep_min(self, minutes):
        self.sleep_min = minutes
        self.settings.setValue("sleep_min", minutes)
        if minutes == 0 and self.sleeping:
            self._wake_all()

    def _wake_all(self):
        self.sleeping = False
        for c in self.cats:
            c.wake()

    def _pulse(self):
        now = time.monotonic()
        pos = QCursor.pos()
        idle = macos.idle_seconds()
        if idle is None:  # 非 macOS：用滑鼠有沒有動來判斷
            if pos != self._last_pos:
                self._last_active = now
            idle = now - self._last_active
        self._last_pos = pos

        if self.sleep_min > 0:
            if not self.sleeping and idle >= self.sleep_min * 60:
                self.sleeping = True
                for c in self.cats:
                    c.sleep()
            elif self.sleeping and idle < 1.5:
                self._wake_all()
            elif self.sleeping:
                for c in self.cats:  # 剛才在忙（跳躍、吃東西）的貓，忙完再去睡
                    if c.activity != "sleep":
                        c.sleep()

        if not self.pet_timer.isActive() and QGuiApplication.mouseButtons() == Qt.NoButton:
            for c in self.cats:
                if c.geometry().contains(pos):
                    self._pet_cat = c
                    self._pet_last_x = pos.x()
                    self._pet_dir = 0
                    self._pet_flips = []
                    self.pet_timer.start()
                    break

    def _pet_step(self):
        cat = self._pet_cat
        pos = QCursor.pos()
        if (cat not in self.cats or not cat.geometry().contains(pos)
                or QGuiApplication.mouseButtons() != Qt.NoButton):
            self.pet_timer.stop()
            return
        dx = pos.x() - self._pet_last_x
        if abs(dx) >= 3:
            d = 1 if dx > 0 else -1
            if self._pet_dir and d != self._pet_dir:
                self._pet_flips.append(time.monotonic())
            self._pet_dir = d
            self._pet_last_x = pos.x()
        now = time.monotonic()
        self._pet_flips = [t for t in self._pet_flips if now - t < 2.0]
        if len(self._pet_flips) >= 3:
            self._pet_flips = []
            cat.petted()

    # ---------------- 電量 ---------------- #
    def set_battery_alert(self, on):
        self.battery_alert = on
        self.settings.setValue("battery_alert", "1" if on else "0")

    def _check_battery(self):
        proc = QProcess(self)
        proc.finished.connect(lambda *_: self._battery_result(proc))
        proc.start("pmset", ["-g", "batt"])

    def _battery_result(self, proc):
        out = bytes(proc.readAllStandardOutput()).decode(errors="ignore")
        proc.deleteLater()
        m = re.search(r"(\d+)%", out)
        if not m:  # 桌機沒有電池
            self.battery_timer.stop()
            return
        pct, on_ac = int(m.group(1)), "AC Power" in out
        prev, self._batt = self._batt, (pct, on_ac)
        tired = (not on_ac) and pct <= 20
        if tired != self.tired:
            self.tired = tired
            for c in self.cats:
                c.refresh_speed()
        if not self.battery_alert:
            return
        cat = self.main_cat
        if prev is None:
            if tired:
                cat.overlay.say(tr("say_batt_low", p=pct), 6000)
            return
        p_pct, p_ac = prev
        if on_ac and not p_ac:
            cat.overlay.say(tr("say_batt_thanks"), 3500)
            cat.overlay.burst("heart", 3)
        elif not on_ac and ((pct <= 20 < p_pct) or (pct <= 10 < p_pct)):
            cat.overlay.say(tr("say_batt_low", p=pct), 6000)

    # ---------------- 餵食 ---------------- #
    def feed_all(self, flavor):
        for i, c in enumerate(self.cats):
            QTimer.singleShot(i * 300, lambda c=c: c in self.cats and self.feed(c, flavor))

    def feed(self, cat, flavor="random"):
        if flavor == "random":
            flavor = random.choice(sprites.FLAVORS)
        r = cat.screen_rect()
        x = cat.center_x() + random.choice((-1, 1)) * random.randint(150, 400)
        x = max(r.left() + 60, min(r.right() - 60, x))
        cat.overlay.say(tr("say_can"), 1500)

        def landed(food):
            if cat not in self.cats:
                food.close()
                return
            side = -1 if food.center_x() < cat.center_x() else 1
            tx = food.center_x() - cat.width() / 2 - side * cat.width() * 0.45
            cat.go_to(tx, cat.ground_y(), then=lambda: cat.eat(food), speed=8)

        food = Food(x, r.top(), r.bottom() + 1, max(2, cat.scale - 1), landed, flavor)
        self._foods.add(food)  # 保留參照，避免被回收
        food.destroyed.connect(lambda *_: self._foods.discard(food))

    # ---------------- 視窗資訊（在視窗上走用）---------------- #
    def windows(self):
        now = time.monotonic()
        if now - self._win_cache[0] > 0.2:
            wins = [(wid, QRect(x, y, w, h)) for wid, x, y, w, h in macos.list_windows()]
            self._win_cache = (now, wins)
        return self._win_cache[1]

    def top_segments(self, cat):
        """所有可以站的視窗頂邊（扣掉被前面視窗擋住的部分）。"""
        wins = self.windows()
        w, h, foot = cat.width(), cat.height(), cat.foot_off()
        segs = []
        for i, (wid, r) in enumerate(wins):
            y = r.top()
            intervals = [(r.left(), r.right())]
            for _, f in wins[:i]:
                if f.top() < y and f.bottom() > y - h // 2:
                    intervals = _subtract(intervals, (f.left(), f.right()))
            screen = QGuiApplication.screenAt(QPoint(r.center().x(), max(y, 0) + 1))
            if not screen:
                continue
            avail = screen.availableGeometry()
            if y - (h - foot) < avail.top() or y > avail.bottom() - 40:
                continue
            for a, b in intervals:
                ca, cb = a + w * 0.25, b - w * 0.25
                if cb - ca >= w * 0.3:
                    segs.append({"wid": wid, "left": r.left(), "top": y, "right": r.right(),
                                 "a": ca, "b": cb})
        return segs

    # ---------------- 結束 ---------------- #
    def quit(self):
        for c in self.cats:
            c.save_pos()
        self.settings.sync()
        QApplication.quit()
