"""養成：小魚乾、專注紀錄、商店物品。

全部存在 QSettings（和其他設定同一個地方），只記錄每天專注了幾分鐘、幾次。
"""
import datetime as dt
import json

import seasons

WELCOME_COINS = 10

# id: (種類, 價格)。種類：hat / neck / desk（桌面家具）/ room（貓屋裡的擺設）
ITEMS = {
    "flower": ("hat", 8), "party": ("hat", 12), "beanie": ("hat", 15), "crown": ("hat", 25),
    "collar": ("neck", 10), "bowtie": ("neck", 10), "scarf": ("neck", 12),
    "box": ("desk", 15), "tree": ("desk", 30),
    "rug": ("room", 10), "plant": ("room", 8), "lamp": ("room", 12), "painting": ("room", 10),
    "scratcher": ("room", 15), "fishtank": ("room", 25), "yarn": ("room", 5),
}
SEASONAL = {"witch": "hat", "santa": "hat"}     # 節慶限定，免費
KINDS = ["hat", "neck", "desk", "room"]


def today():
    return dt.date.today()


class Progress:
    def __init__(self, settings):
        self.s = settings
        if self.s.value("coins") is None:
            self.s.setValue("coins", WELCOME_COINS)
        self.coins = int(self.s.value("coins", WELCOME_COINS))
        self.log = self._json("focus_log", {})          # "2026-10-29": [分鐘, 次數]
        self.owned = set(self._json("owned_items", []))
        self.placed = set(self._json("placed_items", []))  # 放在桌面上的家具

    def _json(self, key, default):
        try:
            return json.loads(self.s.value(key) or json.dumps(default))
        except Exception:
            return default

    def _save(self):
        self.s.setValue("coins", self.coins)
        self.s.setValue("focus_log", json.dumps(self.log))
        self.s.setValue("owned_items", json.dumps(sorted(self.owned)))
        self.s.setValue("placed_items", json.dumps(sorted(self.placed)))

    # ---------------- 小魚乾 ---------------- #
    def add_coins(self, n):
        self.coins = max(0, self.coins + n)
        self._save()

    @staticmethod
    def reward_for(minutes):
        return max(1, minutes // 5)

    # ---------------- 專注紀錄 ---------------- #
    def record_focus(self, minutes, day=None):
        k = (day or today()).isoformat()
        m, n = self.log.get(k, [0, 0])
        self.log[k] = [m + minutes, n + 1]
        self._save()

    def day(self, d):
        return self.log.get(d.isoformat(), [0, 0])

    def streak(self):
        """連續有專注的天數（今天還沒專注也不會中斷，從昨天開始算）。"""
        d = today()
        if self.day(d)[1] == 0:
            d -= dt.timedelta(days=1)
        n = 0
        while self.day(d)[1] > 0:
            n += 1
            d -= dt.timedelta(days=1)
        return n

    def totals(self):
        mins = sum(v[0] for v in self.log.values())
        sessions = sum(v[1] for v in self.log.values())
        return mins, sessions

    # ---------------- 物品 ---------------- #
    def has(self, item):
        return item in self.owned or item in seasons.seasonal_hats()

    def buy(self, item):
        if item in self.owned or item not in ITEMS:
            return False
        price = ITEMS[item][1]
        if self.coins < price:
            return False
        self.coins -= price
        self.owned.add(item)
        self._save()
        return True

    def owned_of(self, kind):
        out = [i for i, (k, _) in ITEMS.items() if k == kind and i in self.owned]
        if kind == "hat":
            out = seasons.seasonal_hats() + out
        return out

    def set_placed(self, item, on):
        (self.placed.add if on else self.placed.discard)(item)
        self._save()
