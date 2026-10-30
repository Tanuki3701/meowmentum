"""小魚乾商店、專注紀錄、幫貓咪取名字的視窗（像素遊戲風，和待辦清單同一套外觀）。"""
import datetime as dt

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout,
                               QWidget)

import art
import i18n
import interior
import pixel
import progress
import seasons
from i18n import tr
from panels import U, PixelButton, PixelPanel, _style_line_edit

INK_HEX = "#3a3737"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SOFT_HEX = "#7a6a58"


def _label(text="", color=INK_HEX, px=12):
    lab = QLabel(text)
    lab.setFont(pixel.font(px))
    lab.setStyleSheet(f"color: {color};")
    return lab


def _coin_row():
    row = QHBoxLayout()
    row.setSpacing(4)
    icon = QLabel()
    icon.setPixmap(art.icon_pm("fish", 1.5))
    row.addWidget(icon)
    lab = _label()
    row.addWidget(lab)
    return row, lab


def preview(item, kind):
    if kind == "hat":
        return art.pix(art.HATS[item], 2)
    if kind == "neck":
        return art.pix(art.NECKS[item]["front"], 2)
    if kind == "desk":
        return art.icon_pm(item, 2)
    return interior.item_preview(item, 1.5)


# ---------------- 商店 ---------------- #
class ShopPanel(PixelPanel):
    """小魚乾商店：服飾店（帽子、脖子的飾品）和家具店（桌面家具、房間和閣樓的擺設）分開。"""
    W = 360

    def __init__(self, ctrl, kinds=None, title_key="shop_title", icon="shirt"):
        super().__init__()
        self.ctrl = ctrl
        self.kinds = kinds or progress.WARDROBE
        self.title_key = title_key
        self.target = None
        self.setFixedWidth(self.W)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(U * 2 + 8, U + 6, U * 2 + 8 + U, U * 2 + 10 + U)
        lay.setSpacing(6)
        self.title = QLabel()
        lay.addWidget(self._title_bar(art.icon_pm(icon, 2), self.title, self.hide))
        coin_row, self.coins = _coin_row()
        self.hint = _label(color=SOFT_HEX)
        coin_row.addStretch()
        coin_row.addWidget(self.hint)
        lay.addLayout(coin_row)

        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 4, 0)
        self.body_lay.setSpacing(2)
        scroll = QScrollArea()
        scroll.setWidget(self.body)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedHeight(380)
        scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
            "QScrollBar:vertical { width: 6px; background: transparent; margin: 0; }"
            "QScrollBar::handle:vertical { background: #c9a865; min-height: 20px; }"
            "QScrollBar::add-line, QScrollBar::sub-line { height: 0; }")
        lay.addWidget(scroll)
        self.msg = _label(color=SOFT_HEX)
        lay.addWidget(self.msg)

    def open_for(self, cat, anchor=None):
        self.target = cat
        self.msg.setText("")
        self.refresh()
        self.place_near(anchor or cat)

    def refresh(self):
        pr = self.ctrl.progress
        self.title.setText(tr(self.title_key))
        self.coins.setText(tr("coins_n", n=pr.coins))
        self.hint.setText(tr("shop_hint"))
        while self.body_lay.count():
            it = self.body_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        seasonal = seasons.seasonal_hats()
        for kind in self.kinds:
            self.body_lay.addSpacing(4)
            self.body_lay.addWidget(_label(tr("kind_" + kind), SOFT_HEX))
            items = [(i, p) for i, (k, p) in progress.ITEMS.items() if k == kind]
            if kind == "hat":
                items = [(h, 0) for h in seasonal] + items
            for item, price in items:
                self.body_lay.addWidget(self._row(item, kind, price, item in seasonal))
        self.body_lay.addStretch()

    def _row(self, item, kind, price, limited):
        pr = self.ctrl.progress
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(8)
        pic = QLabel()
        pic.setFixedSize(48, 34)
        pic.setAlignment(Qt.AlignCenter)
        pic.setPixmap(preview(item, kind))
        row.addWidget(pic)
        name = tr("item_" + item) + (f"  ({tr('limited')})" if limited else "")
        row.addWidget(_label(name))
        row.addStretch()
        cat = self.target
        if not pr.has(item):
            b = PixelButton(tr("buy_n", n=price))
            b.setEnabled(pr.coins >= price)
            if pr.coins < price:
                b.setToolTip(tr("not_enough"))
            b.clicked.connect(lambda _=False, i=item: self._buy(i))
            row.addWidget(b)
        elif kind in ("hat", "neck") and cat is not None:
            worn = (cat.hat if kind == "hat" else cat.neck) == item
            b = PixelButton(tr("take_off") if worn else tr("wear"))
            b.clicked.connect(lambda _=False, i=item, k=kind, wn=worn: self._wear(i, k, wn))
            row.addWidget(b)
        elif kind == "desk":
            placed = item in pr.placed
            b = PixelButton(tr("put_away") if placed else tr("place_out"))
            b.clicked.connect(lambda _=False, i=item, pl=placed: self._place(i, not pl))
            row.addWidget(b)
        else:
            row.addWidget(_label(tr("in_house"), SOFT_HEX))
        return w

    def _buy(self, item):
        if self.ctrl.progress.buy(item):
            self.msg.setText(tr("bought", item=tr("item_" + item)))
            kind = progress.ITEMS[item][0]
            if kind in ("hat", "neck") and self.target is not None:
                self._wear(item, kind, False, refresh=False)
            elif kind == "desk":
                self.ctrl.place_item(item, True)
            if self.target is not None:
                self.target.overlay.burst("heart", 3)
        self.refresh()

    def _wear(self, item, kind, worn, refresh=True):
        cat = self.target
        if cat is None or cat not in self.ctrl.cats:
            return
        value = None if worn else item
        (cat.set_hat if kind == "hat" else cat.set_neck)(value)
        if refresh:
            self.refresh()

    def _place(self, item, on):
        self.ctrl.place_item(item, on)
        self.refresh()

    def retranslate(self):
        if self.isVisible():
            self.refresh()


