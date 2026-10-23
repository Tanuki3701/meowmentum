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


class TodoPanel(QWidget):
    W = 290

    def __init__(self, ctrl):
        super().__init__(None)
        self.ctrl = ctrl
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setFixedWidth(self.W)
        self._drag = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(U * 2 + 8, U + 6, U * 2 + 8 + U, U * 2 + 10 + U)
        lay.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(6)
        icon = QLabel()
        icon.setPixmap(pixel.icon_pixmap("note", 2))
        head.addWidget(icon)
        self.title = QLabel()
        self.title.setFont(pixel.font(12))
        self.title.setStyleSheet("color: #3a3737;")
        head.addWidget(self.title)
        head.addStretch()
        close = PixelButton(icon=pixel.icon_pixmap("close", 2, (7, 7)))
        close.clicked.connect(self.hide)
        head.addWidget(close)
        head_box = QWidget()
        head_box.setFixedHeight(TITLE_H - U - 6)
        head_box.setLayout(head)
        head.setContentsMargins(0, 0, 0, 0)
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
    def paintEvent(self, _e):
        p = QPainter(self)
        r = self.rect().adjusted(0, 0, -U, -U)
        pixel.draw_box(p, r, U)
        band = QRect(r.left() + U, r.top() + U, r.width() - 2 * U, TITLE_H - U)
        p.fillRect(band, pixel.GOLD)
        p.fillRect(QRect(band.left(), band.top(), band.width(), U), QColor(248, 224, 160))
        p.fillRect(QRect(band.left(), band.bottom() + 1, band.width(), U), pixel.INK)

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

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and e.position().y() < TITLE_H:
            self._drag = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

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
        self.entry.setFocus()


class Food(QWidget):
    """從天上掉下來的罐罐。"""

    def __init__(self, x, top, ground_y, scale, on_land):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                            | Qt.WindowTransparentForInput | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.pm = sprites.effect("can", scale)
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
