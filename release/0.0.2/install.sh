#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=============================================="
echo " zentao-story-prd-analyzer 离线安装"
echo "=============================================="
echo ""

"$SCRIPT_DIR/install-skill.sh"

# Check if gateway tarball exists
HAS_GATEWAY=false
shopt -s nullglob
for f in "$SCRIPT_DIR/gateway"/*.tgz; do
  HAS_GATEWAY=true
  break
done
shopt -u nullglob

if $HAS_GATEWAY; then
  echo ""
  read -r -p "是否安装可选的 ACP Agent Gateway？(当前 opencode acp 存在空白响应问题，如不确定请选 N) [y/N]: " INSTALL_GW
  if [ "${INSTALL_GW,,}" = "y" ] || [ "${INSTALL_GW,,}" = "yes" ]; then
    "$SCRIPT_DIR/install-gateway.sh"
  else
    echo "[跳过] 未安装 Gateway。analyzer 将使用直接后端 (--agent opencode/claude/codex)。"
  fi
else
  echo ""
  echo "[提示] 当前离线包未包含 ACP Agent Gateway。analyzer 将使用直接后端。"
fi

if [ -n "${HAS_GATEWAY:-}" ] && $HAS_GATEWAY && command -v npm >/dev/null 2>&1; then
  if [ -z "${ACP_AGENT_GATEWAY_BIN:-}" ]; then
    NPM_PREFIX="$(npm config get prefix)"
    export PATH="$NPM_PREFIX/bin:$PATH"
  fi
fi

echo ""
"$SCRIPT_DIR/preflight.sh"
