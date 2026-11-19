#!/usr/bin/env bash
# pm-trending 定时任务入口（launchd 调用）：采集一轮 Polymarket 热门事件。
set -euo pipefail
cd "$(dirname "$0")/.."
echo "[$(date '+%F %T')] start"
python3 scripts/polymarket_hot.py "$@"
echo "[$(date '+%F %T')] done"
