"""像素風待辦清單（RPG 任務欄）與罐罐。"""
import json

from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea,
                               QVBoxLayout, QWidget)

import pixel
import sprites
from i18n import tr
from macos import show_on_all_spaces

U = 3            # 外框像素單位
TITLE_H = 34
MAX_ROWS = 8
ROW_H = 26

CHECK_OFF = [
    "KKKKKKKKK",
    "KWWWWWWWK",
    "KWCCCCCCK",
    "KWCCCCCCK",
    "KWCCCCCCK",
    "KWCCCCCCK",
    "KWCCCCCCK",
    "KWCCCCCCK",
    "KKKKKKKKK",
]
CHECK_ON = [
    "KKKKKKKKK..",
    "KWWWWWWWK.G",
    "KWCCCCCCKGg",
    "KWCCCCCGGg.",
    "KWGCCCGGgK.",
    "KWGGCGGgCK.",
    "KWCGGGgCCK.",
    "KWCCGgCCCK.",
    "KKKKKKKKKK.",
]


def _style_line_edit(edit):
    fam = pixel.font_family()
    edit.setFont(pixel.font(12))
    edit.setStyleSheet(
        "QLineEdit { background: #fffdf5; color: #3a3737; border: 2px solid #3a3737;"
        " padding: 4px 6px; selection-background-color: #e9c878; selection-color: #3a3737;"
        f" font-family: '{fam}'; font-size: 12px; }}")


class PixelButton(QAbstractButton):
    """遊戲風按鈕：像素框，按下時往下沉一格。"""

    def __init__(self, text="", icon=None, parent=None, flat=False):
        super().__init__(parent)
        self.setText(text)
        self._icon = icon
        self._flat = flat
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(pixel.font(12))

    def sizeHint(self):
        if self._icon is not None:
            return QSize(22, 22)
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 20, 24)

    def enterEvent(self, e):
        self.update()

    def leaveEvent(self, e):
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        down = 2 if self.isDown() else 0
        r = self.rect().adjusted(0, down, -2, -2 + down)
        hover = self.underMouse()
        if self._icon is not None:
            if hover or self.isDown():
                pixel.draw_box(p, r, 2, fill=pixel.GOLD, light=None, shadow=False)
            pm = self._icon
            iw, ih = pm.width() / pm.devicePixelRatio(), pm.height() / pm.devicePixelRatio()
            p.drawPixmap(int(r.center().x() - iw / 2 + 1), int(r.center().y() - ih / 2 + 1), pm)
            return
        fill = QColor(242, 214, 140) if hover else pixel.GOLD
        pixel.draw_box(p, r, 2, fill=fill, light=QColor(250, 232, 180), shadow=not self.isDown())
        p.setPen(pixel.INK)
        p.setFont(self.font())
        p.drawText(r, Qt.AlignCenter, self.text())


