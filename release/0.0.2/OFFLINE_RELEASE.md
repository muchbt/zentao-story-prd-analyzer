# zentao-story-prd-analyzer offline release 0.0.2

## Contents

- `zentao-story-prd-analyzer/`: self-contained Python analyzer skill package.
- `gateway/local-acp-agent-gateway-0.1.0.tgz`: ACP Agent Gateway npm tarball (可选组件).
- `install.sh`: installs the analyzer Skill, optionally prompts for Gateway, then runs preflight.
- `install-skill.sh`: installs the analyzer Skill package.
- `install-gateway.sh`: optional Gateway installation script.
- `preflight.sh`: checks analyzer CLI, Skill files, Gateway (if installed), and smoke script syntax.

## 推荐使用方式

analyzer 默认推荐使用直接后端 (`--agent opencode`) 而非 ACP Gateway，
以避免 `opencode acp` 空白响应问题。如果直接后端在目标环境中正常工作，
则无需安装 Gateway。

## Install All

```bash
./install.sh
```

The default Skill target is `SKILL_INSTALL_ROOT`. If it is unset,
`install-skill.sh` prefers `~/.agents/skills` when that directory exists and
otherwise uses `${CODEX_HOME:-~/.codex}/skills`.

To install the Skill into a specific Agent skill root:

```bash
SKILL_INSTALL_ROOT=/path/to/skills ./install-skill.sh
# or
./install-skill.sh /path/to/skills
```

## Install Gateway (可选)

Gateway 为可选组件。`install.sh` 会询问是否安装。也可单独安装：

```bash
./install-gateway.sh
```

By default the script runs `npm install -g <tarball> --offline`. The Gateway
tarball vendors its own runtime npm dependencies, so this install does not depend
on the target machine's npm cache for `@agentclientprotocol/sdk` or `zod`.
To use a controlled internal registry instead of strict offline cache:

```bash
NPM_INSTALL_FLAGS="--registry <internal-registry> --prefer-offline" ./install-gateway.sh
```

ACP adapters are still explicit runtime dependencies. Install or provide the
selected adapter separately, then confirm:

```bash
acp-agent-gateway doctor
```

## Preflight

```bash
./preflight.sh
```

## Real adapter smoke

```bash
python3 zentao-story-prd-analyzer/scripts/smoke_gateway_real_adapter.py \
  --gateway-agent opencode \
  --model opencode-go/qwen3.6-plus \
  --keep
```
