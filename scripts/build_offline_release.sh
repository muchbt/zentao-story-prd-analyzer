#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
用法:
  scripts/build_offline_release.sh <版本号> [acp-agent-gateway仓库路径]

示例:
  scripts/build_offline_release.sh 0.2.0 ../acp-agent-gateway

说明:
  - 在构建机运行，需要本仓库和 acp-agent-gateway 仓库均已存在。
  - 会同步 analyzer Skill 包、构建 Gateway、执行 npm pack，并生成离线发布目录 release/<版本号>/。
  - Gateway tarball 内置自身运行时 npm 依赖；ACP adapters 仍需由目标环境单独提供。
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
GATEWAY_DIR_INPUT="${2:-$REPO_DIR/../acp-agent-gateway}"
GATEWAY_DIR="$(cd "$GATEWAY_DIR_INPUT" 2>/dev/null && pwd || true)"

if [ -z "$GATEWAY_DIR" ] || [ ! -f "$GATEWAY_DIR/package.json" ]; then
  echo "[错误] 找不到 acp-agent-gateway 仓库: $GATEWAY_DIR_INPUT" >&2
  exit 2
fi

DIST_DIR="$REPO_DIR/dist/$VERSION"
RELEASE_DIR="$REPO_DIR/release/$VERSION"
ANALYZER_RELEASE_DIR="$RELEASE_DIR/zentao-story-prd-analyzer"
GATEWAY_RELEASE_DIR="$RELEASE_DIR/gateway"

echo "[1/5] 同步 analyzer 包 ..."
"$REPO_DIR/sync_dist.sh" "$VERSION"

echo "[2/5] 准备 release 目录 ..."
rm -rf "$RELEASE_DIR"
mkdir -p "$ANALYZER_RELEASE_DIR" "$GATEWAY_RELEASE_DIR"
cp -a "$DIST_DIR/." "$ANALYZER_RELEASE_DIR/"

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

cat >"$RELEASE_DIR/install-gateway.sh" <<EOF_INSTALL
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
GATEWAY_TGZ="\$SCRIPT_DIR/gateway/$GATEWAY_TGZ"
NPM_INSTALL_FLAGS="\${NPM_INSTALL_FLAGS:---offline}"

if [ ! -f "\$GATEWAY_TGZ" ]; then
  echo "[错误] Gateway tarball 不存在: \$GATEWAY_TGZ" >&2
  exit 2
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[错误] 未找到 npm。acp-agent-gateway 需要 Node.js 24+ 和 npm。" >&2
  exit 2
fi

echo "安装 Gateway: \$GATEWAY_TGZ"
echo "npm install flags: \$NPM_INSTALL_FLAGS"
npm install -g "\$GATEWAY_TGZ" \$NPM_INSTALL_FLAGS

echo "验证 acp-agent-gateway doctor ..."
NPM_PREFIX="\$(npm config get prefix)"
GATEWAY_BIN="\$NPM_PREFIX/bin/acp-agent-gateway"
if [ -x "\$GATEWAY_BIN" ]; then
  "\$GATEWAY_BIN" doctor
else
  acp-agent-gateway doctor
fi
EOF_INSTALL

cat >"$RELEASE_DIR/install.sh" <<'EOF_INSTALL_ALL'
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

"$SCRIPT_DIR/install-skill.sh"
"$SCRIPT_DIR/install-gateway.sh"
if [ -z "${ACP_AGENT_GATEWAY_BIN:-}" ] && command -v npm >/dev/null 2>&1; then
  NPM_PREFIX="$(npm config get prefix)"
  export PATH="$NPM_PREFIX/bin:$PATH"
fi
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

echo "[3/4] 检查 Gateway CLI ..."
if [ -n "${ACP_AGENT_GATEWAY_BIN:-}" ]; then
  read -r -a GATEWAY_CMD <<< "$ACP_AGENT_GATEWAY_BIN"
elif command -v npm >/dev/null 2>&1 && [ -x "$(npm config get prefix)/bin/acp-agent-gateway" ]; then
  GATEWAY_CMD=("$(npm config get prefix)/bin/acp-agent-gateway")
else
  GATEWAY_CMD=(acp-agent-gateway)
fi
"${GATEWAY_CMD[@]}" doctor

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

cat >"$RELEASE_DIR/OFFLINE_RELEASE.md" <<EOF_DOC
# zentao-story-prd-analyzer offline release $VERSION

## Contents

- \`zentao-story-prd-analyzer/\`: self-contained Python analyzer skill package.
- \`gateway/$GATEWAY_TGZ\`: ACP Agent Gateway npm tarball.
- \`install.sh\`: installs the analyzer Skill, installs Gateway, then runs preflight.
- \`install-skill.sh\`: installs the analyzer Skill package.
- \`install-gateway.sh\`: installs the Gateway tarball with npm.
- \`preflight.sh\`: checks analyzer CLI, Gateway \`doctor\`, and smoke script syntax.

## Install All

\`\`\`bash
./install.sh
\`\`\`

The default Skill target is \`SKILL_INSTALL_ROOT\`. If it is unset,
\`install-skill.sh\` prefers \`~/.agents/skills\` when that directory exists and
otherwise uses \`\${CODEX_HOME:-~/.codex}/skills\`.

To install the Skill into a specific Agent skill root:

\`\`\`bash
SKILL_INSTALL_ROOT=/path/to/skills ./install-skill.sh
# or
./install-skill.sh /path/to/skills
\`\`\`

## Install Gateway

\`\`\`bash
./install-gateway.sh
\`\`\`

By default the script runs \`npm install -g <tarball> --offline\`. The Gateway
tarball vendors its own runtime npm dependencies, so this install does not depend
on the target machine's npm cache for \`@agentclientprotocol/sdk\` or \`zod\`.
To use a controlled internal registry instead of strict offline cache:

\`\`\`bash
NPM_INSTALL_FLAGS="--registry <internal-registry> --prefer-offline" ./install-gateway.sh
\`\`\`

ACP adapters are still explicit runtime dependencies. Install or provide the
selected adapter separately, then confirm:

\`\`\`bash
acp-agent-gateway doctor
\`\`\`

## Preflight

\`\`\`bash
./preflight.sh
\`\`\`

## Real adapter smoke

\`\`\`bash
python3 zentao-story-prd-analyzer/scripts/smoke_gateway_real_adapter.py \\
  --gateway-agent opencode \\
  --model opencode-go/qwen3.6-plus \\
  --keep
\`\`\`
EOF_DOC

chmod +x "$RELEASE_DIR/install.sh" "$RELEASE_DIR/install-skill.sh" "$RELEASE_DIR/install-gateway.sh" "$RELEASE_DIR/preflight.sh"

echo "[5/5] 完成。"
echo "Release directory: $RELEASE_DIR"
find "$RELEASE_DIR" -maxdepth 3 -type f | sort
