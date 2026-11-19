#!/bin/bash
# 在 macOS 上用 launchd 每小时运行一次 polymarket_hot.py。
#   安装：bash scripts/install_schedule.sh
#   卸载：bash scripts/install_schedule.sh --uninstall
# 电脑睡眠期间错过的运行不会补跑，唤醒后按间隔继续。
set -euo pipefail

LABEL="com.pmresearch.polymarket-hot"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"

if [[ "${1:-}" == "--uninstall" ]]; then
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "已卸载 $LABEL"
  exit 0
fi

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$(command -v python3)"
INTERVAL="${INTERVAL:-3600}"
mkdir -p "$REPO/logs" "$(dirname "$PLIST")"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$REPO/polymarket_hot.py</string>
  </array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>StartInterval</key><integer>$INTERVAL</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$REPO/logs/polymarket_hot.log</string>
  <key>StandardErrorPath</key><string>$REPO/logs/polymarket_hot.err.log</string>
  <key>EnvironmentVariables</key>
  <dict><key>PYTHONIOENCODING</key><string>utf-8</string></dict>
</dict>
</plist>
EOF

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
echo "已安装 $LABEL：每 ${INTERVAL}s 运行一次，日志在 $REPO/logs/"
