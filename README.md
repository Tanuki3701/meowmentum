# Meowmentum 喵動力

Meowmentum is a tiny pixel cat that lives on your macOS desktop and keeps your momentum going. It wanders around, follows your cursor, hops onto your windows, keeps you company while you focus, and takes a nap when you step away.

[繁體中文說明](#繁體中文)

![Meowmentum](docs/screenshots/hero.png)

## Features

### Companion

- **Five modes.** The cat can stay put, wander, follow your cursor, walk on top of other apps' windows, or sleep.
- **Walk on windows.** The cat jumps onto window title bars and strolls along them. It rides along when you drag a window, and it falls down when the window closes.
- **Naps.** After a few idle minutes, the cat curls up and sleeps. It wakes up as soon as you come back. Choose the Sleep mode if you want the cat to keep sleeping. In Sleep mode, clicking the cat gives it a pat without waking it up.
- **Petting.** Move the cursor back and forth over the cat, and it purrs and shows hearts.
- **Treats.** Drop a can of food from the top of the screen, and the cat runs over to eat it.
- **More cats.** Adopt several cats in different colors. Each one remembers its own settings.
- **Customizable.** Choose from four coat colors and three sizes. Drag the cat anywhere with the left mouse button.

![Sleeping, petting, and feeding](docs/screenshots/sleep-pet-feed.png)

![Walking on windows](docs/screenshots/walk-on-windows.png)

### Productivity

- **Pomodoro timer.** Focus for 15, 25, or 50 minutes, or set your own time. A pixel tomato above the cat ripens as time passes. It starts yellow-green, turns yellow-orange halfway, and becomes red when time is up. Then the cat walks to the middle of the screen to remind you, and a break starts automatically.
- **Custom focus and break times.** Pick any length from 1 to 180 minutes with the plus and minus buttons, the arrow keys, or the quick presets. Your last custom focus time stays in the menu, and your break length is used after every focus session.
- **To-do list.** Click the cat to open a game-style quest log. When every quest is checked, the cat spins with joy.
- **Break reminders.** Every 30, 45, or 60 minutes, the cat reminds you to stretch, drink water, or rest your eyes. It stays quiet while you focus or when you are away.
- **Low battery alerts.** Below 20% battery, the cat gets sleepy and asks you to charge. When you plug in, it thanks you.

![Pomodoro tomato changes color over time](docs/screenshots/pomodoro.png)

![Custom focus time](docs/screenshots/custom-time.png)

![To-do list](docs/screenshots/todo.png)

### Design

- **Glass menu.** The right-click menu uses the native macOS frosted-glass material with a soft transparent gradient and pixel-art icons. Submenus open instantly.
- **Pixel-art dialogs.** Speech bubbles and the to-do list look like a retro game, with a pixel font that supports both English and Traditional Chinese.
- **English and Traditional Chinese.** Switch languages any time from the menu. The first launch follows your system language.

![Glass menu in English](docs/screenshots/menu-en.png)

## Battery-friendly by design

| Area | How it saves power |
| --- | --- |
| Windows | Each cat is a window exactly the size of the cat, so moving it costs almost nothing. |
| Timers | Timers run only when needed. Movement is 30 fps, and cats rest between walks. |
| Background checks | One light check every 0.4 seconds detects idle time and petting. |
| Sleeping | A sleeping cat only breathes once per second. |
| Images | Sprites are cut, scaled, and cached once at startup. |
| Battery | The battery is read once every 2 minutes. |
| Window detection | Window positions are read only in "Walk on windows" mode. Window contents are never read, so no screen-recording permission is needed. |

## Install

You need macOS and Python 3.9 or later. If you do not have Python, run `xcode-select --install` in Terminal first.

### Option 1: Build the app (recommended)

```bash
git clone https://github.com/Tanuki3701/meowmentum.git
cd meowmentum
bash build_mac.sh
```

The app is installed to your Applications folder. After that, open it from Spotlight or Launchpad by searching for **Meowmentum**.

To start the cat automatically when you log in, open System Settings, go to General, then Login Items, and add Meowmentum.

### Option 2: Run from source

Run `bash run.command` in Terminal. The first run installs the dependencies automatically.

You can also run it manually.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python src/main.py
```

## Usage

- **Right-click** the cat (or two-finger click on a trackpad) to open the menu.
- **Click** the cat to open the to-do list. Click a sleeping cat to wake it up.
- **Drag** the cat with the left mouse button to move it.
- To quit, right-click the cat and choose **Quit**.

## Project structure

```
meowmentum/
├── src/
│   ├── main.py          # Entry point
│   ├── controller.py    # Manages all cats and global features
│   ├── cat.py           # One cat: animation, movement, jumping
│   ├── overlay.py       # Pixel speech bubble and effects above the cat
│   ├── panels.py        # Pixel to-do list and the falling treat
│   ├── glassmenu.py     # Frosted-glass right-click menu
│   ├── pixel.py         # Pixel font, pixel icons, the ripening tomato, dialog frames
│   ├── i18n.py          # English and Traditional Chinese strings
│   ├── sprites.py       # Sprite loading and caching
│   └── macos.py         # macOS helpers: Dock icon, Spaces, idle time, window positions, glass
├── assets/
│   ├── sprites/         # 32x48 cat sprites (walking and sleeping) and effects
│   ├── fonts/           # Fusion Pixel font (SIL OFL 1.1)
│   └── icon.png         # App icon
├── tools/
│   ├── make_sprites.py      # Generates the sleeping sprites from the original palette
│   └── make_screenshots.py  # Generates the screenshots in this README
├── docs/screenshots/    # README images
├── Meowmentum.spec      # PyInstaller build settings
├── build_mac.sh         # One-step build and install
└── run.command          # Run from source
```

## Credits

- The pixel font is [Fusion Pixel Font](https://fusion-pixel-font.takwolf.com) by TakWolf, licensed under the SIL Open Font License 1.1. See `assets/fonts/LICENSE-fusion-pixel.txt`.
- The sleeping sprites were drawn pixel by pixel with the original sprite palette so that they match the original style.

---

## 繁體中文

喵動力（Meowmentum）是一隻住在 macOS 桌面上的像素小貓，陪你保持前進的動力。牠會散步、跟著滑鼠、跳到視窗上走、陪你專注，你離開電腦時牠就趴著睡覺。

### 功能

#### 陪伴

- **五種模式。** 待著不動、隨意漫步、跟著滑鼠、在其他 App 的視窗上走，或是睡覺。
- **在視窗上走。** 貓咪會跳到視窗頂端散步。你拖動視窗時牠會跟著移動，視窗關掉時牠會掉下來。
- **睡覺。** 一段時間沒碰電腦，貓咪會趴下來睡覺。你一回來牠就醒了。如果想一直看貓咪睡覺，可以選「睡覺」模式。在睡覺模式下點貓咪只會摸摸頭，不會把牠吵醒。
- **摸摸。** 滑鼠在貓咪身上來回滑動，牠會呼嚕呼嚕並冒出愛心。
- **餵罐罐。** 天上會掉下一個罐頭，貓咪會跑過去吃。
- **多隻貓。** 可以同時養好幾隻不同顏色的貓，每隻都會記住自己的設定。
- **自訂外觀。** 有四種毛色和三種大小，用滑鼠左鍵就能把貓咪拖到任何地方。

#### 實用

- **番茄鐘。** 可以專注 15、25 或 50 分鐘，也可以自訂時間。貓咪頭上的像素番茄會隨時間變色，一開始是黃綠色，過一半變成黃橘色，時間到了變成紅色。時間到時貓咪會走到畫面中間提醒你，接著自動開始休息。
- **自訂專注與休息時間。** 可以用加減按鈕、方向鍵或常用時間按鈕，選 1 到 180 分鐘。上次自訂的專注時間會留在選單裡，設定好的休息長度也會套用在之後每次專注結束時。
- **待辦清單。** 點一下貓咪就會打開遊戲風格的任務欄。全部打勾時，貓咪會開心轉圈。
- **休息提醒。** 每 30、45 或 60 分鐘提醒你伸懶腰、喝水或讓眼睛休息。你在專注或不在電腦前時不會打擾。
- **低電量提醒。** 電量低於 20% 時，貓咪會變得懶洋洋並提醒你充電。接上電源時牠會跟你道謝。

#### 設計

- **毛玻璃選單。** 右鍵選單使用 macOS 原生的毛玻璃材質，搭配透明漸層與像素圖示，子選單會立刻展開。
- **像素風對話框。** 對話泡泡和待辦清單都是復古遊戲風格，像素字型同時支援英文和繁體中文。
- **中英文切換。** 隨時可以在選單裡切換語言。第一次開啟時會依照系統語言自動選擇。

![繁體中文選單](docs/screenshots/menu-zh.png)

### 安裝

需要 macOS 與 Python 3.9 以上的版本。如果還沒有 Python，請先在終端機執行 `xcode-select --install`。

```bash
git clone https://github.com/Tanuki3701/meowmentum.git
cd meowmentum
bash build_mac.sh
```

完成後 App 會安裝到「應用程式」資料夾。之後用 Spotlight 或 Launchpad 搜尋 **Meowmentum** 就能開啟。

如果想讓貓咪在開機時自動出現，請到「系統設定」的「一般」裡的「登入項目」，把 Meowmentum 加進去。

### 使用方式

- 在貓咪身上**按右鍵**（觸控板雙指點按）可以打開選單。
- **點一下**貓咪可以打開待辦清單。點一下睡著的貓咪可以把牠叫醒。
- 用滑鼠左鍵**拖曳**可以移動貓咪。
- 要結束程式時，在貓咪身上按右鍵並選擇**結束**。

### 致謝

- 像素字型使用 TakWolf 的 [Fusion Pixel Font](https://fusion-pixel-font.takwolf.com)，授權為 SIL Open Font License 1.1，授權全文在 `assets/fonts/LICENSE-fusion-pixel.txt`。
- 睡覺的精靈圖是用原始精靈圖的調色盤一格一格畫出來的，所以和原本的畫風一致。
