"""時間與季節：白天黑夜、深夜、節慶裝飾（全部照電腦時間判斷，不需要網路）。"""
import datetime as dt

# 農曆新年（大年初一）
LUNAR_NEW_YEAR = {
    2025: (1, 29), 2026: (2, 17), 2027: (2, 6), 2028: (1, 26), 2029: (2, 13), 2030: (2, 3),
    2031: (1, 23), 2032: (2, 11), 2033: (1, 31), 2034: (2, 19), 2035: (2, 8),
}


def now():
    return dt.datetime.now()


def is_night(t=None):
    h = (t or now()).hour
    return h >= 18 or h < 6


def is_late_night(t=None):
    h = (t or now()).hour
    return 0 <= h < 5


def _near_lny(d):
    for y in (d.year, d.year + 1):
        if y in LUNAR_NEW_YEAR:
            m, day = LUNAR_NEW_YEAR[y]
            lny = dt.date(y, m, day)
            if -10 <= (d - lny).days <= 15:
                return True
    return False


def decorations(t=None):
    """回傳目前要顯示的節慶裝飾集合。"""
    d = (t or now()).date()
    out = set()
    if (d.month == 10 and d.day >= 15) or (d.month == 11 and d.day <= 2):
        out.add("halloween")
    if d.month == 12 and d.day <= 26:
        out.add("xmas")
    if d.month in (12, 1, 2):
        out.add("snow")
    if _near_lny(d):
        out.add("lny")
    if d.month in (3, 4):
        out.add("spring")
    return out


def seasonal_hats(t=None):
    """節慶限定、免費就能戴的帽子。"""
    deco = decorations(t)
    hats = []
    if "halloween" in deco:
        hats.append("witch")
    d = (t or now()).date()
    if d.month == 12 or (d.month == 1 and d.day <= 6):
        hats.append("santa")
    return hats
