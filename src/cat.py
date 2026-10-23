"""桌面貓咪本體。

省電設計：
- 貓咪本身就是一個剛好貓咪大小的小視窗（不再是 1920x1080 的透明全螢幕視窗），
  移動時只是移動這個小視窗，系統幾乎不用重繪。
- 所有影格在載入時就切好、放大好並快取，畫面更新時只是貼上一張現成的圖。
- 計時器「需要時才開」：閒置模式下完全沒有計時器在跑（CPU 0%）；
  漫步模式走到目的地會停下休息；跟隨模式在滑鼠附近時改成低頻率檢查。
- 使用 CoarseTimer，讓 macOS 可以把喚醒合併在一起，減少耗電。
"""
import os
import random
import sys

from PySide6.QtCore import QPoint, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QCursor, QGuiApplication, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QWidget

FRAME_W, FRAME_H = 32, 48
FRAMES_PER_DIR = 3
STAND_FRAME = 1  # 每排中間那格是站姿

UP, RIGHT, DOWN, LEFT = 0, 1, 2, 3

COLORS = {"black": "黑貓", "white": "白貓", "orange": "橘貓", "brown": "棕貓"}
MODES = {"idle": "待著不動", "random": "隨意漫步", "follow": "跟著滑鼠"}
DIRECTIONS = {DOWN: "面向前", LEFT: "面向左", RIGHT: "面向右", UP: "背對"}
SIZES = {2: "小", 3: "中", 4: "大"}

MOVE_INTERVAL = 33       # 移動中：約 30fps，已足夠流暢
ANIM_INTERVAL = 150      # 走路動畫換格速度
FOLLOW_IDLE_POLL = 250   # 跟隨模式、貓咪已在滑鼠旁時，每 0.25 秒看一次滑鼠
WANDER_SPEED = 4         # 漫步每步像素
FOLLOW_MAX_SPEED = 10    # 跟隨每步最大像素
FOLLOW_DISTANCE = 50     # 距離滑鼠多近就停下
REST_MS = (2000, 7000)   # 漫步到點後休息多久（毫秒）


def resource_path(*parts):
    """同時支援直接執行原始碼與 PyInstaller 打包後的 .app。"""
    base = getattr(sys, "_MEIPASS", None) or os.path.join(os.path.dirname(__file__), "..")
    return os.path.join(base, *parts)


