#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
用法:
  ./install-skill.sh [skill安装根目录]

说明:
  - 默认安装到 SKILL_INSTALL_ROOT。
  - 未设置 SKILL_INSTALL_ROOT 时，优先使用 ~/.agents/skills；否则使用 ${CODEX_HOME:-~/.codex}/skills。
USAGE
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/zentao-story-prd-analyzer"
SKILL_NAME="zentao-story-prd-analyzer"

if [ ! -f "$SOURCE_DIR/SKILL.md" ] || [ ! -f "$SOURCE_DIR/main.py" ]; then
  echo "[错误] 离线包缺少 Skill 或 analyzer 入口: $SOURCE_DIR" >&2
  exit 2
fi

if [ -n "${1:-}" ]; then
  SKILL_ROOT="$1"
elif [ -n "${SKILL_INSTALL_ROOT:-}" ]; then
  SKILL_ROOT="$SKILL_INSTALL_ROOT"
elif [ -d "$HOME/.agents/skills" ]; then
  SKILL_ROOT="$HOME/.agents/skills"
else
  SKILL_ROOT="${CODEX_HOME:-$HOME/.codex}/skills"
fi

TARGET_DIR="$SKILL_ROOT/$SKILL_NAME"
TMP_TARGET="$SKILL_ROOT/.${SKILL_NAME}.tmp.$$"

mkdir -p "$SKILL_ROOT"
rm -rf "$TMP_TARGET"
mkdir -p "$TMP_TARGET"
cp -a "$SOURCE_DIR/." "$TMP_TARGET/"
rm -rf "$TARGET_DIR"
mv "$TMP_TARGET" "$TARGET_DIR"

echo "Skill installed: $TARGET_DIR"
python3 "$TARGET_DIR/main.py" --help >/dev/null
echo "Analyzer CLI ok"