# ---------------- 專注紀錄 ---------------- #
WEEKS = 16
CELL, GAP = 13, 3


def heat_color(minutes):
    if minutes <= 0:
        return QColor(240, 226, 196)
    t = min(1.0, minutes / 120)
    return QColor(*[int(c) for c in pixel.tomato_color(0.15 + 0.85 * t)])


class HeatMap(QWidget):
    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.setFixedSize(26 + WEEKS * (CELL + GAP), 7 * (CELL + GAP) + 22)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setFont(pixel.font(10))
        today = dt.date.today()
        start = today - dt.timedelta(days=today.weekday() + 7 * (WEEKS - 1))
        p.setPen(QColor(122, 106, 88))
        for wd, key in ((0, "wd_mon"), (2, "wd_wed"), (4, "wd_fri")):
            p.drawText(QRect(0, wd * (CELL + GAP), 24, CELL), Qt.AlignVCenter | Qt.AlignLeft, tr(key))
        last_month = None
        for w in range(WEEKS):
            for d in range(7):
                day = start + dt.timedelta(days=w * 7 + d)
                if day > today:
                    continue
                x, y = 26 + w * (CELL + GAP), d * (CELL + GAP)
                m = self.ctrl.progress.day(day)[0]
                p.fillRect(QRect(x, y, CELL, CELL), pixel.INK)
                p.fillRect(QRect(x + 2, y + 2, CELL - 4, CELL - 4), heat_color(m))
                if day == today:
                    p.fillRect(QRect(x, y + CELL, CELL, 2), QColor(217, 72, 59))
            first = start + dt.timedelta(days=w * 7)
            if first.month != last_month:
                last_month = first.month
                p.setPen(QColor(122, 106, 88))
                p.drawText(QRect(26 + w * (CELL + GAP), 7 * (CELL + GAP) + 2, 40, 18),
                           Qt.AlignLeft, tr("month_n", m=first.month if i18n.lang() == "zh"
                                            else MONTHS[first.month - 1]))