class TodoRow(QWidget):
    def __init__(self, panel, text, done):
        super().__init__()
        self.panel = panel
        self.text = text
        self.done = done
        self.setFixedHeight(ROW_H)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(pixel.font(12))
        self._hover = False

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def _delete_rect(self):
        return QRect(self.width() - 22, (ROW_H - 14) // 2, 14, 14)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        if self._delete_rect().contains(e.position().toPoint()):
            self.panel.remove_row(self)
        else:
            self.done = not self.done
            self.update()
            self.panel.changed()

    def paintEvent(self, _e):
        p = QPainter(self)
        if self._hover:
            p.fillRect(self.rect().adjusted(0, 1, 0, -1), QColor(244, 226, 178, 150))
        grid = CHECK_ON if self.done else CHECK_OFF
        box = pixel._grid_pixmap(grid, 2, size=(11, 9))
        p.drawPixmap(4, (ROW_H - 18) // 2, box)
        f = pixel.font(12)
        f.setStrikeOut(self.done)
        p.setFont(f)
        p.setPen(QColor(150, 140, 130) if self.done else pixel.INK)
        p.drawText(QRect(32, 0, self.width() - 60, ROW_H), Qt.AlignVCenter | Qt.AlignLeft,
                   self.fontMetrics().elidedText(self.text, Qt.ElideRight, self.width() - 60))
        if self._hover:
            p.drawPixmap(self._delete_rect().topLeft(), pixel.icon_pixmap("close", 2, (7, 7)))


class PixelPanel(QWidget):
    """像素風視窗的共用外觀：外框、金色標題列、拖曳標題列移動。"""

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self._drag = None

    def paintEvent(self, _e):
        p = QPainter(self)
        r = self.rect().adjusted(0, 0, -U, -U)
        pixel.draw_box(p, r, U)
        band = QRect(r.left() + U, r.top() + U, r.width() - 2 * U, TITLE_H - U)
        p.fillRect(band, pixel.GOLD)
        p.fillRect(QRect(band.left(), band.top(), band.width(), U), QColor(248, 224, 160))
        p.fillRect(QRect(band.left(), band.bottom() + 1, band.width(), U), pixel.INK)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and e.position().y() < TITLE_H:
            self._drag = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def _title_bar(self, icon_pm, title_label, on_close):
        head = QHBoxLayout()
        head.setSpacing(6)
        head.setContentsMargins(0, 0, 0, 0)
        self._title_icon = QLabel()
        self._title_icon.setPixmap(icon_pm)
        head.addWidget(self._title_icon)
        title_label.setFont(pixel.font(12))
        title_label.setStyleSheet("color: #3a3737;")
        head.addWidget(title_label)
        head.addStretch()
        close = PixelButton(icon=pixel.icon_pixmap("close", 2, (7, 7)))
        close.clicked.connect(on_close)
        head.addWidget(close)
        box = QWidget()
        box.setFixedHeight(TITLE_H - U - 6)
        box.setLayout(head)
        return box

    def place_near(self, cat):
        self.adjustSize()
        screen = cat.screen_rect()
        x = cat.x() + cat.width() + 8
        if x + self.width() > screen.right():
            x = cat.x() - self.width() - 8
        y = min(max(screen.top(), cat.y()), screen.bottom() - self.height())
        self.move(x, y)
        self.show()
        show_on_all_spaces(self)
        self.raise_()
        self.activateWindow()


class TodoPanel(PixelPanel):
    W = 290

    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.setFixedWidth(self.W)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(U * 2 + 8, U + 6, U * 2 + 8 + U, U * 2 + 10 + U)
        lay.setSpacing(6)

        self.title = QLabel()
        head_box = self._title_bar(pixel.icon_pixmap("note", 2), self.title, self.hide)
        lay.addWidget(head_box)
        lay.addSpacing(4)

        self.rows_box = QWidget()
        self.rows_lay = QVBoxLayout(self.rows_box)
        self.rows_lay.setContentsMargins(0, 0, 0, 0)
        self.rows_lay.setSpacing(0)
        self.rows_lay.addStretch()
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.rows_box)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }"
            "QScrollBar:vertical { width: 6px; background: transparent; margin: 0; }"
            "QScrollBar::handle:vertical { background: #c9a865; min-height: 20px; }"
            "QScrollBar::add-line, QScrollBar::sub-line { height: 0; }")
        lay.addWidget(self.scroll)

        self.empty = QLabel()
        self.empty.setFont(pixel.font(12))
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet("color: #a8957a;")
        self.empty.setFixedHeight(ROW_H * 2)
        lay.addWidget(self.empty)

        self.entry = QLineEdit()
        _style_line_edit(self.entry)
        self.entry.returnPressed.connect(self._add)
        lay.addWidget(self.entry)

        foot = QHBoxLayout()
        self.count = QLabel()
        self.count.setFont(pixel.font(12))
        self.count.setStyleSheet("color: #7a6a58;")
        foot.addWidget(self.count)
        foot.addStretch()
        self.clear_btn = PixelButton()
        self.clear_btn.clicked.connect(self._clear_done)
        foot.addWidget(self.clear_btn)
        lay.addLayout(foot)

        self._loading = False
        self._all_done = False
        self._load()
        self.retranslate()

    # ---------------- 外觀 ---------------- #
    def retranslate(self):
        self.title.setText(tr("todo_title"))
        self.entry.setPlaceholderText(tr("todo_add"))
        self.clear_btn.setText(tr("todo_clear"))
        self.clear_btn.updateGeometry()
        self._update_count()

    # ---------------- 資料 ---------------- #
    def _rows(self):
        return [self.rows_lay.itemAt(i).widget() for i in range(self.rows_lay.count() - 1)]

    def _load(self):
        self._loading = True
        try:
            items = json.loads(self.ctrl.settings.value("todos", "[]"))
        except Exception:
            items = []
        for it in items:
            self._append(it.get("t", ""), it.get("d", False))
        self._loading = False
        self._all_done = self._is_all_done()
        self._resize()

    def _save(self):
        items = [{"t": r.text, "d": r.done} for r in self._rows()]
        self.ctrl.settings.setValue("todos", json.dumps(items, ensure_ascii=False))

    def _append(self, text, done=False):
        row = TodoRow(self, text, done)
        self.rows_lay.insertWidget(self.rows_lay.count() - 1, row)

    def _is_all_done(self):
        rows = self._rows()
        return bool(rows) and all(r.done for r in rows)

    def _update_count(self):
        rows = self._rows()
        self.count.setText(tr("todo_count", d=sum(r.done for r in rows), n=len(rows)))
        self.empty.setText(tr("todo_empty"))

    def _resize(self):
        n = len(self._rows())
        self.scroll.setVisible(n > 0)
        self.empty.setVisible(n == 0)
        self.scroll.setFixedHeight(min(n, MAX_ROWS) * ROW_H + 2)
        self._update_count()
        self.adjustSize()

    # ---------------- 事件 ---------------- #
    def _add(self):
        text = self.entry.text().strip()
        if text:
            self._append(text)
            self.entry.clear()
            self._resize()
            QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(
                self.scroll.verticalScrollBar().maximum()))
            self.changed()

    def remove_row(self, row):
        row.setParent(None)
        row.deleteLater()
        self._resize()
        self.changed()

    def _clear_done(self):
        for r in self._rows():
            if r.done:
                r.setParent(None)
                r.deleteLater()
        self._resize()
        self.changed()

    def changed(self):
        if self._loading:
            return
        self._save()
        self._update_count()
        all_done = self._is_all_done()
        if all_done and not self._all_done:
            self.ctrl.celebrate()
        self._all_done = all_done

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)

    def toggle_near(self, cat):
        if self.isVisible():
            self.hide()
            return
        self._resize()
        self.place_near(cat)
        self.entry.setFocus()


