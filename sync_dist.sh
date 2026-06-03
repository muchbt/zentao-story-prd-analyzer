#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:?用法: $0 <版本号>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$SCRIPT_DIR"
DIST_DIR="$SCRIPT_DIR/dist/$VERSION"
PKG_DIR="$DIST_DIR/zentao_analyzer"
DIST_SCRIPTS_DIR="$DIST_DIR/scripts"

echo "同步版本 $VERSION 到 $DIST_DIR ..."

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR" "$PKG_DIR" "$DIST_SCRIPTS_DIR"

cp "$SRC_DIR/main.py" "$DIST_DIR/main.py"
cp "$SRC_DIR/SKILL.md" "$DIST_DIR/SKILL.md"
cp "$SRC_DIR/SKILL.yaml" "$DIST_DIR/SKILL.yaml"
cp "$SRC_DIR/README.md" "$DIST_DIR/README.md"
cp "$SRC_DIR/USER_MANUAL.md" "$DIST_DIR/USER_MANUAL.md"

for f in "$SRC_DIR/zentao_analyzer"/*.py; do
  [ -f "$f" ] && cp "$f" "$PKG_DIR/"
done

if [ -f "$SRC_DIR/scripts/smoke_gateway_real_adapter.py" ]; then
  cp "$SRC_DIR/scripts/smoke_gateway_real_adapter.py" "$DIST_SCRIPTS_DIR/"
  chmod +x "$DIST_SCRIPTS_DIR/smoke_gateway_real_adapter.py"
fi

find "$DIST_DIR" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

echo "同步完成: $DIST_DIR"
echo "文件列表:"
ls -1 "$DIST_DIR"
echo "---"
ls -1 "$PKG_DIR"
echo "---"
ls -1 "$DIST_SCRIPTS_DIR" 2>/dev/null || true
