#!/bin/bash
# 不打包、直接執行原始碼（在 Finder 裡雙擊即可）
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "第一次執行，安裝套件中..."
  python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
fi
nohup .venv/bin/python src/main.py >/dev/null 2>&1 &
echo "貓咪出門了！這個終端機視窗可以關掉。"
