#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ANALYZER_DIR="$SCRIPT_DIR/zentao-story-prd-analyzer"

echo "[1/4] 检查 analyzer CLI ..."
python3 "$ANALYZER_DIR/main.py" --help >/dev/null

echo "[2/4] 检查 Skill 文件 ..."
test -f "$ANALYZER_DIR/SKILL.md"
test -f "$ANALYZER_DIR/SKILL.yaml"
test -f "$ANALYZER_DIR/docs/skill-overview.md"

echo "[3/4] 检查 Gateway CLI (可选) ..."
GATEWAY_FOUND=false
GATEWAY_CMD=()
if [ -n "${ACP_AGENT_GATEWAY_BIN:-}" ]; then
  read -r -a GATEWAY_CMD <<< "$ACP_AGENT_GATEWAY_BIN"
  GATEWAY_FOUND=true
elif command -v npm >/dev/null 2>&1 && [ -x "$(npm config get prefix)/bin/acp-agent-gateway" ]; then
  GATEWAY_CMD=("$(npm config get prefix)/bin/acp-agent-gateway")
  GATEWAY_FOUND=true
elif command -v acp-agent-gateway >/dev/null 2>&1; then
  GATEWAY_CMD=(acp-agent-gateway)
  GATEWAY_FOUND=true
fi
if $GATEWAY_FOUND; then
  "${GATEWAY_CMD[@]}" doctor
else
  echo "[跳过] acp-agent-gateway 未安装。analyzer 将使用直接后端。"
fi

echo "[4/4] 检查手工 smoke 脚本语法 ..."
python3 - <<PY
import ast
from pathlib import Path
path = Path("$ANALYZER_DIR/scripts/smoke_gateway_real_adapter.py")
ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
print("syntax ok")
PY

echo "preflight ok"
