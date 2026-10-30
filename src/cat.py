"""一隻桌面貓咪（每隻貓是一個剛好貓咪大小的小視窗）。

省電設計：
- 所有影格啟動時就切好、放大好並快取，畫面更新只是貼一張現成的圖。
- 計時器「需要時才開」：待著不動時沒有計時器；漫步走到定點會休息；
  跟隨模式在滑鼠旁、或站在視窗上休息時，改成低頻率檢查。
- 使用 CoarseTimer，讓 macOS 可以把喚醒合併在一起。
"""
import random
import time

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

import i18n
import interior
import pixel
import sprites
from glassmenu import GlassMenu
from i18n import tr
from overlay import Overlay

STAND_FRAME = 1
UP, RIGHT, DOWN, LEFT = 0, 1, 2, 3

COLORS = ["orange", "black", "white", "brown"]
DEFAULT_NAMES = {"en": ["Mochi", "Tofu", "Miso", "Latte", "Nori", "Pudding", "Sesame", "Biscuit"],
                 "zh": ["麻糬", "豆腐", "味噌", "拿鐵", "海苔", "布丁", "芝麻", "餅乾"]}
MODES = ["idle", "random", "follow", "windows", "dock", "sleep"]
DIRECTIONS = {DOWN: "dir_down", LEFT: "dir_left", RIGHT: "dir_right", UP: "dir_up"}
SIZES = [2, 3, 4]

MOVE_INTERVAL = 16       # 移動中約 60fps（距離依實際經過的時間計算，計時器晚到也不會頓）
TICK = 0.033             # 速度的單位：每 33ms 走幾點（以前的 30fps 單位）
ANIM_INTERVAL = 150      # 走路動畫換格速度
POLL_INTERVAL = 300      # 跟隨模式待命 / 站在視窗上休息時的檢查間隔
BREATH_INTERVAL = 1100   # 睡覺呼吸動畫
WANDER_SPEED = 4
FOLLOW_MAX_SPEED = 10
FOLLOW_DISTANCE = 50
REST_MS = (2000, 7000)


