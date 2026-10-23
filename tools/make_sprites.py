"""用原始精靈圖的調色盤產生額外動作（睡覺、愛心、Zzz、罐頭）。

執行：python3 tools/make_sprites.py
會在 assets/sprites/ 產生 cat_<color>-extra.png（32x48 一格）。
"""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SPRITES = os.path.join(HERE, "..", "assets", "sprites")

# 語意色 → 各顏色調色盤索引（由原圖逐像素比對而來）
#  O 外框  D 深色陰影  M 中間色  L 亮色  P 粉紅（耳內/鼻）  R 腮紅
PALETTE_MAP = {
    "orange": dict(O=1, R=2, D=3, P=4, M=5, L=6),
    "black":  dict(O=3, R=6, D=1, P=7, M=2, L=4),
    "white":  dict(O=1, R=3, D=2, P=5, M=4, L=6),
    "brown":  dict(O=2, R=5, D=1, P=6, M=3, L=4),
}
SYM = {0: ".", 1: "O", 2: "R", 3: "D", 4: "P", 5: "M", 6: "L"}  # 橘貓索引 → 語意


def read_orange_frame(row, col):
    im = Image.open(os.path.join(SPRITES, "cat_orange-32x48.png"))
    return [[SYM[im.getpixel((col * 32 + x, row * 48 + y))] for x in range(32)] for y in range(48)]


def blank():
    return [["."] * 32 for _ in range(48)]


def put(grid, x, y, text):
    for i, ch in enumerate(text):
        if ch != " " and 0 <= x + i < 32 and 0 <= y < 48:
            grid[y][x + i] = ch


def sleep_frame(breath):
    """趴著睡覺（面向右），breath=1 時背部吸氣隆起一格。"""
    side = read_orange_frame(1, 1)
    g = blank()
    b = breath
    # ---- 尾巴：從屁股繞到肚子前面（先畫，會被身體蓋住一部分）----
    put(g, 2, 39, "ODO")
    put(g, 2, 40, "OMDO")
    put(g, 2, 41, "OMMDOOOOOOOOOO")
    put(g, 3, 42, "OMMMMMMMMMLLLO")
    put(g, 4, 43, "OOOOOOOOOOOOO")
    # ---- 身體（圓滾滾的貓麵包）----
    put(g, 9, 33 - b, "DDDDDDDDD")
    put(g, 7, 34 - b, "DDMMMMMMMMMDD")
    put(g, 6, 35 - b, "DMMLLLMMMLLLMMD")
    for y in range(36 - b, 40):
        put(g, 5, y, "DMLLLLLLLLLLLLLLD")
    put(g, 5, 40, "DMMLLLLLLLLLLLLMD")
    put(g, 6, 41, "DMMMMMMMMMMMMMD")
    put(g, 7, 42, "ODDDDDDDDDDDDO")
    # ---- 頭：沿用原圖側臉，放低，眼睛改成閉眼 ----
    dy = 6
    for y in range(23, 35):
        for x in range(16, 30):
            ch = side[y][x]
            if ch != ".":
                g[y + dy][x] = ch
    # 原本睜開的眼睛 (24,29)(24,30) → 往下彎的閉眼線
    g[29 + dy][24] = "L"
    g[30 + dy][24] = "L"
    g[30 + dy][23] = "O"
    g[31 + dy][24] = "O"
    g[31 + dy][25] = "O"
    # ---- 前腳墊在下巴下面 ----
    put(g, 19, 40, "OMLLLLMO")
    put(g, 19, 41, "OMLLOLLMO")
    put(g, 19, 42, "OOOOOOOOO")
    return g


def heart():
    g = blank()
    art = [
        " OO OO ",
        "ORROPPO",
        "ORPPPPO",
        " ORPPO ",
        "  OPO  ",
        "   O   ",
    ]
    for i, line in enumerate(art):
        put(g, 0, i, line)
    return g


def zzz():
    g = blank()
    art = [
        "OOOOO",
        "   O ",
        "  O  ",
        " O   ",
        "OOOOO",
    ]
    for i, line in enumerate(art):
        put(g, 0, i, line)
    return g


def can():
    g = blank()
    art = [
        " OOOOOOOO ",
        "ODDDDDDDDO",
        "OLLLLLLLLO",
        "ORRRRRRRRO",
        "ORLLRRLLRO",
        "ORRRRRRRRO",
        "OMMMMMMMMO",
        " OOOOOOOO ",
    ]
    for i, line in enumerate(art):
        put(g, 0, i, line)
    return g


def grid_to_image(grids, color):
    """grids: 一排的格子 → 32*n x 48 的 P 模式圖，沿用原調色盤。"""
    src = Image.open(os.path.join(SPRITES, f"cat_{color}-32x48.png"))
    out = Image.new("P", (32 * len(grids), 48), 0)
    out.putpalette(src.getpalette())
    mapping = PALETTE_MAP[color]
    for i, g in enumerate(grids):
        for y in range(48):
            for x in range(32):
                ch = g[y][x]
                if ch != ".":
                    out.putpixel((i * 32 + x, y), mapping[ch])
    out.info["transparency"] = 0
    return out


def main():
    # 睡姿（每種毛色各一張）：格 0 = 呼氣、格 1 = 吸氣
    sleep = [sleep_frame(0), sleep_frame(1)]
    for color in PALETTE_MAP:
        grid_to_image(sleep, color).save(
            os.path.join(SPRITES, f"cat_{color}-sleep.png"), transparency=0)
    # 特效（固定用橘貓調色盤）：格 0 愛心、1 Zzz、2 罐頭
    grid_to_image([heart(), zzz(), can()], "orange").save(
        os.path.join(SPRITES, "effects.png"), transparency=0)
    print("done")


if __name__ == "__main__":
    main()