class TimePicker(PixelPanel):
    """自訂番茄鐘時間：− / + 調整，或點常用時間，按 Enter 開始。"""
    W = 280
    PRESETS = {"focus": (10, 20, 30, 45, 60, 90), "break": (3, 5, 10, 15, 20, 30)}

    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.kind = "focus"
        self.setFixedWidth(self.W)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(U * 2 + 8, U + 6, U * 2 + 8 + U, U * 2 + 10 + U)
        lay.setSpacing(8)
        self.title = QLabel()
        lay.addWidget(self._title_bar(pixel.tomato(1.0, 2), self.title, self.hide))
        lay.addSpacing(2)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch()
        minus = PixelButton(icon=pixel.icon_pixmap("minus", 2, (7, 7)))
        minus.setFixedSize(30, 30)
        minus.clicked.connect(lambda: self._bump(-1))
        row.addWidget(minus)
        self.value = QLineEdit()
        self.value.setAlignment(Qt.AlignCenter)
        self.value.setFixedWidth(84)
        self.value.setMaxLength(3)
        _style_line_edit(self.value)
        self.value.setFont(pixel.font(24))
        self.value.setStyleSheet(self.value.styleSheet().replace("font-size: 12px", "font-size: 24px"))
        self.value.textEdited.connect(self._clean)
        self.value.returnPressed.connect(self._start)
        row.addWidget(self.value)
        self.unit = QLabel()
        self.unit.setFont(pixel.font(12))
        self.unit.setStyleSheet("color: #3a3737;")
        row.addWidget(self.unit)
        plus = PixelButton(icon=pixel.icon_pixmap("plus", 2, (7, 7)))
        plus.setFixedSize(30, 30)
        plus.clicked.connect(lambda: self._bump(1))
        row.addWidget(plus)
        row.addStretch()
        lay.addLayout(row)

        self.chips = QHBoxLayout()
        self.chips.setSpacing(4)
        lay.addLayout(self.chips)

        # 最近使用（每一個都可以刪除）
        self.recent_box = QWidget()
        rl = QHBoxLayout(self.recent_box)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)
        self.recent_label = QLabel()
        self.recent_label.setFont(pixel.font(12))
        self.recent_label.setStyleSheet("color: #7a6a58;")
        rl.addWidget(self.recent_label)
        self.recent_row = QHBoxLayout()
        self.recent_row.setSpacing(6)
        rl.addLayout(self.recent_row)
        rl.addStretch()
        lay.addWidget(self.recent_box)

        self.hint = QLabel()
        self.hint.setFont(pixel.font(12))
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet("color: #7a6a58;")
        lay.addWidget(self.hint)

        foot = QHBoxLayout()
        foot.addStretch()
        self.cancel_btn = PixelButton()
        self.cancel_btn.clicked.connect(self.hide)
        foot.addWidget(self.cancel_btn)
        self.start_btn = PixelButton()
        self.start_btn.clicked.connect(self._start)
        foot.addWidget(self.start_btn)
        lay.addLayout(foot)

    def open(self, kind, cat):
        self.kind = kind
        if kind == "focus":
            current = (self.ctrl.recent["focus"] or [25])[0]
            self._title_icon.setPixmap(pixel.tomato(1.0, 2))
        else:
            current = self.ctrl.break_min
            self._title_icon.setPixmap(pixel.icon_pixmap("cup", 2))
        self.retranslate()
        while self.chips.count():
            w = self.chips.takeAt(0).widget()
            if w:
                w.deleteLater()
        for m in self.PRESETS[kind]:
            b = PixelButton(str(m))
            b.clicked.connect(lambda _=False, m=m: self._set(m))
            self.chips.addWidget(b)
        self._fill_recent()
        self._set(current)
        self.place_near(cat)
        self.value.setFocus()
        self.value.selectAll()

    def _fill_recent(self):
        while self.recent_row.count():
            w = self.recent_row.takeAt(0).widget()
            if w:
                w.deleteLater()
        items = self.ctrl.recent[self.kind]
        self.recent_box.setVisible(bool(items))
        for m in items:
            chip = QWidget()
            cl = QHBoxLayout(chip)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(0)
            b = PixelButton(str(m))
            b.clicked.connect(lambda _=False, m=m: self._set(m))
            cl.addWidget(b)
            x = PixelButton(icon=pixel.icon_pixmap("close", 1, (7, 7)))
            x.setFixedSize(16, 24)
            x.setToolTip(tr("delete"))
            x.clicked.connect(lambda _=False, m=m: self._forget(m))
            cl.addWidget(x)
            self.recent_row.addWidget(chip)
        self.adjustSize()

    def _forget(self, m):
        self.ctrl.forget_recent(self.kind, m)
        self._fill_recent()

    def retranslate(self):
        self.recent_label.setText(tr("recent"))
        self.title.setText(tr("pick_focus" if self.kind == "focus" else "pick_break"))
        self.unit.setText(tr("minutes"))
        self.hint.setText(tr("pick_hint_break") if self.kind == "break" else "")
        self.hint.setVisible(self.kind == "break")
        self.cancel_btn.setText(tr("cancel"))
        self.start_btn.setText(tr("start"))
        for b in (self.cancel_btn, self.start_btn):
            b.updateGeometry()

    def _minutes(self):
        try:
            return max(1, min(180, int(self.value.text())))
        except ValueError:
            return 25 if self.kind == "focus" else 5

    def _set(self, m):
        self.value.setText(str(max(1, min(180, m))))

    def _bump(self, d):
        self._set(self._minutes() + d)

    def _clean(self, text):
        digits = "".join(c for c in text if c.isdigit())
        if digits != text:
            self.value.setText(digits)

    def _start(self):
        m = self._minutes()
        self.hide()
        self.ctrl.picked(self.kind, m)

    def keyPressEvent(self, e):
        step = 5 if e.modifiers() & Qt.ShiftModifier else 1
        if e.key() == Qt.Key_Escape:
            self.hide()
        elif e.key() == Qt.Key_Up:
            self._bump(step)
        elif e.key() == Qt.Key_Down:
            self._bump(-step)
        else:
            super().keyPressEvent(e)


