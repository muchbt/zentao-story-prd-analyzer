## zentao-story-prd-analyzer

结合禅道命令行工具 `zentao` 和代码代理能力，完成从禅道条目获取、代码仓库分析、LLM 判断到 PRD/ISSUE 文档生成的闭环。

代码实现位于 `zentao_analyzer` 包内；根目录 `main.py` 是兼容入口，既有 `python3 main.py ...` 命令保持可用。

### 当前运行方式

本项目当前主要作为命令行工具运行。推荐入口是仓库根目录的 `main.py`：

```bash
python3 main.py --module requirement --id 5939
```

`main.py` 只负责兼容旧命令，真实实现位于 `zentao_analyzer.main`。也可以用 Python package 方式运行：

```bash
python3 -m zentao_analyzer.main --help
```

常见运行模式：

```bash
# 阶段一：只抓取禅道条目，stdout 输出 JSON
python3 main.py --module requirement --id 5939

# 阶段二到五：抓取禅道条目后分析本地代码，生成 PRD/ISSUE、summary 和 debug bundle
python3 main.py --module requirement --id 5939 --analyze --repo-path .

# 指定 Agent
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude

# 显式提供代码线索
python3 main.py --module requirement --id 5939 --analyze --repo-path . \
  --keywords calibration,import \
  --paths src/calib \
  --symbols LoadCalibration
```

运行前需要满足以下前置条件：

- `zentao` CLI 已安装，并可在 `PATH` 中直接调用。
- 已通过 `zentao login` 完成登录，或已配置 `ZENTAO_SERVER` 与 `ZENTAO_TOKEN` / `ZENTAO_USER` / `ZENTAO_PASSWORD`。
- 使用 OpenAI/Codex 后端时已配置 `OPENAI_API_KEY` 和 `OPENAI_MODEL`。
- 使用 Claude 后端时本机可执行 `claude` CLI。
- `--repo-path` 指向当前运行环境可访问的代码仓库。

### `SKILL.yaml` 的作用

`SKILL.yaml` 是本项目的能力声明文件，用于描述这个工具作为“技能”被外部 Agent 或自动化平台调用时需要的输入、输出和默认入口。它不是 Python 代码的直接运行入口，也不是 Codex/Claude Code 常规 Skill 的触发说明；常规 Agent CLI Skill 入口见根目录 `SKILL.md`。

当前 `SKILL.yaml` 主要说明：

- 技能名称：`zentao-story-prd-analyzer`
- 技能能力：从禅道获取需求/缺陷，结合本地代码分析完成度或问题原因，并生成 PRD/ISSUE 文档
- 输入参数：`project_id`、`item_type`、`repo_path`、`agent`、`model`、`keywords`、`paths`、`symbols`、`clues_file` 等
- 输出结果：`prd_docs`
- 默认运行入口：

```yaml
run:
  python: main.py
```

因此：

- 人工或脚本调用时，直接使用 `python3 main.py ...`。
- 支持读取 `SKILL.yaml` 的 Agent/平台可以根据其中的输入定义和 `run.python` 自动组装命令。
- 通过 Codex/Claude Code 等 Agent CLI 的常规 Skill 方式安装时，使用根目录 `SKILL.md` 作为触发说明；`SKILL.md` 会指导 Agent 在目标代码仓库中调用本项目的 `main.py`。

### `SKILL.md` 的作用

`SKILL.md` 是面向 Codex、Claude Code 等 Agent CLI 的通用 Skill 说明文件。它采用薄封装策略：只说明何时使用本工具、如何收集参数、如何在目标代码仓库中调用 CLI、沙箱内需要满足哪些前置条件，以及如何解释输出。

`SKILL.md` 的边界：

- 默认从当前工作目录作为目标代码仓库运行分析。
- 默认执行完整分析链路，即带 `--analyze`。
- 不替代官方禅道 Skill；只查询禅道数据时应优先使用官方禅道 Skill 或 `zentao` CLI。
- 不在 Skill 层重复实现分析逻辑，不伪造 Zentao 内容、代码证据或 PRD/ISSUE 结论。
- 沙箱内必须能访问 `zentao` CLI、禅道配置/登录态、目标代码仓库，以及所选 Agent 后端。

### 资料链接

- 禅道 CLI: https://www.zentao.net/book/zentaopms/2377.html
- 禅道 SKILL: https://www.zentao.net/book/zentaopms/2315.html

---

## 阶段一：禅道 CLI 数据闭环

### 环境要求

- 已安装禅道 CLI 工具 `zentao`，并可在 PATH 中直接调用。
- Python 3.8+

### 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `ZENTAO_CONFIG_FILE` | 禅道 CLI 配置文件路径 | `/path/to/config.json` |
| `ZENTAO_PROFILE` | 已保存的 profile 名称 | `admin@https://zentao.example.com` |
| `ZENTAO_TIMEOUT` | 请求超时毫秒数（默认 30000） | `30000` |
| `ZENTAO_SERVER` | 禅道服务地址 | `https://zentao.example.com` |
| `ZENTAO_USER` | 禅道用户名 | `admin` |
| `ZENTAO_PASSWORD` | 禅道密码 | `***` |
| `ZENTAO_TOKEN` | 禅道 Token | `***` |
| `PROJECT_ID` | 默认项目 ID | `1` |

