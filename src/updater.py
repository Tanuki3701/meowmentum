"""檢查 GitHub 上有沒有新版本（一天最多一次，只讀公開的 Releases 資訊，不傳送任何個人資料）。"""
import json
import time

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

from version import REPO, VERSION

CHECK_EVERY = 24 * 3600


def _ver(s):
    out = []
    for part in s.lstrip("vV").split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        out.append(int(num or 0))
    return tuple(out + [0] * (3 - len(out)))


class Updater(QObject):
    found = Signal(str, str)        # 版本、下載頁網址

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.net = None
        self.latest = None

    def check(self, force=False):
        last = float(self.settings.value("update_checked", 0) or 0)
        if not force and time.time() - last < CHECK_EVERY:
            cached = self.settings.value("update_latest")
            if cached and _ver(cached) > _ver(VERSION):
                self.latest = (cached, f"https://github.com/{REPO}/releases/latest")
                self.found.emit(*self.latest)
            return
        if self.net is None:
            self.net = QNetworkAccessManager(self)
        req = QNetworkRequest(QUrl(f"https://api.github.com/repos/{REPO}/releases/latest"))
        req.setRawHeader(b"Accept", b"application/vnd.github+json")
        req.setRawHeader(b"User-Agent", f"Meowmentum/{VERSION}".encode())
        reply = self.net.get(req)
        reply.finished.connect(lambda: self._done(reply))

    def _done(self, reply):
        try:
            data = json.loads(bytes(reply.readAll()).decode() or "{}")
        except Exception:
            data = {}
        reply.deleteLater()
        tag = data.get("tag_name")
        if not tag:
            return
        self.settings.setValue("update_checked", time.time())
        self.settings.setValue("update_latest", tag)
        if _ver(tag) > _ver(VERSION):
            self.latest = (tag, data.get("html_url") or f"https://github.com/{REPO}/releases/latest")
            self.found.emit(*self.latest)