class Cat(QWidget):
    def __init__(self, ctrl, cid, color=None, near=None):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                            | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.ctrl = ctrl
        self.cid = cid
        self.prefix = f"cat{cid}/"
        self.color = color or self._pref("color", "orange")
        if self.color not in COLORS and self.color not in sprites.CUSTOM:
            self.color = "orange"
        self.mode = self._pref("mode", "idle")
        if self.mode not in MODES:
            self.mode = "idle"
        self.idle_direction = int(self._pref("idle_direction", DOWN))
        self.scale = int(self._pref("scale", 3))
        if self.scale not in SIZES:
            self.scale = 3
        self.name = str(self._pref("name", "") or "")
        self.hat = str(self._pref("hat", "") or "") or None
        self.neck = str(self._pref("neck", "") or "") or None
        self.love = int(self._pref("love", 0) or 0)       # 親密度 0~100
        self._last_love = 0.0
        self._clicks = []
        self._crossing = False
        self._waypoints = []
        self.toy = None           # 正在追的玩具
        self.spot = None          # 待在哪個家具裡／上（紙箱、貓跳台）
        self.indoor = None        # 在貓屋「裡面」看的時候：住在哪間貓屋
        self._indoor_kind = None
        self._fade_anim = None

        self.direction = self.idle_direction
        self.frame = STAND_FRAME
        self.walking = False
        self.activity = None      # None / sleep / fetch / eat / spin / jump / fall / drag
        self.target = None
        self.perch = None         # 站在哪個視窗上：dict(wid, left, top, right, a, b)
        self.fx = self.fy = 0.0
        self.vy = 0.0
        self._press = None
        self._then = None
        self._ticks = 0
        self._sleep_side = 0
        self._act_count = 0

        self.overlay = Overlay(self)

        self.move_timer = self._timer(self._tick)
        self.move_timer.setTimerType(Qt.PreciseTimer)   # 走路要順：移動用精準計時器
        self._last_tick = 0.0
        self._k = 1.0
        self.anim_timer = self._timer(self._next_frame)
        self.anim_timer.setInterval(ANIM_INTERVAL)
        self.act_timer = self._timer(self._act_step)
        self.fidget_timer = self._timer(self._idle_fidget)
        self.fidget_timer.setSingleShot(True)
        self.fidget_timer.start(random.randint(12_000, 30_000))
        self.rest_timer = self._timer(self._rest_done)
        self.rest_timer.setSingleShot(True)
        self.expression = None      # 表情：happy / excited / yuck / dizzy
        self._expr_side = 0
        self.expr_timer = self._timer(self._clear_expression)
        self.expr_timer.setSingleShot(True)
        self.indoor_timer = self._timer(self._indoor_wake)  # 在屋子裡睡多久
        self.indoor_timer.setSingleShot(True)
        self.spot_timer = self._timer(self.leave_spot)     # 在紙箱裡／貓跳台上待多久
        self.spot_timer.setSingleShot(True)
        self.hold_timer = self._timer(self._end_hold)   # 「愣住一下」之後才恢復原本的模式
        self.hold_timer.setSingleShot(True)
        self._hold_then = None

        self._build_frames()
        self._restore_position(near)
        self._apply_mode()

    def _timer(self, slot):
        t = QTimer(self)
        t.setTimerType(Qt.CoarseTimer)
        t.timeout.connect(slot)
        return t

    # ---------------- 設定 ---------------- #
    def _pref(self, key, default):
        s = self.ctrl.settings
        v = s.value(self.prefix + key)
        if v is None and self.cid == 0:
            v = s.value(key)  # 相容舊版（只有一隻貓時）的設定
        return default if v is None else v

    def _save(self, key, value):
        self.ctrl.settings.setValue(self.prefix + key, value)

    # ---------------- 影格與繪圖 ---------------- #
    def _build_frames(self):
        hat = self.hat if self.hat and self.ctrl.progress.has(self.hat) else None
        neck = self.neck if self.neck and self.ctrl.progress.has(self.neck) else None
        self.frames = sprites.cat_frames(self.color, self.scale, hat, neck)
        self.setFixedSize(sprites.FRAME_W * self.scale, sprites.FRAME_H * self.scale)
        self.update()

    def paintEvent(self, _e):
        style = getattr(self, "_sleep_style", "side")
        if self.activity == "sleep" and style in ("loaf", "belly"):
            pm = self.frames["pose"][style][self._sleep_side][self.frame % 2]
        elif self.activity == "fidget":
            pm = self.frames["pose"][self.pose][self._pose_side][self._pose_frame]
        elif self.activity == "sleep":
            pm = self.frames["sleep"][self._sleep_side][self.frame % 2]
        elif self.expression and not self.walking:
            pm = self.frames["expr"][self.expression][self._expr_side]
        else:
            pm = self.frames["walk"][self.direction][self.frame]
        QPainter(self).drawPixmap(0, 0, pm)

    def content_top(self):
        """貓咪頭頂在視窗裡的 y（給頭上的泡泡定位）。"""
        return (29 if self.activity == "sleep" else 20) * self.scale

    def foot_off(self):
        return sprites.FOOT_GAP * self.scale

    def _next_frame(self):
        self.frame = (self.frame + 1) % sprites.FRAMES_PER_DIR
        self.update()

    def moveEvent(self, e):
        self.overlay.follow()
        super().moveEvent(e)

    # ---------------- 位置工具 ---------------- #
    def screen_rect(self, point=None):
        point = point or self.geometry().center()
        screen = QGuiApplication.screenAt(point) or self.screen() or QGuiApplication.primaryScreen()
        return screen.availableGeometry()

    def ground_y(self):
        r = self.screen_rect()
        return r.bottom() + 1 - (self.height() - self.foot_off())

    def center_x(self):
        return self.x() + self.width() / 2

    def _clamp(self, x, y):
        r = self.screen_rect(QPoint(int(x) + self.width() // 2, int(y) + self.height() // 2))
        x = max(r.left(), min(x, r.right() - self.width() + 1))
        y = max(r.top(), min(y, r.bottom() - self.height() + 1 + self.foot_off()))
        return x, y

    def _move_to(self, x, y, clamp=True):
        if clamp:
            x, y = self._clamp(x, y)
        self.fx, self.fy = float(x), float(y)
        self.move(int(round(x)), int(round(y)))

    def _face(self, dx, dy=0):
        if abs(dx) > abs(dy):
            d = RIGHT if dx > 0 else LEFT
        else:
            d = DOWN if dy > 0 else UP
        if d != self.direction:
            self.direction = d
            self.update()

    def _speed(self, base):
        return base * (0.5 if self.ctrl.tired else 1.0)

    def _anim_ms(self):
        return ANIM_INTERVAL * (2 if self.ctrl.tired else 1)

    def _move_ms(self):
        return MOVE_INTERVAL

    def _gait(self, speed):
        """走路換格的速度跟著移動速度：走得快腳步就快，看起來不會滑行。"""
        if not self.walking or self.activity == "jump":
            return
        want = int(max(70, min(160, 560 / max(0.5, speed))))
        if abs(self.anim_timer.interval() - want) > 12:
            self.anim_timer.setInterval(want)

    # ---------------- 走路狀態 ---------------- #
    def _set_walking(self, walking, interval=MOVE_INTERVAL):
        if walking:
            self.move_timer.start(self._move_ms() if interval == MOVE_INTERVAL else interval)
            if not self.walking:
                self.anim_timer.start(self._anim_ms())
        else:
            self.anim_timer.stop()
            if self.mode == "follow" or (self.mode == "windows" and self.perch):
                self.move_timer.start(POLL_INTERVAL)
            else:
                self.move_timer.stop()
            self.frame = STAND_FRAME
            self.update()
        self.walking = walking

    def _stop_all(self):
        for t in (self.move_timer, self.anim_timer, self.rest_timer, self.act_timer):
            t.stop()
        self.walking = False
        self.frame = STAND_FRAME

    def refresh_speed(self):
        if self.walking:
            self.anim_timer.start(self._anim_ms())


    def _apply_mode(self):
        if self.indoor is not None:
            self._stop_all()
            self.activity = None
            self._indoor_next()
            return
        if self.spot is not None and self.spot.kind == "tree" and self.spot_timer.isActive():
            self._stop_all()                       # 還在貓跳台上：醒來後繼續坐著
            self.activity = "tree"
            self.direction = DOWN
            self.update()
            return
        self._stop_all()
        self.activity = None
        self.fx, self.fy = float(self.x()), float(self.y())
        if self.mode != "windows":
            self.perch = None
        if self.mode == "idle":
            self.direction = self.idle_direction
        elif self.mode == "random":
            self._start_wandering()
        elif self.mode == "follow":
            self._set_walking(False)
        elif self.mode == "windows":
            self._set_walking(False)
            self.rest_timer.start(600)
        elif self.mode == "dock":
            if self._on_ground():
                self._dock_next()
            else:
                self.start_fall()
        elif self.mode == "sleep":
            self.sleep()
        self.update()

    def _resume(self):
        self._apply_mode()

    def _rest_done(self):
        if self.activity is not None or self.indoor is not None:
            return
        if self.mode == "random":
            self._start_wandering()
        elif self.mode == "windows":
            self._windows_next()
        elif self.mode == "dock":
            self._dock_next()

    def _dock_next(self):
        """在 Dock 上來回散步：每次走到 Dock 範圍內的隨機一點，休息一下再走。"""
        a, b = self.ctrl.dock_span(self)
        self.target = (random.uniform(a, b), self.ground_y())
        self._set_walking(True)

    def _start_wandering(self):
        r = self.screen_rect()
        screens = [sc.availableGeometry() for sc in QGuiApplication.screens()]
        others = [g for g in screens if g != r]
        if others and random.random() < 0.2:
            # 多螢幕：偶爾散步到另一個螢幕（先走到兩個螢幕相接的邊，再走過去）
            g = random.choice(others)
            tx = random.randint(g.left(), max(g.left(), g.right() - self.width()))
            ty = random.randint(g.top(), max(g.top(), g.bottom() - self.height()))
            lo = max(r.top(), g.top())
            hi = min(r.bottom(), g.bottom()) - self.height()
            if hi > lo:
                ey = max(lo, min(hi, self.y()))
                ex = r.right() - self.width() if g.left() >= r.right() else r.left()
                self._waypoints = [(tx, ty)]
                self.target = (ex, ey)
                self._set_walking(True)
                return
        self._waypoints = []
        self.target = (random.randint(r.left(), max(r.left(), r.right() - self.width())),
                       random.randint(r.top(), max(r.top(), r.bottom() - self.height())))
        self._set_walking(True)

    # ---------------- 每一步 ---------------- #
    def _tick(self):
        now = time.monotonic()
        dt = now - self._last_tick
        self._last_tick = now
        self._k = dt / TICK if 0 < dt < 0.1 else MOVE_INTERVAL / 1000 / TICK
        a = self.activity
        if a == "drag":
            return
        if a == "fetch":
            self._fetch_step()
        elif a == "jump":
            self._jump_step()
        elif a == "fall":
            self._fall_step()
        elif a == "zoom":
            self._zoom_step()
        elif a == "play":
            self._play_step()
        elif a is None:
            if self.mode in ("random", "dock"):
                self._wander_step()
            elif self.mode == "follow":
                self._follow_step()
            elif self.mode == "windows":
                self._windows_step()

    def _step_towards(self, tx, ty, speed):
        self._gait(speed)
        speed *= self._k
        dx, dy = tx - self.fx, ty - self.fy
        if abs(dx) <= speed and abs(dy) <= speed:
            self._move_to(tx, ty, clamp=self.mode != "windows" and not self._crossing)
            self._crossing = False
            return True
        self._face(dx, dy)
        sx = max(-speed, min(speed, dx))
        sy = max(-speed, min(speed, dy))
        before = (self.fx, self.fy)
        self._move_to(self.fx + sx, self.fy + sy, clamp=self.mode != "windows" and not self._crossing)
        if abs(self.fx - before[0]) < 0.01 and abs(self.fy - before[1]) < 0.01:
            return True                    # 被螢幕邊緣擋住、走不過去：就當作到了
        return False

    def _wander_step(self):
        if self._step_towards(*self.target, self._speed(WANDER_SPEED)):
            if self.mode == "random" and getattr(self, "_waypoints", None):
                # 跨到另一個螢幕：暫時不夾在原本的螢幕裡
                self.target = self._waypoints.pop(0)
                self._crossing = True
                return
            self._set_walking(False)
            self.rest_timer.start(random.randint(*REST_MS))

    def _follow_step(self):
        cursor = QCursor.pos()
        dx = cursor.x() - self.width() // 2 - self.x()
        dy = cursor.y() - self.height() // 2 - self.y()
        if (dx * dx + dy * dy) ** 0.5 < FOLLOW_DISTANCE:
            if self.walking:
                self._set_walking(False)
            return
        if not self.walking:
            self._set_walking(True)
        top = self._speed(FOLLOW_MAX_SPEED) * self._k
        f = min(1.0, 0.1 * self._k)
        sx = max(-top, min(top, dx * f))
        sy = max(-top, min(top, dy * f))
        self._face(dx, dy)
        self._move_to(self.fx + sx, self.fy + sy)

    # ---------------- 在視窗上走 ---------------- #
    def _perch_cat_y(self, top):
        return top - (self.height() - self.foot_off())

    def _on_ground(self):
        return self.perch is None and abs(self.y() - self.ground_y()) <= 3

    def _windows_next(self):
        if self.perch is None and not self._on_ground():
            self.start_fall()
            return
        segs = self.ctrl.top_segments(self)
        if self.perch:
            segs = [s for s in segs if s["wid"] != self.perch["wid"]] or segs
        if segs and random.random() < 0.7:
            seg = random.choice(segs)
            cx = random.uniform(seg["a"], seg["b"])
            self.jump_to(cx - self.width() / 2, self._perch_cat_y(seg["top"]), seg)
            return
        # 沿著現在站的地方走一段
        if self.perch:
            a, b = self.perch["a"], self.perch["b"]
            y = self._perch_cat_y(self.perch["top"])
        else:
            r = self.screen_rect()
            a, b = r.left() + self.width() / 2, r.right() - self.width() / 2
            y = self.ground_y()
        self.target = (random.uniform(a, b) - self.width() / 2, y)
        self._set_walking(True)

    def _windows_step(self):
        self._ticks += 1
        if self.perch and (not self.walking or self._ticks % 8 == 0):
            if not self._verify_perch():
                return
        if self.walking and self.target:
            tx, ty = self.target
            if self._step_towards(tx, ty, self._speed(WANDER_SPEED)):
                self._set_walking(False)
                self.rest_timer.start(random.randint(1500, 5000))

    def _verify_perch(self):
        """確認腳下的視窗還在；視窗被拖動就跟著移動，視窗不見了就掉下去。"""
        p = self.perch
        rect = None
        for wid, r in self.ctrl.windows():
            if wid == p["wid"]:
                rect = r
                break
        if rect is None:
            self.start_fall()
            return False
        dx, dy = rect.left() - p["left"], rect.top() - p["top"]
        if dx or dy:
            p.update(left=rect.left(), top=rect.top(), right=rect.right(),
                     a=p["a"] + dx, b=p["b"] + dx)
            self._move_to(self.fx + dx, self.fy + dy, clamp=False)
            if self.target:
                self.target = (self.target[0] + dx, self.target[1] + dy)
            if not self.walking:
                self.move_timer.start(MOVE_INTERVAL)  # 視窗在動：暫時提高檢查頻率
        elif not self.walking and self.move_timer.interval() != POLL_INTERVAL:
            self.move_timer.start(POLL_INTERVAL)
        cx = self.center_x()
        if not (rect.left() <= cx <= rect.right()):
            self.start_fall()
            return False
        return True

    def jump_to(self, x, y, perch, then=None):
        self._stop_all()
        self._jump_then = then
        self.activity = "jump"
        self._j0 = (self.fx, self.fy)
        self._j1 = (x, y)
        dist = ((x - self.fx) ** 2 + (y - self.fy) ** 2) ** 0.5
        self._jn = max(10, int(dist / 14))
        self._jt = 0
        self._arc = max(50, (self.fy - y) / 2 + 45)
        self._jump_perch = perch
        self.perch = None
        self._face(x - self.fx)
        self.walking = True
        self.anim_timer.start(ANIM_INTERVAL // 2)
        self.move_timer.start(MOVE_INTERVAL)

    def _jump_step(self):
        self._jt += self._k
        t = min(1.0, self._jt / self._jn)
        (x0, y0), (x1, y1) = self._j0, self._j1
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t - self._arc * 4 * t * (1 - t)
        self._move_to(x, y, clamp=False)
        if t >= 1:
            self.activity = None
            if self._jump_then:
                then, self._jump_then = self._jump_then, None
                self._stop_all()
                then()
                return
            self.perch = self._jump_perch
            self._set_walking(False)
            if self.perch and not self._verify_perch():
                return
            self.rest_timer.start(random.randint(1500, 5000))

    def start_fall(self):
        self._stop_all()
        self.activity = "fall"
        self.perch = None
        self.vy = 0.0
        self.fx, self.fy = float(self.x()), float(self.y())
        self._fall_segs = self.ctrl.top_segments(self) if self.mode == "windows" else []
        self.update()
        self.move_timer.start(MOVE_INTERVAL)

    def _fall_step(self):
        self.vy = min(self.vy + 1.5 * self._k, 28)
        ny = self.fy + self.vy * self._k
        foot = self.height() - self.foot_off()
        prev_feet, new_feet = self.fy + foot, ny + foot
        cx = self.center_x()
        for seg in self._fall_segs:
            if seg["a"] <= cx <= seg["b"] and prev_feet <= seg["top"] <= new_feet:
                self.perch = seg
                self._move_to(self.fx, self._perch_cat_y(seg["top"]), clamp=False)
                self._landed()
                return
        gy = self.ground_y()
        if ny >= gy:
            self._move_to(self.fx, gy, clamp=False)
            self._landed()
            return
        self._move_to(self.fx, ny, clamp=False)

    def _landed(self):
        self.activity = None
        self.vy = 0
        if self.mode == "windows" and self.indoor is None:
            self._set_walking(False)
            self.rest_timer.start(random.randint(800, 2500))
        else:
            self._resume()

    # ---------------- 特別動作 ---------------- #
    def go_to(self, x, y, then=None, speed=7, keep_indoor=False):
        if self.indoor is not None and not keep_indoor:
            self._leave_indoor_silent()
        if self.activity == "home":
            self._exit_home()
        self._drop_spot()
        if self.activity == "sleep":
            self.wake(quiet=True, force=True)
        self._stop_all()
        self.activity = "fetch"
        self.perch = None
        self.fx, self.fy = float(self.x()), float(self.y())
        self.target = (x, y)
        self._then = then
        self._fetch_speed = speed
        self._set_walking(True)

    def _fetch_step(self):
        if self._step_towards(*self.target, self._speed(self._fetch_speed)):
            self._stop_all()
            self.activity = None
            then, self._then = self._then, None
            if then:
                then()
            else:
                self._resume()

    def eat(self, food):
        self._stop_all()
        self.activity = "eat"
        self.expression = None
        self._food = food
        self._face(food.center_x() - self.center_x())
        self._act_count = 0
        self.act_timer.start(260)

    def spin(self, rounds=2):
        if self.activity in ("home", "box", "tree"):
            self.overlay.burst("heart", 3)
            return
        if self.activity == "sleep":
            self.wake(quiet=True, force=True)
        if self.activity is not None:
            self.overlay.burst("heart", 3)
            return
        self._stop_all()
        self.activity = "spin"
        self._act_count = 0
        self._spin_total = 4 * rounds
        self.act_timer.start(110)

    def sleep(self):
        if self.activity == "tree":
            self.activity = None          # 在貓跳台上直接睡（spot 保留，醒來繼續坐著）
        if self.activity is not None:
            return
        self._stop_all()
        self.activity = "sleep"
        self._sleep_side = 1 if self.direction == LEFT else 0
        self._sleep_style = random.choice(("side", "side", "loaf", "belly"))   # 側躺、麻糬、肚子朝上
        self.frame = 0
        self._act_count = 0
        self.act_timer.start(BREATH_INTERVAL)
        self.update()
        self.overlay.follow()

    def wake(self, quiet=False, force=False):
        """叫醒貓咪。睡覺模式下只有 force=True（拖曳、換模式等）才會真的醒來。"""
        if self.activity != "sleep" or (self.mode == "sleep" and not force):
            return
        self.act_timer.stop()
        self.direction = LEFT if self._sleep_side else RIGHT
        self.activity = None
        self.frame = STAND_FRAME
        self.update()
        if not quiet:
            self.overlay.say(tr("say_morning"), 2000)
        self._resume()

    # ---------------- 小動作：坐著甩尾巴、洗臉、打哈欠、伸懶腰、追尾巴 ---------------- #
    FIDGETS = {"sit": (16, 300), "wash": (12, 260), "yawn": (6, 320), "stretch": (7, 320)}

    def fidget(self, kind=None):
        if self.activity is not None or self.ctrl.all_hidden:
            return False
        kind = kind or random.choice(["sit", "sit", "wash", "yawn", "stretch", "chase"])
        if kind == "chase":                      # 追自己的尾巴：轉圈圈
            self.spin(3)
            self.overlay.burst("sparkle", 1)
            return True
        self._stop_all()
        self.activity = "fidget"
        self.pose = kind
        self._pose_side = 1 if self.direction == LEFT else (0 if self.direction == RIGHT else random.randint(0, 1))
        self._pose_frame = 0
        self._act_count = 0
        self.act_timer.start(self.FIDGETS[kind][1])
        self.update()
        return True

    def _fidget_step(self, n):
        steps, _ms = self.FIDGETS[self.pose]
        if self.pose == "sit":
            self._pose_frame = 1 if n % 5 in (2, 3) else 0          # 尾巴尖甩一下
        elif self.pose == "wash":
            self._pose_frame = n % 2
        self.update()
        if n >= steps:
            self.act_timer.stop()
            self.activity = None
            self.direction = LEFT if self._pose_side else RIGHT
            self._resume()

    def _idle_fidget(self):
        """待著不動或休息時，偶爾做個小動作；很親的貓偶爾會走過來蹭蹭游標。"""
        if self.mode in ("idle", "random") and self.activity is None and not self.walking \
                and self.isVisible() and not self.ctrl.sleeping:
            if self.love >= 60 and random.random() < 0.25 and self.rub_cursor():
                pass
            else:
                self.fidget()
        if self.mode in ("idle", "random"):
            self.fidget_timer.start(random.randint(18_000, 45_000))

    # ---------------- 親密度 ---------------- #
    def love_level(self):
        return min(5, self.love // 20)

    def add_love(self, n, why=None):
        before = self.love_level()
        self.love = max(0, min(100, self.love + n))
        self._save("love", self.love)
        if self.love_level() > before:
            self.overlay.say(tr("say_love_up", n=self.love_level()), 2600)
            self.overlay.burst("heart", 4)
        self.ctrl.check_badges()

    def show_love(self):
        self.overlay.say(tr("say_love", n=self.love_level()), 3200)
        self.overlay.burst("heart", 1 + self.love_level())

    def rub_cursor(self):
        """親密度高的貓：偶爾自己走過來蹭蹭游標。"""
        if self.activity is not None or self.indoor is not None or self.mode not in ("idle", "random"):
            return False
        pos = QCursor.pos()
        r = self.screen_rect()
        if not r.contains(pos):
            return False
        tx = max(r.left(), min(r.right() - self.width(), pos.x() - self.width() / 2))

        def arrived():
            self.show_expression("happy", 2600)
            self.overlay.say(tr("say_rub"), 2200)
            self.overlay.burst("heart", 3)
            self.hold(2600)
        self.go_to(tx, self.ground_y(), then=arrived, speed=4)
        return True

    def petted(self):
        self.overlay.burst("heart", 3)
        self.ctrl.progress.note("pet")
        if time.monotonic() - self._last_love > 8:
            self._last_love = time.monotonic()
            self.add_love(1)
        if self.activity != "sleep":
            self.overlay.say(random.choice(tr("say_pet")), 1800)

    def _act_step(self):
        self._act_count += 1
        n = self._act_count
        if self.activity == "sleep":
            self.frame ^= 1
            self.update()
            if n % 2 == 0:
                self.overlay.zzz()
            if self.perch and n % 3 == 0:
                for wid, _ in self.ctrl.windows():
                    if wid == self.perch["wid"]:
                        break
                else:
                    self.wake(quiet=True, force=True)
                    self.start_fall()
        elif self.activity == "fidget":
            self._fidget_step(n)
        elif self.activity == "spin":
            self.direction = (DOWN, RIGHT, UP, LEFT)[n % 4]
            self.update()
            if n >= self._spin_total:
                self.act_timer.stop()
                self.activity = None
                self.direction = DOWN
                self._resume()
        elif self.activity == "eat":
            self.frame = 0 if n % 2 else 2
            self.update()
            if n % 3 == 0:
                self.overlay.burst("heart", 1)
            if n >= 10:
                self.act_timer.stop()
                flavor = getattr(self._food, "flavor", "tuna")
                self._food.close()
                self._food = None
                self.activity = None
                self._react(flavor)

    # ---------------- 表情與吃罐罐的反應 ---------------- #
    def show_expression(self, name, ms=2500):
        if self.direction == LEFT:
            self._expr_side = 1
        elif self.direction == RIGHT:
            self._expr_side = 0
        self.expression = name
        self.expr_timer.start(ms)
        self.update()

    def _clear_expression(self):
        self.expression = None
        self.update()

    def hold(self, ms, then=None):
        """原地愣住一下（表情會顯示），之後恢復原本的模式。"""
        self._stop_all()
        self.activity = "hold"
        self._hold_then = then
        self.hold_timer.start(ms)
        self.update()

    def _end_hold(self):
        if self.activity != "hold":
            return
        self.activity = None
        then, self._hold_then = self._hold_then, None
        if then:
            then()
        else:
            self._resume()

    def _react(self, flavor):
        """不同口味的罐罐，貓咪有不同反應。"""
        ov = self.overlay
        if flavor == "bowl":                 # 在家裡吃自己碗裡的飯
            self.show_expression("happy", 2200)
            ov.burst("heart", 2)
            self.hold(2200)
            return
        self.ctrl.progress.note("can")
        self.ctrl.progress.try_flavor(flavor)
        self.add_love(2)
        if flavor == "chicken":
            self.show_expression("happy", 3000)
            ov.say(tr("react_chicken"), 3000)
            ov.burst("note", 4)
            self.hold(3000)
        elif flavor == "salmon":
            self.show_expression("excited", 3800)
            ov.say(tr("react_salmon"), 3500)
            ov.burst("sparkle", 5)
            x, y = self.fx, self.fy
            self.jump_to(x, y, None, then=lambda: (ov.burst("sparkle", 3), self.hold(2200)))
            self._arc = 70
        elif flavor == "catnip":
            ov.say(tr("react_catnip"), 3000)
            self._start_zoomies()
        elif flavor == "bitter":
            self.show_expression("yuck", 2600)
            ov.say(tr("react_bitter"), 3000)
            ov.burst("sweat", 2)
            back = -1 if self._expr_side == 0 else 1
            r = self.screen_rect()
            tx = max(r.left(), min(r.right() - self.width(), self.x() + back * 180))
            self.hold(1400, then=lambda: self.go_to(tx, self.y(), then=self._resume, speed=4))
        else:   # tuna
            self.show_expression("happy", 2500)
            ov.say(tr("react_tuna"), 2500)
            ov.burst("heart", 4)
            self.hold(2500)

    def _start_zoomies(self):
        """貓薄荷：在螢幕底部瘋狂衝刺 4 秒，然後頭暈。"""
        self._stop_all()
        self.activity = "zoom"
        self.perch = None
        self.fx, self.fy = float(self.x()), float(self.y())
        self._zoom_until = time.monotonic() + 4.0
        self.target = None
        self.walking = True
        self.anim_timer.start(60)
        self.move_timer.start(MOVE_INTERVAL)

    def _zoom_step(self):
        if time.monotonic() >= self._zoom_until:
            self._stop_all()
            self.activity = None
            self.show_expression("dizzy", 2600)
            self.overlay.say(tr("react_dizzy"), 2500)
            self.overlay.burst("sparkle", 3)
            self.hold(2600)
            return
        if self.target is None:
            r = self.screen_rect()
            self.target = (random.uniform(r.left(), r.right() - self.width()), self.ground_y())
        if self._step_towards(*self.target, 15):
            self.target = None

    # ---------------- 淡入淡出 ---------------- #
    def _fade(self, value, ms=260, done=None):
        from PySide6.QtCore import QEasingCurve, QPropertyAnimation
        if self._fade_anim is not None:
            self._fade_anim.stop()
        a = QPropertyAnimation(self, b"windowOpacity", self)
        a.setDuration(ms)
        a.setStartValue(self.windowOpacity())
        a.setEndValue(value)
        a.setEasingCurve(QEasingCurve.InOutQuad)
        if done:
            a.finished.connect(done)
        a.start()
        self._fade_anim = a

    # ---------------- 回家 ---------------- #
    def go_home(self, house):
        if self.activity in ("home", "entering") or self.indoor is not None:
            return
        x, y = house.door_cat_pos(self)
        self.go_to(x, y, then=lambda: self._enter_home(house), speed=6)

    def _enter_home(self, house):
        """走到門口：門打開，貓咪轉身走進去慢慢消失。"""
        self._stop_all()
        self.activity = "entering"
        self.expression = None
        house.open_door()
        self.direction = UP
        self.walking = True
        self.anim_timer.start(ANIM_INTERVAL)
        self.update()

        def gone():
            self.anim_timer.stop()
            self.walking = False
            self.hide()
            self.overlay.hide()
            self.setWindowOpacity(1.0)
            self.activity = "home"
            house.add(self)
            if house.is_interior():
                self.enter_indoor(house, from_door=True)
        self._fade(0.0, 300, gone)

    def _exit_home(self):
        """馬上出來（換模式、被叫去做別的事時）。"""
        house = self.ctrl.house
        house.remove(self)
        x, y = house.door_cat_pos(self)
        self.activity = None
        self._move_to(x, y, clamp=False)
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()

    def leave_home(self):
        if self.indoor is not None:
            house = self.indoor
            x = house.indoor_spot_x(self, "door")
            self.go_to(x, house.indoor_floor_y(self), then=lambda: self._exit_indoor(house),
                       speed=5, keep_indoor=True)
            return
        if self.activity != "home":
            return
        self._walk_out(self.ctrl.house)

    def _walk_out(self, house):
        """門打開，貓咪從門口慢慢出現，再走出來幾步。"""
        house.open_door()
        x, y = house.door_cat_pos(self)
        self.activity = "entering"
        self._move_to(x, y, clamp=False)
        self.direction = DOWN
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.update()

        def shown():
            house.remove(self)
            self.activity = None
            self.overlay.say(tr("say_hello"), 1800)
            side = random.choice((-1, 1))
            self.go_to(x + side * self.width() * 0.7, y, then=self._resume, speed=3)
        self._fade(1.0, 300, shown)

    # ---------------- 在貓屋裡面 ---------------- #
    def use_room_scale(self, unit):
        """在房間裡：貓咪換成和房間一樣的像素大小（不會改到自己的大小設定）。"""
        unit = unit if unit else int(self._pref("scale", 3))
        if unit != self.scale:
            self.scale = unit
            self._build_frames()

    def _restore_scale(self):
        saved = int(self._pref("scale", 3))
        if self.scale != saved:
            self.scale = saved
            self._build_frames()

    def enter_indoor(self, house, from_door=False):
        """貓屋換成「裡面」的樣子：在家的貓咪出現在房間裡，可以點、拖、按右鍵。"""
        self._stop_all()
        self.indoor = house
        self._restore_scale()
        self.activity = None
        self.expression = None
        lo, hi = house.indoor_x_range(self)
        x = house.indoor_spot_x(self, "door") if from_door else random.uniform(lo, hi)
        self._move_to(x, house.indoor_floor_y(self), clamp=False)
        self.direction = DOWN
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.update()
        self._fade(1.0, 320, lambda: self.indoor is house and self._resume())

    def indoor_to_home(self, house):
        """貓屋換回「外面」的樣子：房間裡的貓咪回到看不見的家裡。"""
        self._stop_all()
        self.indoor_timer.stop()
        self.indoor = None
        self._indoor_kind = None
        if self.activity == "sleep":
            self.act_timer.stop()
        self._restore_scale()
        self.activity = "home"
        self.expression = None
        self.hide()
        self.overlay.hide()
        self.setWindowOpacity(1.0)

    def _exit_indoor(self, house):
        """從房間的門走出去：在門口慢慢消失，再從屋外出現。"""
        self._stop_all()
        self.activity = "entering"
        self.direction = UP

        def outside():
            self.indoor = None
            self.hide()
            self._restore_scale()
            self._walk_out(house)
        self._fade(0.0, 260, outside)

    def _leave_indoor_silent(self):
        house, self.indoor = self.indoor, None
        self.indoor_timer.stop()
        self._indoor_kind = None
        if house is not None:
            bottom = self.y() + self.height()
            self._restore_scale()
            self._move_to(self.x(), bottom - self.height(), clamp=False)
        if house is not None:
            house.remove(self)

    def _indoor_next(self):
        house = self.indoor
        if house is None or not house.is_interior():
            return
        y = house.indoor_floor_y(self)
        lo, hi = house.indoor_x_range(self)
        others = [c for c in house.residents if c is not self and c.indoor is house]
        attic = house.view == "attic"
        kinds = ["walk", "walk", "walk", "walk", "sit", "sit", "sleep"]
        kinds += ["play", "play"] if attic else ["eat", "eat"]
        if attic and "kotatsu" in self.ctrl.progress.owned:
            kinds += ["kotatsu"]
        awake = [c for c in others if c.activity in (None, "hold") and c._indoor_kind in ("sit", "walk", None)]
        if awake:
            kinds += ["groom", "groom"]                    # 幫房間裡的朋友理毛
        if self.ctrl.sleeping:
            kinds = ["sleep"]
        k = random.choice(kinds)
        sleeper = next((c for c in others if c._indoor_kind in ("sleep", "cuddle") and c.activity == "sleep"), None)
        if k == "sleep" and sleeper is not None:
            k = "cuddle"                                   # 有朋友在床上睡：擠過去一起睡
        if k == "eat" and any(c._indoor_kind == "eat" for c in others):
            k = "walk"
        if k == "kotatsu" and any(c._indoor_kind == "kotatsu" for c in others):
            k = "sleep" if sleeper is None else "cuddle"
        self._indoor_kind = k
        if k == "walk":
            self.go_to(random.uniform(lo, hi), y, then=lambda: self.hold(random.randint(1200, 3500)),
                       speed=2.6, keep_indoor=True)
        elif k == "sit":
            self.direction = random.choice((LEFT, RIGHT))
            if not self.fidget(random.choice(["sit", "sit", "wash", "yawn", "stretch"])):
                self.hold(random.randint(2500, 6000))
        elif k == "sleep":
            self.go_to(house.indoor_spot_x(self, "cushion"), y, then=self._indoor_sleep, speed=2.6,
                       keep_indoor=True)
        elif k == "cuddle":
            side = random.choice((-1, 1))
            tx = sleeper.x() + side * sleeper.width() * 0.42
            tx = max(lo - self.width() * 0.2, min(hi + self.width() * 0.2, tx))
            self.go_to(tx, y, then=lambda: self._indoor_cuddle(sleeper), speed=2.6, keep_indoor=True)
        elif k == "kotatsu":
            self.go_to(house.indoor_spot_x(self, "kotatsu"), y, then=self._indoor_sleep, speed=2.6,
                       keep_indoor=True)
        elif k == "groom":
            friend = random.choice(awake)
            friend._stop_all()
            friend._indoor_kind = "groomed"
            friend.hold(9000)
            side = -1 if self.center_x() < friend.center_x() else 1
            tx = friend.x() + side * friend.width() * 0.55
            tx = max(lo, min(hi, tx))
            self.go_to(tx, y, then=lambda: self._indoor_groom(friend), speed=3, keep_indoor=True)
        elif k == "play":
            self.go_to(house.indoor_spot_x(self, "cushion") if not attic else
                       house._gx(sum(interior.A_TOYS) / 2) - self.width() * 0.75, y,
                       then=self._indoor_play, speed=3.4, keep_indoor=True)
        else:
            self.go_to(house.indoor_spot_x(self, "bowl"), y, then=self._indoor_eat, speed=3,
                       keep_indoor=True)

    def _indoor_cuddle(self, friend):
        """擠在朋友旁邊睡，臉朝向對方。"""
        self.direction = RIGHT if self.center_x() < friend.center_x() else LEFT
        self.sleep()
        self.overlay.burst("heart", 1)
        self.indoor_timer.start(random.randint(16_000, 34_000))

    def _indoor_groom(self, friend):
        if friend.indoor is not self.indoor:
            self._resume()
            return
        self.direction = RIGHT if self.center_x() < friend.center_x() else LEFT
        friend.direction = LEFT if self.direction == RIGHT else RIGHT
        friend.update()
        self.show_expression("happy", 3200)
        friend.show_expression("happy", 3200)
        self.overlay.burst("heart", 2)
        self.ctrl.progress.note("groom")
        self.add_love(1)
        friend.add_love(1)
        QTimer.singleShot(1200, lambda: friend.indoor is not None and friend.overlay.say(
            random.choice(tr("say_groom")), 2400))
        QTimer.singleShot(1500, lambda: friend.indoor is not None and friend.overlay.burst("heart", 2))
        self.hold(3800)
        QTimer.singleShot(4200, lambda: friend.indoor is not None and friend.activity == "hold"
                          and friend._resume())

    def _indoor_play(self):
        """在閣樓的玩具箱旁邊玩：跳一下、興奮一下。"""
        self.direction = RIGHT
        self.show_expression("excited", 2200)
        self.overlay.burst("sparkle", 2)
        self.hold(2600)

    def _indoor_sleep(self):
        self.direction = random.choice((LEFT, RIGHT))
        self.sleep()
        self.indoor_timer.start(random.randint(14_000, 32_000))

    def _indoor_wake(self):
        if self.activity == "sleep" and self.indoor is not None and not self.ctrl.sleeping:
            self.wake(quiet=True, force=True)

    def _indoor_eat(self):
        house = self.indoor

        class _Bowl:
            flavor = "bowl"

            def center_x(_self):
                return house._gx(sum(interior.BOWL_X) / 2)

            def close(_self):
                pass
        self.eat(_Bowl())

    # ---------------- 滑鼠：點擊、拖曳 ---------------- #
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            gp = e.globalPosition().toPoint()
            self._press = (gp, gp - self.pos())

    def mouseMoveEvent(self, e):
        if not self._press:
            return
        gp = e.globalPosition().toPoint()
        if self.activity != "drag":
            if (gp - self._press[0]).manhattanLength() < 5:
                return
            if self.activity == "sleep":
                self.wake(quiet=True, force=True)
            self._drop_spot()
            self.toy = None
            if self.activity == "eat" and getattr(self, "_food", None):
                self._food.close()
                self._food = None
            self._stop_all()
            self.activity = "drag"
            self.perch = None
            self.direction = DOWN
            self.update()
        self.move(gp - self._press[1])

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self._press:
            return
        self._press = None
        if self.activity == "drag" and self._drop_on_house():
            return
        if self.activity == "drag" and self.indoor is not None:
            self._leave_indoor_silent()                # 被拖到屋子外面：就出門了
        if self.activity == "drag":
            self.activity = None
            x, _ = self._clamp(self.x(), self.y())
            self._move_to(x, self.y(), clamp=False)
            self.save_pos()
            if self.mode in ("windows", "dock"):
                self.start_fall()
            else:
                self._move_to(*self._clamp(self.x(), self.y()))
                self._resume()
        elif self.activity == "sleep":
            if self.mode == "sleep":
                self.overlay.burst("heart", 2)   # 睡覺模式：摸摸頭，繼續睡
            else:
                self.wake()
                self.overlay.burst("heart", 2)
        else:
            self.overlay.burst("heart", 1)   # 左鍵只是摸摸，功能一律從右鍵選單
            now = time.monotonic()
            self._clicks = [t for t in self._clicks if now - t < 3] + [now]
            if len(self._clicks) >= 5:
                self._clicks = []
                self.annoyed()

    def _drop_on_house(self):
        """把貓咪拖到貓屋上放開：看外面時就回家，看裡面時就住進房間。"""
        house = self.ctrl.house
        if not house.isVisible():
            return False
        feet = QPoint(int(self.center_x()), int(self.y() + self.height() - self.foot_off() - 6))
        if house.is_interior() and house.room_contains(feet):
            if self.indoor is not house:
                self._leave_indoor_silent()
                self._drop_spot()
                house.add(self)
            self.indoor = house
            self.activity = None
            lo, hi = house.indoor_x_range(self)
            self._move_to(max(lo, min(hi, self.x())), house.indoor_floor_y(self), clamp=False)
            self.overlay.burst("heart", 1)
            self._resume()
            house.raise_residents()
            return True
        if not house.is_interior() and house.body_contains(feet):
            self._drop_spot()
            self.activity = None
            x, y = house.door_cat_pos(self)
            self._move_to(x, y, clamp=False)
            self._enter_home(house)
            return True
        return False

    def contextMenuEvent(self, e):
        menu = GlassMenu()
        self.ctrl.build_menu(self, menu)
        menu.exec(e.globalPos())

    def add_own_menus(self, menu):
        menu.sub("paw", tr("mode")).choices(
            {m: tr("mode_" + m) for m in MODES}, self.mode, self.set_mode)
        colors = {c: tr("color_" + c) for c in COLORS}
        colors.update(self.ctrl.custom_color_names())
        cm = menu.sub(pixel.cat_head_icon(self.color), tr("color"))
        cm.choices(colors, self.color, self.set_color,
                   icons={c: pixel.cat_head_icon(c) for c in colors},
                   checked_icons={c: pixel.cat_head_icon(c, check=True) for c in colors})
        cm.addSeparator()
        cm.item("palette", tr("palette"), lambda: self.ctrl.open_palette(self))
        look = menu.sub("crown", tr("accessories"))
        hats = {None: tr("acc_none")}
        hats.update({h: tr("item_" + h) for h in self.ctrl.progress.owned_of("hat")})
        look.sub("crown", tr("acc_hat")).choices(hats, self.hat, self.set_hat)
        necks = {None: tr("acc_none")}
        necks.update({n: tr("item_" + n) for n in self.ctrl.progress.owned_of("neck")})
        look.sub("dot", tr("acc_neck")).choices(necks, self.neck, self.set_neck)
        look.addSeparator()
        look.item("shop", tr("shop"), lambda: self.ctrl.open_shop(self))
        menu.item("name", tr("name_cat", n=self.display_name()), lambda: self.ctrl.rename(self))
        lv = self.love_level()
        menu.item("heart", tr("love_level", h="♥" * lv + "♡" * (5 - lv)), self.show_love)
        menu.sub("facing", tr("facing")).choices(
            {d: tr(k) for d, k in DIRECTIONS.items()}, self.idle_direction, self.set_idle_direction)
        menu.sub("size", tr("size")).choices(
            {z: tr(f"size_{z}") for z in SIZES}, int(self._pref("scale", 3)), self.set_scale)

    # ---------------- 名字、飾品、生氣 ---------------- #
    def display_name(self):
        if self.name:
            return self.name
        names = DEFAULT_NAMES[i18n.lang()]
        return names[self.cid % len(names)]

    def set_name(self, name):
        self.name = name.strip()[:16]
        self._save("name", self.name)

    def set_hat(self, hat):
        self.hat = hat
        self._save("hat", hat or "")
        self._build_frames()

    def set_neck(self, neck):
        self.neck = neck
        self._save("neck", neck or "")
        self._build_frames()

    def annoyed(self):
        """被連續戳太多次：皺眉、冒汗，走開一點。"""
        self.show_expression("yuck", 2400)
        self.overlay.say(random.choice(tr("say_annoyed")), 2500)
        self.overlay.burst("sweat", 2)
        if self.activity in (None, "hold") and self.mode != "sleep":
            back = -1 if self.direction != LEFT else 1
            r = self.screen_rect()
            tx = max(r.left(), min(r.right() - self.width(), self.x() + back * 200))
            self.hold(1200, then=lambda: self.go_to(tx, self.y(), then=self._resume, speed=5))

    # ---------------- 玩具 ---------------- #
    def play_with(self, toy):
        if self.activity in ("home", "drag", "eat", "jump", "fall", "zoom"):
            return
        self._drop_spot()
        if self.activity == "sleep":
            self.wake(quiet=True, force=True)
        self._stop_all()
        if self.toy is not toy:
            self.ctrl.progress.note("play")
            self.add_love(1)
        self.activity = "play"
        self.toy = toy
        self.perch = None
        self.fx, self.fy = float(self.x()), float(self.y())
        self._pounce_at = time.monotonic() + random.uniform(0.3, 1.2)
        self.move_timer.start(self._move_ms())

    def stop_play(self, resume=True):
        if self.toy is None:
            return
        self.toy = None
        if self.activity in ("play", "jump"):
            self._stop_all()
            self.activity = None
            if resume:
                self._resume()

    def _play_target(self):
        tx, ty = self.toy.point()
        gx = tx - self.width() / 2
        if self.mode in ("windows", "dock"):
            return gx, self.ground_y()
        return gx, ty - (self.height() - self.foot_off()) + 4

    def _play_step(self):
        if self.toy is None or not self.toy.alive:
            self.stop_play()
            return
        gx, gy = self._play_target()
        dist = ((gx - self.fx) ** 2 + (gy - self.fy) ** 2) ** 0.5
        if dist < 34:
            if self.walking:
                self.anim_timer.stop()
                self.walking = False
                self.frame = STAND_FRAME
                self.update()
            if time.monotonic() >= self._pounce_at:
                self._pounce_at = time.monotonic() + random.uniform(1.2, 2.4)
                self.jump_to(gx + random.uniform(-10, 10), gy, None, then=self._after_pounce)
                self._arc = 38
            return
        if not self.walking:
            self.walking = True
            self.anim_timer.start(self._anim_ms() // 2)
        self._step_towards(gx, gy, self._speed(9))

    def _after_pounce(self):
        self.overlay.burst("sparkle", 2)
        if self.toy is not None and self.toy.alive:
            self.activity = "play"
            self.move_timer.start(self._move_ms())
        else:
            self.toy = None
            self._resume()

    # ---------------- 紙箱、貓跳台 ---------------- #
    def visit(self, spot):
        """走到家具旁邊：紙箱就鑽進去，貓跳台就跳上去。"""
        x, y = spot.approach(self)
        self.go_to(x, y, then=lambda: self._arrive_spot(spot), speed=6)

    def _arrive_spot(self, spot):
        if not spot.alive or spot.occupant is not None:
            self._resume()
            return
        if spot.kind == "box":
            self._stop_all()
            self.activity = "box"
            self.spot = spot
            self.expression = None
            self.hide()
            self.overlay.hide()
            spot.occupy(self)
        else:
            tx, ty = spot.perch(self)
            spot.occupant = self
            self.spot = spot
            self.jump_to(tx, ty, None, then=self._sit_tree)
            self._arc = 30
        self.spot_timer.start(random.randint(15_000, 45_000))

    def _sit_tree(self):
        if self.spot is None:
            self._resume()
            return
        self._stop_all()
        self.activity = "tree"
        self.direction = DOWN
        self.update()
        self.overlay.burst("heart", 2)

    def leave_spot(self):
        spot = self.spot
        if spot is None:
            return
        if self.activity == "box" or (self.activity == "sleep" and spot.kind == "box"):
            self._drop_spot()
            self._resume()
        elif spot.kind == "tree":
            self._drop_spot()
            if self.activity == "sleep":
                self.wake(quiet=True, force=True)
            if self.activity in (None, "tree"):
                x = self.x() + random.choice((-1, 1)) * self.width()
                self.jump_to(x, self.ground_y(), None, then=self._resume)

    def _drop_spot(self):
        """馬上離開家具（被叫去做別的事時）。"""
        spot, self.spot = self.spot, None
        self.spot_timer.stop()
        if spot is None:
            return
        spot.release(self)
        if self.activity == "box":
            self.activity = None
            x, y = spot.approach(self)
            self._move_to(x, y, clamp=False)
            if not self.ctrl.all_hidden:
                self.show()
                self.raise_()
        elif self.activity == "tree":
            self.activity = None

    # ---------------- 設定變更 ---------------- #
    def set_color(self, color):
        self.color = color
        self._save("color", color)
        self._build_frames()

    def set_mode(self, mode):
        if self.activity == "home":
            self._exit_home()
        self._drop_spot()
        self.stop_play(resume=False)
        if self.activity == "sleep":
            self.wake(quiet=True, force=True)
        self.mode = mode
        self._save("mode", mode)
        self._apply_mode()

    def set_idle_direction(self, direction):
        self.idle_direction = direction
        self._save("idle_direction", direction)
        if self.mode == "idle" and self.activity is None:
            self.direction = direction
            self.update()

    def set_scale(self, scale):
        bottom = self.y() + self.height()
        self._save("scale", scale)
        self.scale = scale
        self._build_frames()
        if self.indoor is not None:              # 在房間裡：站回地板上
            house = self.indoor
            lo, hi = house.indoor_x_range(self)
            self._move_to(max(lo, min(hi, self.x())), house.indoor_floor_y(self), clamp=False)
            return
        self._move_to(self.x(), bottom - self.height())
        if self.mode == "windows":
            self.perch = None
            self._apply_mode()

    # ---------------- 位置記憶 / 移除 ---------------- #
    def _restore_position(self, near):
        if near is not None:
            r = near.screen_rect()
            x = near.x() + random.choice((-1, 1)) * random.randint(self.width(), self.width() * 3)
            self._move_to(*self._clamp(x, near.y()))
            return
        pos = self._pref("pos", None)
        if isinstance(pos, QPoint) and QGuiApplication.screenAt(pos):
            self._move_to(*self._clamp(pos.x(), pos.y()))
        else:
            r = QGuiApplication.primaryScreen().availableGeometry()
            self._move_to(r.right() - self.width() - 80 - 160 * self.cid,
                          r.bottom() + 1 - (self.height() - self.foot_off()))

    def save_pos(self):
        self._save("pos", self.pos())

    def dispose(self):
        self._stop_all()
        self._leave_indoor_silent()
        self._drop_spot()
        self.spot_timer.stop()
        self.ctrl.house.remove(self)          # 在家裡被送走的貓也要離開貓屋（不然煙囪會一直冒煙）
        if getattr(self, "_food", None):
            self._food.close()
        self.overlay.close()
        self.close()
        self.deleteLater()
