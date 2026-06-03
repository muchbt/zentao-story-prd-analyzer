#!/usr/bin/env bash
set -euo pipefail

echo "=============================================="
echo " ACP Agent Gateway 安装脚本 (可选组件)"
echo " 如果 opencode acp 工作正常可跳过此安装"
echo "=============================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Find the gateway tarball (filename may vary by build)
GATEWAY_TGZ=""
for f in "$SCRIPT_DIR/gateway"/*.tgz; do
  if [ -f "$f" ]; then
    GATEWAY_TGZ="$f"
    break
  fi
done

if [ -z "$GATEWAY_TGZ" ]; then
  echo "[跳过] 当前离线包未包含 Gateway tarball，无法安装。" >&2
  echo "如需使用 Gateway，请在构建离线包时提供 acp-agent-gateway 仓库路径。" >&2
  exit 0
fi

NPM_INSTALL_FLAGS="${NPM_INSTALL_FLAGS:---offline}"

if ! command -v npm >/dev/null 2>&1; then
  echo "[错误] 未找到 npm。acp-agent-gateway 需要 Node.js 24+ 和 npm。" >&2
  exit 2
fi

echo "安装 Gateway: $GATEWAY_TGZ"
echo "npm install flags: $NPM_INSTALL_FLAGS"
npm install -g "$GATEWAY_TGZ" $NPM_INSTALL_FLAGS

echo "验证 acp-agent-gateway doctor ..."
NPM_PREFIX="$(npm config get prefix)"
GATEWAY_BIN="$NPM_PREFIX/bin/acp-agent-gateway"
if [ -x "$GATEWAY_BIN" ]; then
  "$GATEWAY_BIN" doctor
else
  acp-agent-gateway doctor
fi