class Swatch(QAbstractButton):
    """像素風色塊按鈕。"""

    def __init__(self, rgb, parent=None):
        super().__init__(parent)
        self.rgb = tuple(rgb)
        self.setCheckable(True)
        self.setFixedSize(22, 22)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        r = self.rect().adjusted(1, 1, -2, -2)
        pixel.draw_box(p, r, 2, fill=QColor(*self.rgb), light=None, shadow=False)
        if self.isChecked():
            p.fillRect(QRect(r.left(), r.bottom() + 1, r.width(), 2), pixel.INK)
            p.fillRect(QRect(r.center().x() - 2, r.center().y() - 2, 4, 4), QColor(255, 255, 255))


class PaletteDialog(PixelPanel):
    """貓咪調色盤：選毛色和眼睛顏色，即時預覽，存成自己的貓。"""
    W = 360
    FURS = [(150, 150, 158), (112, 128, 150), (236, 218, 180), (214, 120, 60), (110, 70, 50),
            (228, 190, 90), (236, 170, 190), (180, 160, 220), (150, 210, 180), (140, 190, 230),
            (80, 80, 90), (245, 245, 245)]
    EYES = [(58, 55, 55), (60, 160, 80), (230, 190, 60), (80, 150, 230), (220, 140, 50),
            (180, 90, 50), (150, 90, 200), (200, 60, 60)]

    def __init__(self, ctrl):
        super().__init__()
        self.ctrl = ctrl
        self.target = None
        self.fur = self.FURS[1]
        self.eye = self.EYES[3]
        self.setFixedWidth(self.W)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(U * 2 + 8, U + 6, U * 2 + 8 + U, U * 2 + 10 + U)
        lay.setSpacing(6)
        self.title = QLabel()
        lay.addWidget(self._title_bar(pixel.icon_pixmap("palette", 2), self.title, self.hide))

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFixedHeight(150)
        lay.addWidget(self.preview)

        self.fur_label, self.fur_btns = self._swatch_row(lay, self.FURS, self._pick_fur, "fur")
        self.eye_label, self.eye_btns = self._swatch_row(lay, self.EYES, self._pick_eye, "eye")

        self.mine_label = QLabel()
        self.mine_label.setFont(pixel.font(12))
        self.mine_label.setStyleSheet("color: #7a6a58;")
        lay.addWidget(self.mine_label)
        self.mine_row = QHBoxLayout()
        self.mine_row.setSpacing(6)
        lay.addLayout(self.mine_row)

        foot = QHBoxLayout()
        foot.addStretch()
        self.cancel_btn = PixelButton()
        self.cancel_btn.clicked.connect(self.hide)
        foot.addWidget(self.cancel_btn)
        self.save_btn = PixelButton()
        self.save_btn.clicked.connect(self._save)
        foot.addWidget(self.save_btn)
        lay.addLayout(foot)

    def _swatch_row(self, lay, colors, handler, kind):
        label = QLabel()
        label.setFont(pixel.font(12))
        label.setStyleSheet("color: #3a3737;")
        lay.addWidget(label)
        row = QHBoxLayout()
        row.setSpacing(2)
        btns = []
        for rgb in colors:
            b = Swatch(rgb)
            b.clicked.connect(lambda _=False, rgb=rgb: handler(rgb))
            row.addWidget(b)
            btns.append(b)
        more = PixelButton("...")
        more.setFixedHeight(22)
        more.clicked.connect(lambda: self._more(kind))
        row.addWidget(more)
        row.addStretch()
        lay.addLayout(row)
        return label, btns

    def _more(self, kind):
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(*(self.fur if kind == "fur" else self.eye))
        c = QColorDialog.getColor(cur, self, tr("palette"))
        if c.isValid():
            (self._pick_fur if kind == "fur" else self._pick_eye)((c.red(), c.green(), c.blue()))
        self.raise_()

    def _pick_fur(self, rgb):
        self.fur = tuple(rgb)
        self._refresh()

    def _pick_eye(self, rgb):
        self.eye = tuple(rgb)
        self._refresh()

    def _refresh(self):
        for b in self.fur_btns:
            b.setChecked(b.rgb == self.fur)
        for b in self.eye_btns:
            b.setChecked(b.rgb == self.eye)
        sp = sprites.derive_spec(self.fur, self.eye)
        self.preview.setPixmap(sprites.preview_image(sp, 4).copy(0, int(60 * sprites._dpr()),
                                                                 int(128 * sprites._dpr()),
                                                                 int(132 * sprites._dpr())))

    def _fill_mine(self):
        while self.mine_row.count():
            w = self.mine_row.takeAt(0).widget()
            if w:
                w.deleteLater()
        names = self.ctrl.custom_color_names()
        self.mine_label.setVisible(bool(names))
        for cid in names:
            chip = QWidget()
            cl = QHBoxLayout(chip)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(0)
            b = PixelButton(icon=pixel.cat_head_icon(cid).pixmap(18, 18))
            b.setFixedSize(26, 26)
            b.setToolTip(names[cid])
            b.clicked.connect(lambda _=False, cid=cid: self._apply(cid))
            cl.addWidget(b)
            x = PixelButton(icon=pixel.icon_pixmap("close", 1, (7, 7)))
            x.setFixedSize(14, 26)
            x.setToolTip(tr("delete"))
            x.clicked.connect(lambda _=False, cid=cid: self._delete(cid))
            cl.addWidget(x)
            self.mine_row.addWidget(chip)
        self.mine_row.addStretch()
        self.adjustSize()

    def _apply(self, cid):
        if self.target in self.ctrl.cats:
            self.target.set_color(cid)

    def _delete(self, cid):
        self.ctrl.delete_custom_color(cid)
        self._fill_mine()

    def _save(self):
        cid = self.ctrl.add_custom_color(self.fur, self.eye)
        self._apply(cid)
        self.hide()

    def retranslate(self):
        self.title.setText(tr("palette_title"))
        self.fur_label.setText(tr("fur"))
        self.eye_label.setText(tr("eyes"))
        self.mine_label.setText(tr("my_colors"))
        self.cancel_btn.setText(tr("cancel"))
        self.save_btn.setText(tr("save_apply"))

    def open_for(self, cat):
        self.target = cat
        self.retranslate()
        self._fill_mine()
        self._refresh()
        self.place_near(cat)


class Food(QWidget):
    """從天上掉下來的罐罐。"""

    def __init__(self, x, top, ground_y, scale, on_land, flavor="tuna"):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                            | Qt.WindowTransparentForInput | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.flavor = flavor
        self.pm = sprites.effect("can_" + flavor, scale)
        dpr = self.pm.devicePixelRatio()
        self.setFixedSize(int(self.pm.width() / dpr), int(self.pm.height() / dpr))
        self.ground = ground_y - self.height()
        self.fy = float(top)
        self.vy = 0.0
        self.on_land = on_land
        self.move(int(x - self.width() / 2), top)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.CoarseTimer)
        self.timer.timeout.connect(self._fall)
        self.show()
        show_on_all_spaces(self)
        self.timer.start(33)

    def center_x(self):
        return self.x() + self.width() // 2

    def _fall(self):
        self.vy = min(self.vy + 1.6, 30)
        self.fy += self.vy
        if self.fy >= self.ground:
            self.fy = self.ground
            self.timer.stop()
            self.move(self.x(), int(self.fy))
            self.on_land(self)
            return
        self.move(self.x(), int(self.fy))

    def paintEvent(self, _e):
        QPainter(self).drawPixmap(0, 0, self.pm)
