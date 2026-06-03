#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
用法:
  scripts/build_offline_release.sh <版本号> [acp-agent-gateway仓库路径]

示例:
  scripts/build_offline_release.sh 0.2.0 ../acp-agent-gateway

说明:
  - 在构建机运行，需要本仓库已存在；acp-agent-gateway 仓库为可选。
  - 会同步 analyzer Skill 包；若提供 acp-agent-gateway 路径则构建并打包 Gateway。
  - 生成离线发布目录 release/<版本号>/。
  - Gateway tarball 内置自身运行时 npm 依赖；ACP adapters 仍需由目标环境单独提供。
  - Gateway 为可选组件：在不提供 Gateway 路径时，离线包不含 Gateway，安装脚本将跳过 Gateway 相关步骤。
USAGE
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  usage
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GATEWAY_DIR_INPUT="${2:-}"
GATEWAY_DIR=""
GATEWAY_TGZ=""

if [ -n "$GATEWAY_DIR_INPUT" ]; then
  GATEWAY_DIR="$(cd "$GATEWAY_DIR_INPUT" 2>/dev/null && pwd || true)"
  if [ -z "$GATEWAY_DIR" ] || [ ! -f "$GATEWAY_DIR/package.json" ]; then
    echo "[警告] 找不到 acp-agent-gateway 仓库: $GATEWAY_DIR_INPUT，将跳过 Gateway 构建。" >&2
    GATEWAY_DIR=""
  fi
else
  echo "[提示] 未提供 acp-agent-gateway 路径，将跳过 Gateway 构建。离线包仅包含 analyzer Skill。" >&2
fi

DIST_DIR="$REPO_DIR/dist/$VERSION"
RELEASE_DIR="$REPO_DIR/release/$VERSION"
ANALYZER_RELEASE_DIR="$RELEASE_DIR/zentao-story-prd-analyzer"
GATEWAY_RELEASE_DIR="$RELEASE_DIR/gateway"

echo "[1/5] 同步 analyzer 包 ..."
"$REPO_DIR/sync_dist.sh" "$VERSION"

echo "[2/5] 准备 release 目录 ..."
rm -rf "$RELEASE_DIR"
if [ -n "$GATEWAY_DIR" ]; then
  mkdir -p "$ANALYZER_RELEASE_DIR" "$GATEWAY_RELEASE_DIR"
else
  mkdir -p "$ANALYZER_RELEASE_DIR"
fi
cp -a "$DIST_DIR/." "$ANALYZER_RELEASE_DIR/"

if [ -n "$GATEWAY_DIR" ]; then
  echo "[3/5] 构建并打包 acp-agent-gateway ..."
  PACK_NAME_FILE="$(mktemp)"
  (
    cd "$GATEWAY_DIR"
    npm run build
    npm pack --pack-destination "$GATEWAY_RELEASE_DIR" >"$PACK_NAME_FILE"
  )
  GATEWAY_TGZ="$(tail -n 1 "$PACK_NAME_FILE" | tr -d '\r')"
  rm -f "$PACK_NAME_FILE"

  if [ -z "$GATEWAY_TGZ" ] || [ ! -f "$GATEWAY_RELEASE_DIR/$GATEWAY_TGZ" ]; then
    echo "[错误] Gateway npm pack 未生成 tarball" >&2
    exit 1
  fi
else
  echo "[3/5] 跳过 Gateway 构建 (未提供 Gateway 仓库路径)"
fi

echo "[4/5] 生成离线安装与预检脚本 ..."
cat >"$RELEASE_DIR/install-skill.sh" <<'EOF_INSTALL_SKILL'
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
EOF_INSTALL_SKILL

cat >"$RELEASE_DIR/install-gateway.sh" <<'EOF_INSTALL_GW'
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
EOF_INSTALL_GW

cat >"$RELEASE_DIR/install.sh" <<'EOF_INSTALL_ALL'
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
EOF_INSTALL_ALL

cat >"$RELEASE_DIR/preflight.sh" <<'EOF_PREFLIGHT'
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
EOF_PREFLIGHT

