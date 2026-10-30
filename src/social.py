"""貓咪之間的互動：追來追去、聞聞對方、幫對方理毛、睡覺時擠在一起。

省電：每 14 秒才檢查一次，而且只在有兩隻以上、沒事做的貓時才動作。
"""
import random

from PySide6.QtCore import QObject, Qt, QTimer

from i18n import tr

FREE_MODES = ("idle", "random")


class Social(QObject):
    def __init__(self, ctrl):
        super().__init__(ctrl)
        self.ctrl = ctrl
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.VeryCoarseTimer)
        self.timer.timeout.connect(self._tick)
        self.timer.start(14_000)

    def _free(self):
        return [c for c in self.ctrl.cats
                if c.activity is None and c.mode in FREE_MODES and c.isVisible() and c.spot is None
                and c.indoor is None]

    def _tick(self):
        ctrl = self.ctrl
        if ctrl.all_hidden or ctrl.sleeping or ctrl.toy is not None or len(ctrl.cats) < 2:
            return
        if random.random() > 0.55:
            return
        free = self._free()
        if len(free) < 2:
            return
        a, b = random.sample(free, 2)
        if a.screen_rect() != b.screen_rect() or abs(a.x() - b.x()) > 700:
            return
        random.choice((self.chase, self.sniff, self.groom))(a, b)

    # ---------------- 互動 ---------------- #
    def chase(self, a, b):
        """a 追 b：b 先跑，a 在後面追。"""
        r = b.screen_rect()
        away = 1 if b.x() >= a.x() else -1
        bx = b.x() + away * random.randint(220, 380)
        if bx < r.left() or bx > r.right() - b.width():
            away = -away
            bx = b.x() + away * random.randint(220, 380)
        bx = max(r.left(), min(r.right() - b.width(), bx))
        a.overlay.say(random.choice(tr("say_chase")), 1800)
        b.overlay.burst("sweat", 1)
        b.go_to(bx, b.y(), then=b._resume, speed=8)
        ax = bx - away * a.width() * 0.8

        def caught():
            a._face(b.x() - a.x())
            a.overlay.burst("heart", 2)
            a.hold(1200)
        a.go_to(ax, b.y(), then=caught, speed=7)

    def _meet(self, a, b, after):
        """a 走到 b 旁邊，面對面。"""
        b.hold(6000)
        side = -1 if a.x() < b.x() else 1
        tx = b.x() + side * b.width() * 0.62

        def arrived():
            a._face(b.x() - a.x())
            b._face(a.x() - b.x())
            after()
        a.go_to(tx, b.y(), then=arrived, speed=5)

    def sniff(self, a, b):
        def after():
            a.overlay.say(random.choice(tr("say_sniff")), 2200)
            b.overlay.burst("note", 2)
            a.hold(2200)
            b.hold(2600)
        self._meet(a, b, after)

    def groom(self, a, b):
        def after():
            a.show_expression("happy", 3000)
            b.show_expression("happy", 3200)
            b.overlay.say(random.choice(tr("say_groom")), 2600)
            b.overlay.burst("heart", 4)
            a.hold(3000)
            b.hold(3200)
            self.ctrl.progress.note("groom")
            a.add_love(1)
            b.add_love(1)
        self._meet(a, b, after)

    # ---------------- 一起睡 ---------------- #
    def cuddle(self):
        """大家要睡覺時，走到第一隻貓旁邊擠在一起睡。"""
        cats = [c for c in self.ctrl.cats if c.isVisible() and c.spot is None and c.indoor is None]
        if len(cats) < 2:
            return
        anchor = cats[0]
        if anchor.activity not in (None, "sleep") or abs(anchor.y() - anchor.ground_y()) > 4:
            return
        k = 0
        for c in cats[1:]:
            if c.mode not in FREE_MODES + ("dock",) or c.activity is not None:
                continue
            if c.screen_rect() != anchor.screen_rect():
                continue
            k += 1
            side = 1 if k % 2 else -1
            step = (k + 1) // 2
            x = anchor.x() + side * step * anchor.width() * 0.62
            r = anchor.screen_rect()
            x = max(r.left(), min(r.right() - c.width(), x))
            c.go_to(x, c.ground_y(), then=c.sleep, speed=4)
