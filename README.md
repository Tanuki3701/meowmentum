# 🐱 Desktop Cat

一隻住在 macOS 桌面上的像素小貓。牠可以乖乖待著、在螢幕上隨意散步，或是跟著你的滑鼠走。

![orange cat](assets/icon.png)

## 功能

- **三種模式**：待著不動／隨意漫步（走到定點會停下休息）／跟著滑鼠
- **四種毛色**：黑、白、橘、棕
- **三種大小**：小、中、大
- **拖曳**：用滑鼠左鍵按住貓咪就能把牠搬到別的地方
- **右鍵選單**（觸控板雙指點按）：切換顏色、模式、方向、大小，或結束程式
- 會記住你上次的設定和貓咪位置
- 不佔 Dock、不出現在 Cmd+Tab，會出現在所有桌面（Spaces）
- 支援 Retina 與多螢幕

## 省電設計

| 以前 | 現在 |
| --- | --- |
| 1920×1080 的透明全螢幕視窗，每次移動整個視窗都要重繪 | 視窗只有貓咪大小，移動時幾乎不需重繪 |
| 不管什麼模式，計時器每秒都喚醒 60 次 | 待著不動時**完全沒有計時器**（CPU 0%）；移動中 30fps |
| 每一格都重新裁切、縮放圖片 | 啟動時一次切好放大並快取 |
| 跟隨模式一直全速檢查滑鼠 | 貓咪在滑鼠旁時改為每 0.25 秒檢查一次 |
| 漫步模式永遠不停 | 走到目的地會休息 2–7 秒，休息時計時器關閉 |

## 安裝

需要 macOS 與 Python 3.9 以上（沒有的話先在終端機執行 `xcode-select --install`）。

### 方法一：打包成 App（推薦）

```bash
git clone https://github.com/Tanuki3701/desktop-cat.git
cd desktop-cat
bash build_mac.sh
```

完成後會出現在「應用程式」資料夾，之後用 Spotlight 搜尋 **DesktopCat** 就能開啟。

> 想讓貓咪開機自動出現：系統設定 → 一般 → 登入項目 → 按 ＋ 加入 DesktopCat。

### 方法二：直接執行原始碼

在終端機執行 `bash run.command`（第一次會自動安裝套件）。

> 想在 Finder 直接雙擊 `run.command`：先執行一次 `chmod +x run.command`。

或手動執行：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python src/main.py
```

## 結束程式

在貓咪身上按右鍵 → **結束**。

## 專案結構

```
desktop-cat/
├── src/
│   ├── main.py        # 程式進入點
│   ├── cat.py         # 貓咪視窗：動畫、移動、選單
│   └── macos.py       # macOS 專用：隱藏 Dock 圖示、出現在所有桌面
├── assets/
│   ├── sprites/       # 32×48 像素貓咪圖（4 方向 × 3 格）
│   └── icon.png       # App 圖示
├── DesktopCat.spec    # PyInstaller 打包設定
├── build_mac.sh       # 一鍵打包並安裝
└── run.command        # 雙擊直接執行
```
