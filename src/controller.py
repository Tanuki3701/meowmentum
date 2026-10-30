"""管理所有貓咪，以及全域功能：番茄鐘、待辦清單、休息提醒、電量、睡覺、摸摸、餵食、貓屋、選單列。"""
import json
import random
import re
import shutil
import time

from PySide6.QtCore import QObject, QPoint, QProcess, QRect, QSettings, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

import art
import i18n
import macos
import pixel
import progress
import seasons
import sprites
from cat import COLORS, MODES, SIZES, Cat
from glassmenu import PlainMenu
from house import House
from i18n import tr
from macos import show_on_all_spaces
from panels import Food, PaletteDialog, TimePicker, TodoPanel
from progress import Progress
from social import Social
from toys import Gift, Spot, Toy

PULSE_INTERVAL = 400        # 背景輕量檢查：閒置時間、滑鼠是否在貓咪身上
PET_INTERVAL = 50           # 滑鼠在貓咪身上時，才開始密集偵測「摸摸」
BATTERY_INTERVAL = 120_000  # 每 2 分鐘看一次電量
SLOW_INTERVAL = 60_000      # 每分鐘：低耗電模式、深夜提醒、每天檢查更新
FURNITURE_INTERVAL = 25_000 # 每 25 秒看看有沒有貓想去紙箱、貓跳台
FULLSCREEN_INTERVAL = 2_000 # 全螢幕偵測（只有開啟「全螢幕時藏起來」才會跑）
GIFT_AFTER = 20 * 60        # 離開超過 20 分鐘，回來會收到小禮物
HOTKEY_TEXT = "⌃⌥M"


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
        self.low_power = macos.low_power_mode()
        self.all_hidden = False          # 目前所有貓咪是否藏起來（手動或全螢幕）
        self._hidden_manual = False
        self._hidden_fullscreen = False
        self.toy = None
        self.spots = {}
        self._gifts = set()
        self.progress = Progress(s)
        self.seasonal = str(s.value("seasonal", "1")) == "1"
        self.focus_home = str(s.value("focus_home", "0")) == "1"
        self.autohide_fs = str(s.value("autohide_fullscreen", "1")) == "1"
        self.update_check = str(s.value("update_check", "1")) == "1"
        i18n.set_lang(str(s.value("lang", "") or i18n.system_default()))

        # ---- 天氣（預設關閉）----
        from weather import Weather
        self.weather = Weather(s)
        self.weather.changed.connect(self._weather_changed)
        self._phase = seasons.phase()

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
        self.social = Social(self)
        self._shop = self._furn = self._stats = self._namer = self._inside = None

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

        # ---- 白噪音、會議提醒 ----
        from meetings import Meetings
        from sounds import FocusSound
        self.sound = FocusSound(s)
        self.meetings = Meetings(s)
        self.meetings.soon.connect(self._meeting_soon)

        # ---- 快捷鍵、更新（選單列選單會用到）----
        self.hotkey_ok = macos.register_hotkey(lambda: QTimer.singleShot(0, self.toggle_hidden))
        from updater import Updater
        self.updater = Updater(s)
        self.updater.found.connect(self._update_found)
        self._update_said = False

        # ---- 選單列圖示（一次控制全部貓咪）----
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_season = seasons.season() if self.seasonal else None
            icon = pixel.tray_icon(self._tray_season)  # macOS：跟著深淺色模式自動變色
            self.tray = QSystemTrayIcon(icon, self)
            self.tray.setToolTip("Meowmentum")
            self.tray_menu = PlainMenu()
            self.tray_menu.aboutToShow.connect(self._build_tray_menu)
            self._build_tray_menu()
            self.tray.setContextMenu(self.tray_menu)
            self.tray.show()
        if str(s.value("house_visible", "0")) == "1":
            self.house.show_house()

        # ---- 家具、深夜、低耗電、全螢幕、快捷鍵、更新 ----
        for item in sorted(self.progress.placed):
            if self.progress.has(item):
                self.spots[item] = Spot(self, item)
        self.furniture_timer = self._timer(self._furniture_tick, FURNITURE_INTERVAL)
        self.furniture_timer.start()
        self._last_yawn = 0.0
        self.slow_timer = self._timer(self._slow_tick, SLOW_INTERVAL)
        self.slow_timer.start()
        self.fs_timer = self._timer(self._check_fullscreen, FULLSCREEN_INTERVAL)
        if self.autohide_fs:
            self.fs_timer.start()
        if self.update_check:
            QTimer.singleShot(8000, self.updater.check)

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

    @property
    def pomo_cat(self):
        """顯示番茄鐘的貓：從哪隻貓的右鍵選單開始，就是那隻（選單列開始的話用最後互動的貓）。"""
        c = getattr(self, "_pomo_cat", None)
        return c if c in self.cats else (self.last_cat if self.last_cat in self.cats else self.main_cat)

    @property
    def last_cat(self):
        return getattr(self, "_last_cat", None) or self.cats[0]

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
        self.check_badges()

    def remove_cat(self, cat):
        if len(self.cats) <= 1:
            return
        self.cats.remove(cat)
        if cat.toy is not None:
            cat.toy = None
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
            pomo.item(None, tr("focus_n", m=m), lambda m=m: self.start_focus(m, cat))
        pomo.item("pencil", tr("custom_focus"), lambda: self.picker.open("focus", cat))
        pomo.addSeparator()
        pomo.item("cup", tr("break_n", m=self.break_min), lambda: self.start_break(self.break_min, cat))
        pomo.item("pencil", tr("custom_break"), lambda: self.picker.open("break", cat))

    def _feed_menu(self, menu, title, handler):
        feed = menu.sub("can", title)
        for f in sprites.FLAVORS:
            feed.item(QIcon(sprites.effect("can_" + f, 2)), tr("flavor_" + f), lambda f=f: handler(f))
        feed.addSeparator()
        feed.item("dot", tr("flavor_random"), lambda: handler("random"))

    def _toy_menu(self, menu):
        toy = menu.sub(QIcon(art.icon_pm("toy")), tr("toys"))
        if self.toy is not None:
            toy.item("close", tr("toy_away"), self.stop_toy)
            toy.addSeparator()
        toy.item(QIcon(art.icon_pm("toy")), tr("toy_wand"), lambda: self.start_toy("wand"))
        toy.item(QIcon(art.pix(art.YARN[0], 1.5)), tr("toy_yarn"), lambda: self.start_toy("yarn"))

    def _furniture_menu(self, menu):
        fm = menu.sub(QIcon(art.icon_pm("box")), tr("furniture"))
        any_owned = False
        for item in ("box", "tree"):
            if self.progress.has(item):
                any_owned = True
                fm.item("check" if item in self.spots else None, tr("item_" + item),
                        lambda i=item: self.place_item(i, i not in self.spots))
        if not any_owned:
            act = fm.addAction(tr("furniture_none"))
            act.setEnabled(False)
        fm.addSeparator()
        fm.item(QIcon(art.icon_pm("sofa")), tr("furniture_shop"), lambda: self.open_furniture())

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
        settings.addSeparator()
        settings.item("check" if self.focus_home else None, tr("focus_home"),
                      lambda: self._toggle("focus_home"))
        settings.item("check" if self.seasonal else None, tr("seasonal"),
                      lambda: self._toggle("seasonal"))
        settings.item("check" if self.autohide_fs else None, tr("autohide_fs"),
                      lambda: self._toggle("autohide_fs"))
        settings.item("check" if self.weather.enabled() else None, tr("weather_on"),
                      lambda: self.weather.set_enabled(not self.weather.enabled()))
        if self.sound.available():
            settings.sub(QIcon(art.icon_pm("sound")), tr("focus_sound")).choices(
                {k: tr("sound_" + k) for k in ("off", "purr", "rain", "fire")}, self.sound.kind, self.sound.set_kind)
        if self.meetings.available():
            settings.item("check" if self.meetings.enabled() else None, tr("meetings_on"),
                          lambda: self.meetings.set_enabled(not self.meetings.enabled()))
        settings.addSeparator()
        settings.item("check" if macos.login_item_enabled() else None, tr("login_item"),
                      lambda: macos.set_login_item(not macos.login_item_enabled()))
        settings.item("check" if self.update_check else None, tr("update_check"),
                      lambda: self._toggle("update_check"))
        settings.item(QIcon(art.icon_pm("update")), tr("update_now"), self.check_update_now)
        menu.sub("globe", tr("language")).choices(i18n.LANGS, i18n.lang(), self.set_language)

    def build_menu(self, cat, menu):
        """在某一隻貓身上按右鍵的選單。"""
        self._last_cat = cat
        self._pomo_menu(menu, cat)
        menu.item("note", tr("todo"), lambda: self.toggle_todo(cat))
        self._feed_menu(menu, tr("feed"), lambda f: self.feed(cat, f))
        self._toy_menu(menu)
        menu.addSeparator()
        cat.add_own_menus(menu)
        if cat.indoor is not None or cat.activity == "home":
            menu.item("paw", tr("come_out_one"), cat.leave_home)
        else:
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
        if self.updater.latest:
            m.item(QIcon(art.icon_pm("update")), tr("update_get", v=self.updater.latest[0]), self.open_update)
            m.addSeparator()
        self._pomo_menu(m, self.last_cat)
        m.item("note", tr("todo"), lambda: self.toggle_todo(self.main_cat))
        m.item(QIcon(art.icon_pm("chart")), tr("stats"), lambda: self.open_stats(self.main_cat))
        m.item(QIcon(art.icon_pm("shirt")), tr("shop_with", n=self.progress.coins),
               lambda: self.open_shop(self.main_cat))
        m.item(QIcon(art.icon_pm("sofa")), tr("furniture_shop"), lambda: self.open_furniture())
        m.addSeparator()
        self._feed_menu(m, tr("feed_all"), self.feed_all)
        self._toy_menu(m)
        m.addSeparator()
        modes = {c.mode for c in self.cats}
        m.sub("paw", tr("all_mode")).choices(
            {k: tr("mode_" + k) for k in MODES}, modes.pop() if len(modes) == 1 else None,
            self.set_all_mode)
        scales = {c.scale for c in self.cats}
        m.sub("size", tr("all_size")).choices(
            {z: tr(f"size_{z}") for z in SIZES}, scales.pop() if len(scales) == 1 else None,
            self.set_all_size)
        hm = m.sub("home", tr("house_menu"))
        self.house.fill_menu(hm)
        hm.addSeparator()
        hm.item("check" if self.house.isVisible() else None, tr("house_show"), self.toggle_house)
        self._furniture_menu(m)
        hide_text = tr("show_all") if self._hidden_manual else tr("hide_all")
        if self.hotkey_ok:
            hide_text += f"    {HOTKEY_TEXT}"
        m.item(QIcon(art.icon_pm("hide")), hide_text, self.toggle_hidden)
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

    def set_all_size(self, scale):
        for c in self.cats:
            c.set_scale(scale)

    def _toggle(self, name):
        keys = {"focus_home": "focus_home", "seasonal": "seasonal", "autohide_fs": "autohide_fullscreen",
                "update_check": "update_check"}
        on = not getattr(self, name)
        setattr(self, name, on)
        self.settings.setValue(keys[name], "1" if on else "0")
        if name == "seasonal":
            self.house.petals.clear()
            self.house.update_fx()
            self._refresh_tray_icon()
            for c in self.cats:
                c._build_frames()
        elif name == "autohide_fs":
            if on:
                self.fs_timer.start()
            else:
                self.fs_timer.stop()
                self._hidden_fullscreen = False
                self._apply_hidden()
        elif name == "update_check" and on:
            self.updater.check()

    # ---------------- 視窗：商店、紀錄、名字、貓屋裡面 ---------------- #
    def open_shop(self, cat):
        """服飾店：帽子和脖子上的飾品。"""
        from shop import ShopPanel
        if self._shop is None:
            self._shop = ShopPanel(self, progress.WARDROBE, "shop_title", "shirt")
        self._shop.open_for(cat)

    def open_furniture(self, cat=None):
        """家具店：桌面家具、房間和閣樓的擺設。"""
        from shop import ShopPanel
        if self._furn is None:
            self._furn = ShopPanel(self, progress.FURNITURE, "furniture_title", "sofa")
        anchor = self.house if self.house.isVisible() else (cat or self.main_cat)
        self._furn.open_for(cat, anchor)

    def open_stats(self, cat):
        from shop import StatsPanel
        if self._stats is None:
            self._stats = StatsPanel(self)
        self._stats.open_near(cat)

    def rename(self, cat):
        from shop import NamePrompt
        if self._namer is None:
            self._namer = NamePrompt(self)
        self._namer.open_for(cat)

    def open_interior(self):
        self.house.show_house()
        self.house.set_view("inside")

    # ---------------- 藏起所有貓咪 ---------------- #
    def toggle_hidden(self):
        self._hidden_manual = not self._hidden_manual
        self._apply_hidden()

    def _check_fullscreen(self):
        screens = [(g.x(), g.y(), g.width(), g.height())
                   for g in (sc.geometry() for sc in QGuiApplication.screens())]
        fs = macos.fullscreen_active(screens)
        if fs != self._hidden_fullscreen:
            self._hidden_fullscreen = fs
            self._apply_hidden()

    def _apply_hidden(self):
        hidden = self._hidden_manual or self._hidden_fullscreen
        if hidden == self.all_hidden:
            return
        self.all_hidden = hidden
        if hidden:
            self.stop_toy()
        for c in self.cats:
            if c.activity not in ("home", "box"):
                c.setVisible(not hidden)
            c.overlay._refresh()
        for w in list(self.spots.values()) + list(self._gifts):
            w.setVisible(not hidden)
        if self.settings.value("house_visible", "0") == "1" or self.house.residents:
            if hidden:
                self.house.hide()
            else:
                self.house.show_house()
        for panel in (self.todo, self.picker, self.palette, self._shop, self._furn, self._stats, self._namer):
            if panel is not None and hidden:
                panel.hide()

    # ---------------- 玩具 ---------------- #
    def start_toy(self, kind):
        self.stop_toy()
        self.toy = Toy(kind, self._toy_done)
        for i, c in enumerate(self.cats):
            QTimer.singleShot(i * 200, lambda c=c: self.toy is not None and c in self.cats
                              and c.indoor is None and c.play_with(self.toy))

    def stop_toy(self):
        if self.toy is not None:
            self.toy.stop()

    def _toy_done(self, toy):
        if self.toy is toy:
            self.toy = None
        for c in self.cats:
            if c.toy is toy:
                c.stop_play()

    # ---------------- 家具 ---------------- #
    def place_item(self, item, on):
        if on and item not in self.spots and self.progress.has(item):
            self.spots[item] = Spot(self, item)
            if self.all_hidden:
                self.spots[item].hide()
        elif not on and item in self.spots:
            self.spots.pop(item).dispose()
        self.progress.set_placed(item, on)

    def _free_cats(self):
        return [c for c in self.cats if c.activity is None and c.mode in ("idle", "random")
                and c.isVisible() and c.spot is None and c.indoor is None]

    def invite_to(self, spot):
        if spot.occupant is not None:
            return
        free = self._free_cats()
        if not free:
            return
        cat = min(free, key=lambda c: abs(c.center_x() - (spot.x() + spot.width() / 2)))
        cat.overlay.say(tr("say_coming"), 1500)
        cat.visit(spot)

    def _furniture_tick(self):
        if self.all_hidden or self.sleeping or self.toy is not None:
            return
        for spot in self.spots.values():
            if spot.occupant is None and random.random() < 0.3:
                free = [c for c in self._free_cats()
                        if c.screen_rect().contains(spot.geometry().center())]
                if free:
                    random.choice(free).visit(spot)
                    return

    # ---------------- 小禮物、深夜、低耗電、更新 ---------------- #
    def _meeting_soon(self, title, minutes):
        """會議前 5 分鐘：最近互動的貓咪跑到畫面中間提醒你，其他貓咪先回家。"""
        if self.all_hidden:
            return
        cat = self.last_cat
        if cat.indoor is not None or cat.activity in ("home", "entering"):
            cat.leave_home()
        r = cat.screen_rect()
        text = tr("say_meeting", m=minutes, t=title) if title else tr("say_meeting_untitled", m=minutes)

        def arrived():
            cat.overlay.say(text, 9000)
            cat.overlay.burst("sparkle", 3)
        if cat.activity is None:
            cat.go_to(r.center().x() - cat.width() / 2, cat.ground_y(), then=arrived, speed=6)
        else:
            arrived()
        for i, c in enumerate([c for c in self.cats if c is not cat]):
            QTimer.singleShot(1200 + i * 300, lambda c=c: c in self.cats and c.go_home(self.house))

    def check_badges(self):
        """看看有沒有新的成就；有的話由最近互動的貓咪宣布，獎勵的飾品馬上就能戴。"""
        new = self.progress.check_badges(len(self.cats), max((c.love for c in self.cats), default=0))
        for i, b in enumerate(new):
            reward = next((r for bid, _ic, r in progress.BADGES if bid == b), None)
            text = tr("say_badge", b=tr("badge_" + b))
            if reward:
                text += "\n" + tr("say_badge_reward", item=tr("item_" + reward))

            def say(text=text):
                cat = self.last_cat
                cat.overlay.say(text, 5000)
                cat.overlay.burst("sparkle", 4)
            QTimer.singleShot(1500 + i * 5500, say)

    def collect_gift(self, gift):
        self._gifts.discard(gift)
        self.progress.add_coins(2)
        self.progress.note("gift")
        cat = self.main_cat
        cat.overlay.say(tr("say_gift_thanks", n=2), 2500)
        cat.overlay.burst("heart", 3)

    def _slow_tick(self):
        lp = macos.low_power_mode()
        if lp != self.low_power:
            self.low_power = lp
            for c in self.cats:
                c.refresh_speed()
        now = time.monotonic()
        if (seasons.is_late_night() and not self.sleeping and not self.all_hidden
                and now - self._last_yawn > 3600):
            self._last_yawn = now
            cat = self.main_cat
            if cat.activity in (None, "hold") and cat.isVisible():
                cat.overlay.say(random.choice(tr("say_late")), 5000)
                cat.overlay.zzz()
        if self.update_check:
            self.updater.check()

    def _update_found(self, version, _url):
        if not self._update_said:
            self._update_said = True
            self.main_cat.overlay.say(tr("say_update", v=version), 6000)

    def open_update(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        if self.updater.latest:
            QDesktopServices.openUrl(QUrl(self.updater.latest[1]))

    def check_update_now(self):
        self._update_said = False
        self.updater.check(force=True)
        self.main_cat.overlay.say(tr("say_checking"), 2000)

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
        return sprites.derive_spec(c["fur"], c["eye"], c.get("pattern", "solid"), c.get("p1"), c.get("p2"),
                                   c.get("stripes"), c.get("white"), c.get("eye2"), c.get("points"),
                                   c.get("gradient"), c.get("ears"), c.get("tail"))

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

    @staticmethod
    def _look(pattern, p1, p2, stripes, white, eye2, points=None, gradient=None, ears=None, tail=None):
        base, p1, p2, stripes, white = sprites.normalize_look(pattern, p1, p2, stripes, white)
        L = lambda v: list(v) if v else None     # noqa: E731
        return {"pattern": base, "p1": L(p1), "p2": L(p2), "stripes": L(stripes), "white": L(white),
                "eye2": L(eye2), "points": L(points), "gradient": L(gradient), "ears": L(ears), "tail": L(tail)}

    def add_custom_color(self, fur, eye, name="", pattern="solid", p1=None, p2=None,
                         stripes=None, white=None, eye2=None, points=None, gradient=None, ears=None, tail=None):
        used = {c["id"] for c in self.custom_colors}
        k = 1
        while f"custom{k}" in used:
            k += 1
        cid = f"custom{k}"
        c = {"id": cid, "fur": list(fur), "eye": list(eye), "name": name.strip(),
             **self._look(pattern, p1, p2, stripes, white, eye2, points, gradient, ears, tail)}
        self.custom_colors.append(c)
        sprites.CUSTOM[cid] = self._spec_of(c)
        self._save_custom_colors()
        return cid

    def update_custom_color(self, cid, fur, eye, name="", pattern="solid", p1=None, p2=None,
                            stripes=None, white=None, eye2=None, points=None, gradient=None, ears=None, tail=None):
        c = self.custom_color(cid)
        if not c:
            return self.add_custom_color(fur, eye, name, pattern, p1, p2, stripes, white, eye2,
                                         points, gradient, ears, tail)
        c.update(fur=list(fur), eye=list(eye), name=name.strip(),
                 **self._look(pattern, p1, p2, stripes, white, eye2, points, gradient, ears, tail))
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
        for panel in (self._shop, self._furn, self._stats, self._namer, self._inside):
            if panel is not None:
                panel.hide()

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

    def _set_pomo_cat(self, cat):
        old = self.pomo_cat
        self._pomo_cat = cat if cat in self.cats else self.last_cat
        if old is not self._pomo_cat:
            old.overlay.set_label(None)
        cat = self._pomo_cat
        if cat.indoor is not None or cat.activity in ("home", "entering"):
            cat.leave_home()                     # 在家的貓：先出來陪你

    def start_focus(self, minutes, cat=None):
        self._set_pomo_cat(cat)
        self._start_phase("focus", minutes)
        pc = self.pomo_cat
        pc.overlay.say(tr("say_focus", m=minutes), 3000)
        if self.focus_home:
            # 專注時其他貓咪回家睡覺，留下開始番茄鐘的那隻貓安靜地陪你、顯示倒數
            for i, c in enumerate([c for c in self.cats if c is not pc]):
                QTimer.singleShot(400 + i * 250, lambda c=c: c in self.cats and c.go_home(self.house))
            QTimer.singleShot(3200, lambda: self.pomo_phase == "focus" and self.pomo_cat.sleep())

    def start_break(self, minutes, cat=None):
        if cat is not None:
            self._set_pomo_cat(cat)
        self._start_phase("break", minutes)

    def picked(self, kind, minutes, cat=None):
        """時間選擇器按下「開始」：記住自訂值並開始計時。"""
        self.remember_recent(kind, minutes)
        if kind == "focus":
            self.start_focus(minutes, cat)
        else:
            self.break_min = minutes
            self.settings.setValue("break_min", minutes)
            self.start_break(minutes, cat)

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
        if phase == "focus":                       # 專注時的白噪音
            self.sound.stop()
            self.sound.start()
        else:
            self.sound.stop()

    def stop_pomodoro(self):
        self.pomo_phase = None
        self.pomo_timer.stop()
        self.sound.stop()
        self.pomo_cat.overlay.set_label(None)

    def _pomo_tick(self):
        if self.pomo_end - time.monotonic() <= 0:
            self._pomo_finish()
            return
        left = self._pomo_left()
        if self.pomo_phase == "focus":
            icon = pixel.tomato(self._pomo_progress(), 2)   # 黃綠 → 黃橘 → 紅
        else:
            icon = pixel.icon_pixmap("cup", 2)
        self.pomo_cat.overlay.set_label((icon, f"{left // 60:02d}:{left % 60:02d}"))

    def _pomo_finish(self):
        cat = self.pomo_cat
        if self.pomo_phase == "focus":
            minutes = int(round(self.pomo_total / 60))
            coins = self.progress.reward_for(minutes)
            self.progress.record_focus(minutes)
            self.progress.add_coins(coins)
            cat.add_love(5)
            self.check_badges()
            if self.focus_home and self.house.residents:
                QTimer.singleShot(1500, self.come_out)
            cat.wake(quiet=True)
            self.start_break(self.break_min)
            r = cat.screen_rect()
            x = r.center().x() - cat.width() / 2

            def arrived():
                cat.spin(2)
                cat.overlay.say(tr("say_focus_done", m=self.break_min) + "\n" + tr("say_reward", n=coins), 6000)
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
        away = time.monotonic() - getattr(self, "_sleep_started", time.monotonic())
        cat = self.main_cat
        if away >= GIFT_AFTER and not self.all_hidden and cat.isVisible() and not self._gifts:
            gift = Gift(self, cat)
            self._gifts.add(gift)
            QTimer.singleShot(2200, lambda: cat.overlay.say(tr("say_gift"), 4000))

    def _refresh_tray_icon(self):
        if self.tray is None:
            return
        season = seasons.season() if self.seasonal else None
        if season != getattr(self, "_tray_season", None):
            self._tray_season = season
            self.tray.setIcon(pixel.tray_icon(season))

    def _weather_changed(self, kind):
        self.house.update_fx()
        rainy = kind in ("rain", "storm", "snow")
        if rainy and not self.sleeping and random.random() < 0.5:
            # 下雨天：沒事做的貓咪有一隻會想回家躲雨
            free = [c for c in self.cats if c.mode in ("idle", "random") and c.activity is None
                    and c.indoor is None and c.isVisible()]
            if free:
                c = random.choice(free)
                c.overlay.say(tr("say_rain"), 2600)
                QTimer.singleShot(1800, lambda: c in self.cats and c.go_home(self.house))

    def _pulse(self):
        now = time.monotonic()
        ph = seasons.phase()
        if ph != self._phase:                     # 換時段：貓屋重畫，動畫計時器跟著開關
            self._phase = ph
            self.house.update_fx()
            self._refresh_tray_icon()
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
                self._sleep_started = now - idle
                self.stop_toy()
                self.social.cuddle()
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
