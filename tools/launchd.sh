#!/usr/bin/env bash
# 按模块的 deploy/launchd/agent.plist.tmpl 渲染并管理 launchd 任务。
#   用法：tools/launchd.sh <模块目录> install|uninstall|status
#   间隔：INTERVAL=秒（默认 3600）
# Label 统一为 com.prediction-market-research.<模块名>。
set -euo pipefail

MODULE="${1:?用法：tools/launchd.sh <模块> install|uninstall|status}"
ACTION="${2:-status}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
MODULE_DIR="$REPO/${MODULE}"
TMPL="$MODULE_DIR/deploy/launchd/agent.plist.tmpl"
LABEL="com.prediction-market-research.${MODULE}"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
DOMAIN="gui/$(id -u)"
INTERVAL="${INTERVAL:-3600}"

[[ -f "${TMPL}" ]] || { echo "找不到模板：${TMPL}"; exit 2; }

case "${ACTION}" in
  install)
    PY_DIR="$(dirname "$(command -v python3)")"
    mkdir -p "$MODULE_DIR/logs" "$(dirname "$PLIST")"
    sed -e "s|__LABEL__|${LABEL}|g" -e "s|__MODULE_DIR__|$MODULE_DIR|g" \
        -e "s|__LOG_DIR__|$MODULE_DIR/logs|g" -e "s|__INTERVAL__|$INTERVAL|g" \
        -e "s|__PATH__|$PY_DIR:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin|g" \
        "${TMPL}" > "$PLIST"
    plutil -lint "$PLIST" >/dev/null
    launchctl bootout "$DOMAIN/${LABEL}" 2>/dev/null || true
    launchctl bootstrap "$DOMAIN" "$PLIST"
    echo "已安装 ${LABEL}：每 ${INTERVAL}s 运行一次，日志在 ${MODULE}/logs/"
    ;;
  uninstall)
    launchctl bootout "$DOMAIN/${LABEL}" 2>/dev/null || true
    rm -f "$PLIST"
    echo "已卸载 ${LABEL}"
    ;;
  status)
    launchctl print "$DOMAIN/${LABEL}" 2>/dev/null | grep -E "^\s*(state|runs|last exit code|run interval)" \
      || echo "${LABEL} 未安装"
    ;;
  *) echo "未知 action：${ACTION}（install|uninstall|status）"; exit 2 ;;
esac
