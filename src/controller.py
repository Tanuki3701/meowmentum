"""管理所有貓咪，以及全域功能：番茄鐘、待辦清單、休息提醒、電量、睡覺、摸摸、餵食。"""
import random
import re
import shutil
import time

from PySide6.QtCore import QObject, QPoint, QProcess, QRect, QSettings, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

import i18n
import macos
import pixel
from cat import COLORS, Cat
from i18n import tr
from macos import show_on_all_spaces
from panels import Food, TodoPanel

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
        self.settings = QSettings("DesktopCat", "DesktopCat")
        s = self.settings
        self.tired = False
        i18n.set_lang(str(s.value("lang", "") or i18n.system_default()))

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
    def build_menu(self, cat, menu):
        pomo = menu.sub(QIcon(pixel.tomato(self._pomo_progress() if self.pomo_phase == "focus" else 1.0, pixel.MENU_UNIT)),
                        self._pomo_title())
        if self.pomo_phase:
            pomo.item("power", tr("pomo_stop"), self.stop_pomodoro)
            pomo.addSeparator()
        for m in (15, 25, 50):
            pomo.item(None, tr("focus_n", m=m), lambda m=m: self.start_focus(m)).setIcon(pixel.blank_icon())
        pomo.item("cup", tr("break_n", m=5), lambda: self.start_break(5))

        menu.item("note", tr("todo"), lambda: self.toggle_todo(cat))
        menu.item("can", tr("feed"), lambda: self.feed(cat))
        menu.addSeparator()
        cat.add_own_menus(menu)
        menu.addSeparator()
        menu.item(pixel.cat_head_icon("orange", plus=True), tr("add_cat"), lambda: self.add_cat(cat))
        if len(self.cats) > 1:
            menu.item("home", tr("remove_cat"), lambda: self.remove_cat(cat))
        settings = menu.sub("gear", tr("settings"))
        settings.sub(pixel.blank_icon(), tr("remind")).choices(
            {0: tr("off"), 30: tr("every_n", m=30), 45: tr("every_n", m=45), 60: tr("every_n", m=60)},
            self.remind_min, self.set_remind)
        settings.sub(pixel.blank_icon(), tr("nap_after")).choices(
            {0: tr("never"), 1: tr("n_min", m=1), 3: tr("n_min", m=3), 5: tr("n_min", m=5),
             10: tr("n_min", m=10)}, self.sleep_min, self.set_sleep_min)
        settings.item("check" if self.battery_alert else None, tr("battery_alert"),
                      lambda: self.set_battery_alert(not self.battery_alert))
        if not self.battery_alert:
            settings.actions()[-1].setIcon(pixel.blank_icon())
        menu.sub("globe", tr("language")).choices(i18n.LANGS, i18n.lang(), self.set_language)
        menu.addSeparator()
        menu.item("power", tr("quit"), self.quit)

    def set_language(self, lang):
        i18n.set_lang(lang)
        self.settings.setValue("lang", lang)
        self.todo.retranslate()

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
            self.start_break(5)
            r = cat.screen_rect()
            x = r.center().x() - cat.width() / 2

            def arrived():
                cat.spin(2)
                cat.overlay.say(tr("say_focus_done"), 6000)
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
    def feed(self, cat):
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

        food = Food(x, r.top(), r.bottom() + 1, max(2, cat.scale - 1), landed)
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