# Generate OFFLINE_RELEASE.md
{
  echo "# zentao-story-prd-analyzer offline release $VERSION"
  echo ""
  echo "## Contents"
  echo ""
  echo "- \`zentao-story-prd-analyzer/\`: self-contained Python analyzer skill package."
  if [ -n "$GATEWAY_TGZ" ]; then
    echo "- \`gateway/$GATEWAY_TGZ\`: ACP Agent Gateway npm tarball (可选组件)."
  else
    echo "- 当前离线包**未包含** ACP Agent Gateway (构建时未提供 Gateway 仓库路径)。"
  fi
  echo "- \`install.sh\`: installs the analyzer Skill, optionally prompts for Gateway, then runs preflight."
  echo "- \`install-skill.sh\`: installs the analyzer Skill package."
  echo "- \`install-gateway.sh\`: optional Gateway installation script."
  echo "- \`preflight.sh\`: checks analyzer CLI, Skill files, Gateway (if installed), and smoke script syntax."
  echo ""

  echo "## 推荐使用方式"
  echo ""
  echo "analyzer 默认推荐使用直接后端 (\`--agent opencode\`) 而非 ACP Gateway，"
  echo "以避免 \`opencode acp\` 空白响应问题。如果直接后端在目标环境中正常工作，"
  echo "则无需安装 Gateway。"
  echo ""

  echo "## Install All"
  echo ""
  echo '```bash'
  echo "./install.sh"
  echo '```'
  echo ""
  echo "The default Skill target is \`SKILL_INSTALL_ROOT\`. If it is unset,"
  echo "\`install-skill.sh\` prefers \`~/.agents/skills\` when that directory exists and"
  echo "otherwise uses \`\${CODEX_HOME:-~/.codex}/skills\`."
  echo ""
  echo "To install the Skill into a specific Agent skill root:"
  echo ""
  echo '```bash'
  echo "SKILL_INSTALL_ROOT=/path/to/skills ./install-skill.sh"
  echo "# or"
  echo "./install-skill.sh /path/to/skills"
  echo '```'
  echo ""

  if [ -n "$GATEWAY_TGZ" ]; then
    echo "## Install Gateway (可选)"
    echo ""
    echo "Gateway 为可选组件。\`install.sh\` 会询问是否安装。也可单独安装："
    echo ""
    echo '```bash'
    echo "./install-gateway.sh"
    echo '```'
    echo ""
    echo "By default the script runs \`npm install -g <tarball> --offline\`. The Gateway"
    echo "tarball vendors its own runtime npm dependencies, so this install does not depend"
    echo "on the target machine's npm cache for \`@agentclientprotocol/sdk\` or \`zod\`."
    echo "To use a controlled internal registry instead of strict offline cache:"
    echo ""
    echo '```bash'
    echo 'NPM_INSTALL_FLAGS="--registry <internal-registry> --prefer-offline" ./install-gateway.sh'
    echo '```'
    echo ""
    echo "ACP adapters are still explicit runtime dependencies. Install or provide the"
    echo "selected adapter separately, then confirm:"
    echo ""
    echo '```bash'
    echo "acp-agent-gateway doctor"
    echo '```'
    echo ""
  fi

  echo "## Preflight"
  echo ""
  echo '```bash'
  echo "./preflight.sh"
  echo '```'
  echo ""

  echo "## Real adapter smoke"
  echo ""
  echo '```bash'
  echo 'python3 zentao-story-prd-analyzer/scripts/smoke_gateway_real_adapter.py \\'
  echo "  --gateway-agent opencode \\"
  echo "  --model opencode-go/qwen3.6-plus \\"
  echo "  --keep"
  echo '```'
} >"$RELEASE_DIR/OFFLINE_RELEASE.md"

chmod +x "$RELEASE_DIR/install.sh" "$RELEASE_DIR/install-skill.sh" "$RELEASE_DIR/install-gateway.sh" "$RELEASE_DIR/preflight.sh"

echo "[5/5] 完成。"
echo "Release directory: $RELEASE_DIR"
find "$RELEASE_DIR" -maxdepth 3 -type f | sort
