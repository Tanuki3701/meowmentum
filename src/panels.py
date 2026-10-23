"""待辦清單面板與罐罐。"""
import json

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout, QWidget)

import sprites
from macos import show_on_all_spaces

NOTE_STYLE = """
QWidget#note { background: #fff6dd; border: 2px solid #3a3737; border-radius: 12px; }
QLabel { color: #3a3737; font-weight: bold; font-size: 15px; }
QListWidget { background: transparent; border: none; color: #3a3737; font-size: 14px; }
QListWidget::item { padding: 3px 2px; }
QLineEdit { background: #fffdf7; border: 1px solid #c9b98f; border-radius: 6px;
            padding: 4px 6px; color: #3a3737; font-size: 13px; }
QPushButton { background: transparent; border: none; color: #996b4a; font-size: 12px; }
QPushButton:hover { color: #3a3737; }
"""


class TodoPanel(QWidget):
    def __init__(self, ctrl):
        super().__init__(None)
        self.ctrl = ctrl
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setFixedWidth(260)

        note = QWidget(self)
        note.setObjectName("note")
        note.setStyleSheet(NOTE_STYLE)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(note)

        lay = QVBoxLayout(note)
        lay.setContentsMargins(14, 10, 14, 10)
        head = QHBoxLayout()
        head.addWidget(QLabel("📝 今天要做的事"))
        head.addStretch()
        close = QPushButton("✕")
        close.clicked.connect(self.hide)
        head.addWidget(close)
        lay.addLayout(head)

        self.list = QListWidget()
        self.list.setMinimumHeight(140)
        self.list.itemChanged.connect(self._changed)
        lay.addWidget(self.list)

        self.entry = QLineEdit()
        self.entry.setPlaceholderText("新增事項，按 Enter")
        self.entry.returnPressed.connect(self._add)
        lay.addWidget(self.entry)

        foot = QHBoxLayout()
        self.count = QLabel()
        self.count.setStyleSheet("font-size: 12px; font-weight: normal;")
        foot.addWidget(self.count)
        foot.addStretch()
        clear = QPushButton("清除已完成")
        clear.clicked.connect(self._clear_done)
        foot.addWidget(clear)
        lay.addLayout(foot)

        self._loading = False
        self._all_done = False
        self._load()

    # ---------------- 資料 ---------------- #
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
        self._update_count()

    def _save(self):
        items = [{"t": self.list.item(i).text(),
                  "d": self.list.item(i).checkState() == Qt.Checked}
                 for i in range(self.list.count())]
        self.ctrl.settings.setValue("todos", json.dumps(items, ensure_ascii=False))

    def _append(self, text, done=False):
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
        item.setCheckState(Qt.Checked if done else Qt.Unchecked)
        self.list.addItem(item)

    def _is_all_done(self):
        n = self.list.count()
        return n > 0 and all(self.list.item(i).checkState() == Qt.Checked for i in range(n))

    def _update_count(self):
        n = self.list.count()
        done = sum(self.list.item(i).checkState() == Qt.Checked for i in range(n))
        self.count.setText(f"完成 {done} / {n}" if n else "還沒有事項")

    # ---------------- 事件 ---------------- #
    def _add(self):
        text = self.entry.text().strip()
        if text:
            self._append(text)
            self.entry.clear()
            self._changed()

    def _clear_done(self):
        for i in reversed(range(self.list.count())):
            if self.list.item(i).checkState() == Qt.Checked:
                self.list.takeItem(i)
        self._changed()

    def _changed(self, *_):
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
        elif e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.list.hasFocus():
            row = self.list.currentRow()
            if row >= 0:
                self.list.takeItem(row)
                self._changed()
        else:
            super().keyPressEvent(e)

    def toggle_near(self, cat):
        if self.isVisible():
            self.hide()
            return
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
        from PySide6.QtGui import QPainter
        QPainter(self).drawPixmap(0, 0, self.pm)
