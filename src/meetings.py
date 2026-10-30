"""會議提醒：讀「行事曆」裡接下來的活動，開始前 5 分鐘貓咪跑來提醒你（預設關閉）。

打開時 macOS 會問一次要不要讓喵動力讀取行事曆。只在本機讀，不會上傳任何東西。
需要 pyobjc 的 EventKit（打包好的 App 已經內建；從原始碼執行時用 requirements.txt 安裝）。
"""
import time

from PySide6.QtCore import QObject, Qt, QTimer, Signal

try:
    import EventKit  # type: ignore
    from Foundation import NSDate  # type: ignore
except Exception:                                # 沒有 pyobjc（或不是 macOS）
    EventKit = None

CHECK_MS = 60_000
AHEAD_S = 5 * 60


class Meetings(QObject):
    soon = Signal(str, int)                      # 活動名稱、還有幾分鐘

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.store = None
        self.granted = False
        self._asked = False
        self._told = {}                          # 已經提醒過的活動
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.VeryCoarseTimer)
        self.timer.timeout.connect(self.check)
        if self.enabled():
            QTimer.singleShot(5000, self._start)

    @staticmethod
    def available():
        return EventKit is not None

    def enabled(self):
        return self.available() and str(self.settings.value("meetings_on", "0")) == "1"

    def set_enabled(self, on):
        self.settings.setValue("meetings_on", "1" if on else "0")
        if on:
            self._start()
        else:
            self.timer.stop()

    def _start(self):
        if not self.available():
            return
        if self.store is None:
            self.store = EventKit.EKEventStore.alloc().init()
        if not self._asked:
            self._asked = True

            def done(granted, _err):
                self.granted = bool(granted)     # 這是在別的執行緒，只設旗標，由計時器去讀
            if hasattr(self.store, "requestFullAccessToEventsWithCompletion_"):
                self.store.requestFullAccessToEventsWithCompletion_(done)
            else:
                self.store.requestAccessToEntityType_completion_(EventKit.EKEntityTypeEvent, done)
        self.timer.start(CHECK_MS)
        QTimer.singleShot(3000, self.check)

    def check(self):
        if not self.enabled() or self.store is None:
            return
        status = EventKit.EKEventStore.authorizationStatusForEntityType_(EventKit.EKEntityTypeEvent)
        if status not in (3, 4) and not self.granted:      # 3 = 已授權，4 = 完整存取（macOS 14+）
            return
        try:
            start = NSDate.date()
            end = NSDate.dateWithTimeIntervalSinceNow_(AHEAD_S + 60)
            pred = self.store.predicateForEventsWithStartDate_endDate_calendars_(start, end, None)
            events = self.store.eventsMatchingPredicate_(pred) or []
        except Exception:
            return
        now = time.time()
        self._told = {k: t for k, t in self._told.items() if now - t < 3 * 3600}
        for e in events:
            if e.isAllDay():
                continue
            left = e.startDate().timeIntervalSinceNow()
            key = str(e.eventIdentifier()) + str(e.startDate())
            if 0 < left <= AHEAD_S + 30 and key not in self._told:
                self._told[key] = now
                self.soon.emit(str(e.title() or ""), max(1, int(round(left / 60))))