class StatsPanel(PixelPanel):
    W = 26 + WEEKS * (CELL + GAP) + 2 * (U * 2 + 8) + U + 8

    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.setFixedWidth(self.W)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(U * 2 + 8, U + 6, U * 2 + 8 + U, U * 2 + 10 + U)
        lay.setSpacing(8)
        self.title = QLabel()
        lay.addWidget(self._title_bar(art.icon_pm("chart", 2), self.title, self.hide))
        grid = QHBoxLayout()
        self.cards = []
        for _ in range(4):
            box = QVBoxLayout()
            box.setSpacing(2)
            v = _label(px=16)
            k = _label(color=SOFT_HEX)
            box.addWidget(v)
            box.addWidget(k)
            grid.addLayout(box, 1)
            self.cards.append((v, k))
        lay.addLayout(grid)
        self.map = HeatMap(ctrl)
        lay.addWidget(self.map)
        legend = QHBoxLayout()
        legend.addStretch()
        self.less = _label(color=SOFT_HEX)
        legend.addWidget(self.less)
        for m in (0, 25, 50, 90, 140):
            sw = QLabel()
            sw.setFixedSize(CELL, CELL)
            c = heat_color(m)
            sw.setStyleSheet(f"background: rgb({c.red()},{c.green()},{c.blue()}); border: 2px solid #3a3737;")
            legend.addWidget(sw)
        self.more = _label(color=SOFT_HEX)
        legend.addWidget(self.more)
        lay.addLayout(legend)
        # 成就徽章
        self.badge_title = _label(color=SOFT_HEX)
        lay.addWidget(self.badge_title)
        brow = QHBoxLayout()
        brow.setSpacing(6)
        self.badge_icons = []
        for _ in progress.BADGES:
            ic = QLabel()
            ic.setFixedSize(30, 30)
            ic.setAlignment(Qt.AlignCenter)
            brow.addWidget(ic)
            self.badge_icons.append(ic)
        brow.addStretch()
        lay.addLayout(brow)
        # 貓咪日記：最近幾天發生的小事
        self.diary_title = _label(color=SOFT_HEX)
        lay.addWidget(self.diary_title)
        self.diary_lines = []
        for _ in range(4):
            d = _label()
            d.setWordWrap(True)
            lay.addWidget(d)
            self.diary_lines.append(d)
        coin_row, self.coins = _coin_row()
        coin_row.addStretch()
        lay.addLayout(coin_row)

    @staticmethod
    def _badge_pm(on):
        pm = art.icon_pm("badge", 2)
        if on:
            return pm
        img = pm.toImage().convertToFormat(pm.toImage().Format.Format_ARGB32)
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                if c.alpha():
                    g = int(c.red() * 0.3 + c.green() * 0.59 + c.blue() * 0.11)
                    g = 150 + (g - 150) // 3
                    img.setPixelColor(x, y, QColor(g, g - 6, g - 14, 150))
        from PySide6.QtGui import QPixmap
        out = QPixmap.fromImage(img)
        out.setDevicePixelRatio(pm.devicePixelRatio())
        return out

    def diary_text(self, day):
        pr = self.ctrl.progress
        d = pr.diary.get(day.isoformat(), {})
        parts = []
        mins = pr.day(day)[0]
        if mins:
            parts.append(tr("diary_focus", n=mins))
        for k in ("can", "pet", "play", "groom", "gift"):
            if d.get(k):
                parts.append(tr("diary_" + k, n=d[k]))
        if not parts:
            return None
        sep = "，" if i18n.lang() == "zh" else ", "
        text = sep.join(parts)
        return text[0].upper() + text[1:] if i18n.lang() == "en" else text

    def refresh(self):
        pr = self.ctrl.progress
        self.title.setText(tr("stats_title"))
        got = 0
        for ic, (bid, _icon, reward) in zip(self.badge_icons, progress.BADGES):
            on = bid in pr.badges
            got += on
            ic.setPixmap(self._badge_pm(on))
            tip = tr("badge_" + bid) + "  ·  " + tr("badge_" + bid + "_how")
            if reward:
                tip += "  ·  " + tr("item_" + reward)
            ic.setToolTip(tip)
        self.badge_title.setText(tr("stat_badges", n=got, t=len(progress.BADGES)))
        self.diary_title.setText(tr("stat_diary"))
        today = dt.date.today()
        lines = []
        for back in range(0, 14):
            day = today - dt.timedelta(days=back)
            text = self.diary_text(day)
            if text:
                lines.append(f"{day.month}/{day.day}  {text}")
            if len(lines) >= 4:
                break
        if not lines:
            lines = [tr("diary_empty")]
        for lab, text in zip(self.diary_lines, lines + [""] * 4):
            lab.setText(text)
            lab.setVisible(bool(text))
        self.adjustSize()
        m, n = pr.day(dt.date.today())
        total_m, total_n = pr.totals()
        vals = [(tr("n_min_short", m=m), tr("stat_today")),
                (tr("n_times", n=n), tr("stat_sessions_today")),
                (tr("n_days", n=pr.streak()), tr("stat_streak")),
                (tr("n_hours", h=f"{total_m / 60:.1f}"), tr("stat_total"))]
        for (v, k), (vt, kt) in zip(self.cards, vals):
            v.setText(vt)
            k.setText(kt)
        self.less.setText(tr("less"))
        self.more.setText(tr("more"))
        self.coins.setText(tr("coins_n", n=pr.coins) + "  ·  " + tr("coins_hint"))
        self.map.update()

    def open_near(self, cat):
        self.refresh()
        self.place_near(cat)


# ---------------- 取名字 ---------------- #
class NamePrompt(PixelPanel):
    W = 300

    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.cat = None
        self.setFixedWidth(self.W)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(U * 2 + 8, U + 6, U * 2 + 8 + U, U * 2 + 10 + U)
        lay.setSpacing(8)
        self.title = QLabel()
        lay.addWidget(self._title_bar(art.icon_pm("name", 2), self.title, self.hide))
        self.edit = QLineEdit()
        self.edit.setMaxLength(16)
        _style_line_edit(self.edit)
        self.edit.returnPressed.connect(self._ok)
        lay.addWidget(self.edit)
        self.hint = _label(color=SOFT_HEX)
        lay.addWidget(self.hint)
        foot = QHBoxLayout()
        foot.addStretch()
        self.cancel = PixelButton()
        self.cancel.clicked.connect(self.hide)
        foot.addWidget(self.cancel)
        self.ok = PixelButton()
        self.ok.clicked.connect(self._ok)
        foot.addWidget(self.ok)
        lay.addLayout(foot)

    def open_for(self, cat):
        self.cat = cat
        self.title.setText(tr("name_title"))
        self.hint.setText(tr("name_hint"))
        self.cancel.setText(tr("cancel"))
        self.ok.setText(tr("save_apply"))
        self.edit.setText(cat.name)
        self.edit.setPlaceholderText(cat.display_name())
        self.place_near(cat)
        self.edit.setFocus()
        self.edit.selectAll()

    def _ok(self):
        if self.cat in self.ctrl.cats:
            self.cat.set_name(self.edit.text())
            self.cat.overlay.say(tr("say_named", n=self.cat.display_name()), 2500)
            self.cat.overlay.burst("heart", 3)
        self.hide()