### 命令行用法

沙箱或新环境内首次运行前，需要先让 `zentao` 完成登录。推荐使用 token 登录：

```bash
zentao login -s http://101.91.119.66:8000/ -t <token>
python3 main.py --module requirement --id 5939
```

也可以在 shell 环境中设置禅道服务和 token，之后直接运行分析命令：

```bash
export ZENTAO_SERVER="http://101.91.119.66:8000/"
export ZENTAO_TOKEN="<token>"
python3 main.py --module requirement --id 5939
```

```bash
# 获取单个 story 详情
python3 main.py --module story --id 123

# 获取某个项目下的 bug 列表
python3 main.py --module bug --project 5 --status active --limit 10

# 登录禅道（使用环境变量）
python3 main.py --login --use-env

# 登录禅道（使用命令行参数）
python3 main.py --login --server https://zentao.example.com --user admin --password ***

# 将阶段一结果写入文件
python3 main.py --module story --project 3 --output story_data.json

# 获取数据后继续执行代码分析与 PRD 生成（阶段二）
python3 main.py --module story --project 3 --analyze --repo-path ./my-repo
```

### 支持的模块映射

| 模块参数 | 说明 |
|----------|------|
| `story` | 软件需求 |
| `requirement` | 用户需求 |
| `bug` | 缺陷 |
| `task` | 任务 |
| `ticket` | 工单 |
| `feedback` | 反馈 |

### 错误处理

- 当未找到 `zentao` 命令时，会提示安装禅道 CLI。
- 当未登录或认证失败时，会明确提示 `禅道认证失败`，不会泄露密码或 Token。
- 当对象不存在时，会提示 `禅道对象不存在`。
- 当网络超时时，会提示超时信息。
- 所有日志和异常信息均已对敏感字段做脱敏处理。

---

## 阶段四：Agent、日志与 Debug Bundle

### Agent 选择

```bash
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent openai --model "$OPENAI_MODEL"
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent codex --model "$OPENAI_MODEL"
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent opencode
```

`openai` 和 `codex` 使用 OpenAI SDK 后端。需要设置：

```bash
export OPENAI_API_KEY="你的 OpenAI API Key"
export OPENAI_MODEL="模型名"
export OPENAI_BASE_URL="可选的兼容 OpenAI 接口地址"
```

`claude` 使用本机 Claude CLI。默认命令是 `claude`，默认通过 stdin 传入 prompt：

```bash
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude --claude-command claude --claude-prompt-via arg
```

`opencode` 是预留接口，当前返回 `not_implemented`，不会伪造成功。

### 日志

运行日志默认写入 stderr，stdout 保持最终 JSON：

```bash
python3 main.py --module requirement --id 5939 --analyze --quiet
python3 main.py --module requirement --id 5939 --analyze --verbose
python3 main.py --module requirement --id 5939 --analyze --log-file logs/run.jsonl
```

日志会脱敏 token、password、API key、Authorization 和 Bearer token。

### Debug Bundle

`--analyze` 时 debug bundle 默认开启，默认写入：

```text
debug_runs/{timestamp}-{module}-{id_or_project}/
```

其中包含脱敏配置、禅道条目摘要、扫描摘要、prompt、Agent response、分析结果、文档路径、summary 路径和本次 JSONL 日志引用。默认不保存完整代码片段。

```bash
python3 main.py --module requirement --id 5939 --analyze --debug-bundle-dir debug_runs
python3 main.py --module requirement --id 5939 --analyze --no-debug-bundle
python3 main.py --module requirement --id 5939 --analyze --debug-include-code
```

Debug bundle 会默认脱敏，但仍可能包含业务上下文、prompt 和模型响应，应按项目敏感资料管理。

---

## 阶段五：证据可追溯性

### 代码线索

除了从禅道标题和描述中自动抽取关键词，用户也可以显式提供代码线索：

```bash
python3 main.py --module requirement --id 5939 --analyze --repo-path . \
  --keywords calibration,import \
  --paths src/calib,src/config \
  --symbols LoadCalibration,ImportConfig
```

批量分析时可使用 `--clues-file` 为不同条目指定不同线索：

```json
{
  "5939": {
    "keywords": ["calibration", "import"],
    "paths": ["src/calib"],
    "symbols": ["LoadCalibration"]
  }
}
```

```bash
python3 main.py --module requirement --project 3 --analyze --repo-path . --clues-file clues.json
```

路径线索必须位于 `--repo-path` 内。越界路径不会被读取，会记录到 debug bundle 的 `rejected_clues.json`。

### 证据位置

debug bundle 默认保存证据位置文件：

```text
code_evidence_locations.json
rejected_clues.json
```

`code_evidence_locations.json` 区分：

- `collected_locations`：实际喂给 Agent 的文件名和行号范围。
- `cited_evidence_locations`：Agent 最终引用为结论依据的文件名和行号范围。

PRD/ISSUE 文档只展示关键引用证据。完整代码内容仍只有在传入 `--debug-include-code` 时才保存。
