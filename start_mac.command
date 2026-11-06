#!/bin/bash
# 雙擊啟動(macOS)。使用 iPad 期間請不要關閉這個視窗。
cd "$(dirname "$0")"
python3 -m faultdetect serve --host 0.0.0.0 --port 8000 --data samples
