"""天氣：下雨、下雪、起霧時，貓屋外面和窗戶裡都看得到（預設關閉，要在設定裡打開）。

打開後才會連網：用 IP 查大概的城市位置（一天一次），再向 Open-Meteo 查目前的天氣（30 分鐘一次）。
不需要帳號，也不會傳送任何個人資料；只存下大概的經緯度。
"""
import json
import time

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

from version import VERSION

KINDS = ["clear", "cloudy", "fog", "rain", "snow", "storm"]
EVERY_MS = 30 * 60 * 1000
LOCATE_EVERY = 24 * 3600


def kind_of(code):
    """WMO 天氣代碼 → 簡單的種類。"""
    if code is None:
        return None
    code = int(code)
    if code in (0, 1):
        return "clear"
    if code in (2, 3):
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code >= 95:
        return "storm"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    return "cloudy"


class Weather(QObject):
    changed = Signal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.kind = None
        self.city = ""
        self.net = None
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.VeryCoarseTimer)
        self.timer.timeout.connect(self.refresh)
        if self.enabled():
            QTimer.singleShot(4000, self.refresh)
            self.timer.start(EVERY_MS)

    def enabled(self):
        return str(self.settings.value("weather_on", "0")) == "1"

    def set_enabled(self, on):
        self.settings.setValue("weather_on", "1" if on else "0")
        if on:
            self.refresh()
            self.timer.start(EVERY_MS)
        else:
            self.timer.stop()
            self._set(None)

    def set_kind(self, kind):
        """測試或截圖用：直接指定天氣。"""
        self._set(kind)

    def _set(self, kind):
        if kind != self.kind:
            self.kind = kind
            self.changed.emit(kind or "")

    # ---------------- 連網 ---------------- #
    def _get(self, url, done):
        if self.net is None:
            self.net = QNetworkAccessManager(self)
        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"User-Agent", f"Meowmentum/{VERSION}".encode())
        req.setTransferTimeout(15000)
        reply = self.net.get(req)

        def finished():
            try:
                data = json.loads(bytes(reply.readAll()).decode() or "{}")
            except Exception:
                data = {}
            reply.deleteLater()
            done(data)
        reply.finished.connect(finished)

    def refresh(self):
        if not self.enabled():
            return
        lat, lon = self.settings.value("weather_lat"), self.settings.value("weather_lon")
        when = float(self.settings.value("weather_located", 0) or 0)
        if lat is None or lon is None or time.time() - when > LOCATE_EVERY:
            self._get("https://ipapi.co/json/", self._located)
        else:
            self._fetch(lat, lon)

    def _located(self, data):
        lat, lon = data.get("latitude"), data.get("longitude")
        if lat is None or lon is None:
            lat, lon = self.settings.value("weather_lat"), self.settings.value("weather_lon")
            if lat is None:
                return
        else:
            self.settings.setValue("weather_lat", round(float(lat), 2))
            self.settings.setValue("weather_lon", round(float(lon), 2))
            self.settings.setValue("weather_located", time.time())
            self.city = data.get("city") or ""
        self._fetch(lat, lon)

    def _fetch(self, lat, lon):
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={float(lat):.2f}&longitude={float(lon):.2f}"
               "&current=weather_code,is_day")
        self._get(url, lambda d: self._set(kind_of((d.get("current") or {}).get("weather_code"))))