class Cat(QWidget):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool                      # 不出現在 Cmd+Tab / 視窗列表
            | Qt.NoDropShadowWindowHint    # macOS 預設會加陰影，透明視窗不需要
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)  # 切到別的 App 時不要消失
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.settings = QSettings("DesktopCat", "DesktopCat")
        self.color = self.settings.value("color", "orange")
        if self.color not in COLORS:
            self.color = "orange"
        self.mode = self.settings.value("mode", "idle")
        if self.mode not in MODES:
            self.mode = "idle"
        self.idle_direction = int(self.settings.value("idle_direction", DOWN))
        self.scale = int(self.settings.value("scale", 3))
        if self.scale not in SIZES:
            self.scale = 3

        self.direction = self.idle_direction
        self.frame = STAND_FRAME
        self.walking = False
        self.drag_offset = None
        self.target = None
        self.frames = []

        # 計時器：只建立，不先啟動
        self.move_timer = QTimer(self)
        self.move_timer.setTimerType(Qt.CoarseTimer)
        self.move_timer.timeout.connect(self._tick)

        self.anim_timer = QTimer(self)
        self.anim_timer.setTimerType(Qt.CoarseTimer)
        self.anim_timer.setInterval(ANIM_INTERVAL)
        self.anim_timer.timeout.connect(self._next_frame)

        self.rest_timer = QTimer(self)
        self.rest_timer.setSingleShot(True)
        self.rest_timer.setTimerType(Qt.CoarseTimer)
        self.rest_timer.timeout.connect(self._start_wandering)

        self._build_frames()
        self._restore_position()
        self._apply_mode()

    # ---------------- 影格 ---------------- #
    def _build_frames(self):
        path = resource_path("assets", "sprites", f"cat_{self.color}-32x48.png")
        sheet = QPixmap(path)
        if sheet.isNull():
            raise FileNotFoundError(f"找不到圖檔: {path}")

        # 依螢幕最高的像素密度預先放大（Retina 上也保持像素風銳利）
        dpr = max((s.devicePixelRatio() for s in QGuiApplication.screens()), default=1.0)
        w, h = FRAME_W * self.scale, FRAME_H * self.scale
        self.frames = []
        for d in range(4):
            row = []
            for f in range(FRAMES_PER_DIR):
                pm = sheet.copy(f * FRAME_W, d * FRAME_H, FRAME_W, FRAME_H).scaled(
                    round(w * dpr), round(h * dpr),
                    Qt.IgnoreAspectRatio, Qt.FastTransformation,
                )
                pm.setDevicePixelRatio(dpr)
                row.append(pm)
            self.frames.append(row)
        self.setFixedSize(w, h)
        self.update()

    def paintEvent(self, _event):
        QPainter(self).drawPixmap(0, 0, self.frames[self.direction][self.frame])

    def _next_frame(self):
        self.frame = (self.frame + 1) % FRAMES_PER_DIR
        self.update()

    # ---------------- 走路狀態 ---------------- #
    def _set_walking(self, walking, interval=MOVE_INTERVAL):
        if walking:
            self.move_timer.start(interval)
            if not self.walking:
                self.anim_timer.start()
        else:
            self.anim_timer.stop()
            if self.mode == "follow":
                self.move_timer.start(FOLLOW_IDLE_POLL)  # 低頻率盯著滑鼠
            else:
                self.move_timer.stop()
            self.frame = STAND_FRAME
            self.update()
        self.walking = walking

    def _stop_everything(self):
        for t in (self.move_timer, self.anim_timer, self.rest_timer):
            t.stop()
        self.walking = False
        self.frame = STAND_FRAME

    def _apply_mode(self):
        self._stop_everything()
        if self.mode == "idle":
            self.direction = self.idle_direction
            self.update()
        elif self.mode == "random":
            self._start_wandering()
        elif self.mode == "follow":
            self._set_walking(False)  # 先以低頻率檢查，需要時才開始走
        self.update()

    def _start_wandering(self):
        self.target = self._random_target()
        self._set_walking(True)

    # ---------------- 移動 ---------------- #
    def _screen_rect(self, point=None):
        point = point or self.geometry().center()
        screen = QGuiApplication.screenAt(point) or self.screen() or QGuiApplication.primaryScreen()
        return screen.availableGeometry()  # 扣掉選單列和 Dock

    def _clamp(self, x, y):
        r = self._screen_rect(QPoint(x + self.width() // 2, y + self.height() // 2))
        x = max(r.left(), min(x, r.right() - self.width() + 1))
        y = max(r.top(), min(y, r.bottom() - self.height() + 1))
        return x, y

    def _random_target(self):
        r = self._screen_rect()
        return (
            random.randint(r.left(), max(r.left(), r.right() - self.width())),
            random.randint(r.top(), max(r.top(), r.bottom() - self.height())),
        )

    def _face(self, dx, dy):
        if abs(dx) > abs(dy):
            d = RIGHT if dx > 0 else LEFT
        else:
            d = DOWN if dy > 0 else UP
        if d != self.direction:
            self.direction = d
            self.update()

    def _tick(self):
        if self.drag_offset is not None:
            return
        if self.mode == "random":
            self._wander_step()
        elif self.mode == "follow":
            self._follow_step()

    def _wander_step(self):
        tx, ty = self.target
        dx, dy = tx - self.x(), ty - self.y()
        if abs(dx) <= WANDER_SPEED and abs(dy) <= WANDER_SPEED:
            self.move(*self._clamp(tx, ty))
            self._set_walking(False)
            self.rest_timer.start(random.randint(*REST_MS))  # 休息一下再走
            return
        sx = max(-WANDER_SPEED, min(WANDER_SPEED, dx))
        sy = max(-WANDER_SPEED, min(WANDER_SPEED, dy))
        self._face(dx, dy)
        self.move(*self._clamp(self.x() + sx, self.y() + sy))

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
        sx = max(-FOLLOW_MAX_SPEED, min(FOLLOW_MAX_SPEED, int(dx * 0.1)))
        sy = max(-FOLLOW_MAX_SPEED, min(FOLLOW_MAX_SPEED, int(dy * 0.1)))
        self._face(dx, dy)
        self.move(*self._clamp(self.x() + sx, self.y() + sy))

    # ---------------- 拖曳 ---------------- #
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag_offset = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self.drag_offset is not None:
            self.move(e.globalPosition().toPoint() - self.drag_offset)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.drag_offset is not None:
            self.drag_offset = None
            self.move(*self._clamp(self.x(), self.y()))
            self._save_position()
            if self.mode == "random" and self.walking:
                self.target = self._random_target()

    # ---------------- 右鍵選單 ---------------- #
    def contextMenuEvent(self, e):
        menu = QMenu(self)
        self._add_choices(menu.addMenu("顏色"), COLORS, self.color, self.set_color)
        self._add_choices(menu.addMenu("模式"), MODES, self.mode, self.set_mode)
        self._add_choices(menu.addMenu("待著時的方向"), DIRECTIONS, self.idle_direction,
                          self.set_idle_direction)
        self._add_choices(menu.addMenu("大小"), SIZES, self.scale, self.set_scale)
        menu.addSeparator()
        menu.addAction("結束").triggered.connect(self.quit)
        menu.exec(e.globalPos())

    def _add_choices(self, submenu, options, current, handler):
        group = QActionGroup(submenu)
        for value, label in options.items():
            act = QAction(label, submenu, checkable=True, checked=(value == current))
            act.triggered.connect(lambda _=False, v=value: handler(v))
            group.addAction(act)
            submenu.addAction(act)

    def set_color(self, color):
        self.color = color
        self.settings.setValue("color", color)
        self._build_frames()

    def set_mode(self, mode):
        self.mode = mode
        self.settings.setValue("mode", mode)
        self._apply_mode()

    def set_idle_direction(self, direction):
        self.idle_direction = direction
        self.settings.setValue("idle_direction", direction)
        if self.mode == "idle":
            self.direction = direction
            self.update()

    def set_scale(self, scale):
        self.scale = scale
        self.settings.setValue("scale", scale)
        self._build_frames()
        self.move(*self._clamp(self.x(), self.y()))

    # ---------------- 位置記憶 / 結束 ---------------- #
    def _restore_position(self):
        pos = self.settings.value("pos")
        if isinstance(pos, QPoint) and QGuiApplication.screenAt(pos):
            self.move(*self._clamp(pos.x(), pos.y()))
        else:
            r = QGuiApplication.primaryScreen().availableGeometry()
            self.move(r.right() - self.width() - 80, r.bottom() - self.height())

    def _save_position(self):
        self.settings.setValue("pos", self.pos())

    def quit(self):
        self._save_position()
        self.settings.sync()
        QApplication.quit()
