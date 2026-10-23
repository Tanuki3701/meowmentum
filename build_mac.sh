#!/bin/bash
# 把 Meowmentum 打包成 Meowmentum.app，並放進「應用程式」資料夾。
# 用法：在終端機執行  bash build_mac.sh
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "找不到 python3。請先執行 xcode-select --install，或從 python.org 安裝 Python。"
  exit 1
fi

echo "[1/3] 建立虛擬環境並安裝套件（第一次會比較久）..."
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt pyinstaller pillow

echo "[2/3] 打包中..."
.venv/bin/pyinstaller --noconfirm --clean --log-level ERROR Meowmentum.spec

echo "[3/3] 安裝中..."
DEST="/Applications"
[ -w "$DEST" ] || { DEST="$HOME/Applications"; mkdir -p "$DEST"; }
pkill -x Meowmentum 2>/dev/null || true
pkill -x DesktopCat 2>/dev/null || true      # 舊版名稱
sleep 1
rm -rf "$DEST/Meowmentum.app" "$DEST/DesktopCat.app"
cp -R dist/Meowmentum.app "$DEST/"
rm -rf build dist

echo "完成！已安裝到 $DEST/Meowmentum.app。"
echo "之後在 Launchpad 或 Spotlight 搜尋 Meowmentum 就能開啟。"
open "$DEST/Meowmentum.app"
