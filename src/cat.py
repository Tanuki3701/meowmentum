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

MOVE_INTERVAL = 33       # 移動中約 30fps
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
        self._clicks = []
        self._crossing = False
        self._waypoints = []
        self.toy = None           # 正在追的玩具
        self.spot = None          # 待在哪個家具裡／上（紙箱、貓跳台）

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
        self.anim_timer = self._timer(self._next_frame)
        self.anim_timer.setInterval(ANIM_INTERVAL)
        self.act_timer = self._timer(self._act_step)
        self.rest_timer = self._timer(self._rest_done)
        self.rest_timer.setSingleShot(True)
        self.expression = None      # 表情：happy / excited / yuck / dizzy
        self._expr_side = 0
        self.expr_timer = self._timer(self._clear_expression)
        self.expr_timer.setSingleShot(True)
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
        if self.activity == "sleep":
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
        return ANIM_INTERVAL * (2 if (self.ctrl.tired or self.ctrl.low_power) else 1)

    def _move_ms(self):
        """低耗電模式：移動改成約 15fps（走的距離一樣，只是畫面更新少一半）。"""
        return MOVE_INTERVAL * 2 if self.ctrl.low_power else MOVE_INTERVAL

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
            if self.move_timer.interval() in (MOVE_INTERVAL, MOVE_INTERVAL * 2):
                self.move_timer.start(self._move_ms())

    def _apply_mode(self):
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
        if self.activity is not None:
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
        if self.ctrl.low_power and self.move_timer.interval() == MOVE_INTERVAL * 2:
            speed *= 2
        dx, dy = tx - self.fx, ty - self.fy
        if abs(dx) <= speed and abs(dy) <= speed:
            self._move_to(tx, ty, clamp=self.mode != "windows" and not self._crossing)
            self._crossing = False
            return True
        self._face(dx, dy)
        sx = max(-speed, min(speed, dx))
        sy = max(-speed, min(speed, dy))
        self._move_to(self.fx + sx, self.fy + sy, clamp=self.mode != "windows" and not self._crossing)
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
        top = self._speed(FOLLOW_MAX_SPEED)
        sx = max(-top, min(top, dx * 0.1))
        sy = max(-top, min(top, dy * 0.1))
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
        self._jt += 1
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
        self.vy = min(self.vy + 1.5, 28)
        ny = self.fy + self.vy
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
        if self.mode == "windows":
            self._set_walking(False)
            self.rest_timer.start(random.randint(800, 2500))
        else:
            self._resume()

    # ---------------- 特別動作 ---------------- #
    def go_to(self, x, y, then=None, speed=7):
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

    def petted(self):
        self.overlay.burst("heart", 3)
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

    # ---------------- 回家 ---------------- #
    def go_home(self, house):
        if self.activity == "home":
            return
        x, y = house.door_cat_pos(self)
        self.go_to(x, y, then=lambda: self._enter_home(house), speed=8)

    def _enter_home(self, house):
        self._stop_all()
        self.activity = "home"
        self.expression = None
        self.hide()
        house.add(self)

    def _exit_home(self):
        house = self.ctrl.house
        house.remove(self)
        x, y = house.door_cat_pos(self)
        self.activity = None
        self._move_to(x, y, clamp=False)
        self.show()
        self.raise_()

    def leave_home(self):
        if self.activity != "home":
            return
        self._exit_home()
        self.direction = DOWN
        self.overlay.say(tr("say_hello"), 1800)
        self._resume()

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
        menu.sub("facing", tr("facing")).choices(
            {d: tr(k) for d, k in DIRECTIONS.items()}, self.idle_direction, self.set_idle_direction)
        menu.sub("size", tr("size")).choices(
            {z: tr(f"size_{z}") for z in SIZES}, self.scale, self.set_scale)

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
        self.scale = scale
        self._save("scale", scale)
        self._build_frames()
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
        self._drop_spot()
        self.spot_timer.stop()
        self.ctrl.house.remove(self)          # 在家裡被送走的貓也要離開貓屋（不然煙囪會一直冒煙）
        if getattr(self, "_food", None):
            self._food.close()
        self.overlay.close()
        self.close()
        self.deleteLater()
