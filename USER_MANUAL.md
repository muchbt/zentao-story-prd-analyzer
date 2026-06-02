# Zentao Story PRD Analyzer — 用户手册

结合禅道命令行工具 `zentao` 和 AI Agent 能力，从禅道条目获取、代码仓库分析到 PRD/ISSUE 文档生成的一站式工具。

## 前置条件

- **Python 3.8+**
- **禅道 CLI (`zentao`)** 已安装并可在 PATH 中直接调用，且已完成登录（`zentao login`）
- **Agent CLI**：使用 `--agent claude` 需本机可执行 `claude`，`--agent codex` 需本机可执行 `codex`，`--agent opencode` 需本机可执行 `opencode`
- `--repo-path` 指向当前运行环境可访问的代码仓库

验证准备状态：

```bash
# 确认 zentao CLI 可用并检查当前登录 session
command -v zentao
zentao profile

# 确认 python 入口可用
python3 main.py --help
```

## 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `ZENTAO_SERVER` | 禅道服务地址 | `https://zentao.example.com` |
| `ZENTAO_TOKEN` | 禅道 Token | `***` |
| `ZENTAO_USER` | 禅道用户名 | `admin` |
| `ZENTAO_PASSWORD` | 禅道密码 | `***` |
| `ZENTAO_CONFIG_FILE` | 禅道 CLI 配置文件路径 | `/path/to/config.json` |
| `ZENTAO_PROFILE` | 已保存的 profile 名称 | `admin@https://zentao.example.com` |
| `ZENTAO_TIMEOUT` | 请求超时毫秒数（默认 30000） | `30000` |
| `LLM_AGENT` | 默认 Agent 后端 | `claude` |
| `PROJECT_ID` | 默认项目 ID | `1` |

## 快速开始

### 1. 登录禅道

```bash
# 使用 Token 登录
zentao login -s http://m2motive.cn:8000/ -t <token>

# 或使用用户名密码
zentao login -s https://zentao.example.com -u admin -p ***
```

也可以通过环境变量方式：

```bash
export ZENTAO_SERVER="http://m2motive.cn:8000/"
export ZENTAO_TOKEN="<token>"
```

### 2. 运行分析

```bash
# 仅抓取禅道条目，stdout 输出 JSON
python3 main.py --module requirement --id 5939

# 完整分析：抓取禅道条目 + 分析本地代码 + 生成 PRD/ISSUE
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude

# 批量分析
python3 main.py --module story --project 3 --status open --limit 10 --analyze --repo-path . --agent claude
```

## 支持的模块

| 模块参数 | 说明 |
|----------|------|
| `story` | 软件需求 |
| `requirement` | 用户需求 |
| `bug` | 缺陷 |
| `task` | 任务 |
| `ticket` | 工单 |
| `feedback` | 反馈 |

## 常用运行模式

```bash
# 基础：单个需求分析
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude

# 提供代码线索：Search Hint（指导 Agent 搜索）+ Seed Path（预加载文件）
python3 main.py --module requirement --id 5939 --analyze --repo-path . \
  --clues calibration,LoadCalibration,src/calib \
  --paths src/calib/import_config.c \
  --agent claude

# 指定 Agent 超时（秒）
python3 main.py --module requirement --id 5939 --analyze --repo-path . \
  --agent claude --agent-timeout 900

# 安静模式（stdout 仅输出 JSON）
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude --quiet

# 详细日志
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude --verbose

# 日志写入文件
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude --log-file logs/run.jsonl

# 指定输出目录
python3 main.py --module requirement --id 5939 --analyze --repo-path . --agent claude --output-root docs

# 结果写入文件
python3 main.py --module requirement --id 5939 --output result.json
```

## 提供需求正文模式（不从禅道读取）

当用户直接提供完整需求正文（而非禅道条目）时：

```bash
python3 main.py --module requirement --id 5932 \
  --title "Ecall功能的优先级定义" \
  --requirement-file /tmp/requirement-5932.txt \
  --analyze --repo-path . --agent claude --quiet
```

规则：
- `--requirement-file` 仅支持 `requirement` 或 `story` 模块
- 需同时提供非空的 `--id` 和 `--title`
- 该模式下不调用禅道读取或登录，ID 仅作输出标识
- `--requirement-file` 与 `--login`、禅道认证参数不能同时使用

## Agent 选择

`--agent` 参数应与宿主 Agent CLI 环境一致：

| 宿主环境 | `--agent` 参数 |
|----------|---------------|
| Claude Code | `claude` |
| Codex | `codex` |
| OpenCode | `opencode` |

未指定时自动检测顺序：`claude` → `codex` → `opencode`。

## 多仓库分析

```bash
# 基本多仓分析
python3 main.py --module requirement --id 5939 --analyze \
  --repo soc=/path/to/soc \
  --repo mcu=/path/to/mcu \
  --agent claude

# 带通信协议线索
python3 main.py --module requirement --id 5939 --analyze \
  --repo soc=/path/to/soc \
  --repo mcu=/path/to/mcu \
  --protocol-hint soc,mcu:cmd_id=0x1234 \
  --agent claude
```

`--repo` 和旧版单仓参数 `--repo-path` 不能同时使用。

## 代码线索

| 类型 | 参数 | 说明 |
|------|------|------|
| Search Hint | `--clues` | 写入 prompt，指导 Agent 搜索（关键词、符号名、目录名） |
| Seed Path | `--paths` | 预加载到 Agent 上下文的仓库内文件路径 |

- 目录名、模块名或符号名放入 `--clues`；只有明确要预加载的文件才放入 `--paths`
- Seed Path 必须是 `--repo-path` 内的文件，不接受目录

### 批量分析用 Clues File

```json
{
  "5939": {
    "clues": ["callback", "CallBackMode", "src/ecall"],
    "paths": ["src/ecall/xcall.c"]
  }
}
```

```bash
python3 main.py --module requirement --project 3 --analyze --repo-path . --clues-file clues.json
```

## Debug Bundle

完整分析时 debug bundle 默认开启，路径为：

```
.zentao-story-prd-analyzer/{timestamp}-{module}-{id_or_project}/
```

包含脱敏配置、禅道条目摘要、扫描摘要、prompt、Agent response、分析结果、文档路径等。

```bash
# 自定义路径
python3 main.py --module requirement --id 5939 --analyze --debug-bundle-dir .zentao-story-prd-analyzer

# 关闭 debug bundle
python3 main.py --module requirement --id 5939 --analyze --no-debug-bundle

# 保存完整代码片段（注意业务敏感数据）
python3 main.py --module requirement --id 5939 --analyze --debug-include-code
```

## 输出解读

完整分析后 stdout 输出 JSON，关键字段：

| 字段 | 说明 |
|------|------|
| `items` | 获取的禅道条目或提供的需求条目 |
| `analysis` | 完成度或缺陷原因分析结果 |
| `documents` | 生成的 PRD/ISSUE Markdown 路径 |
| `summary_report` | 机器可读摘要路径 |
| `debug_bundle` | 诊断包路径 |
| `has_retryable_failure` | 是否存在可重试的失败条目 |

### PRD 文档章节

Feature Item 的 PRD 包含固定章节：

1. **概述**：需求摘要、范围、术语定义、来源信息
2. **需求解读**：业务规则、场景与流程、关系或并发矩阵、待确认事项
3. **代码依据**：代码位置总览、影响说明、实现完成度
4. **完成度评估**：需求点完成情况、差异与缺口
5. **实现建议**：代码变更建议、测试要点（明确为建议，不代表已有实现）
6. **参考信息**：追踪信息

### 完成度结论说明

| 结论 | 含义 |
|------|------|
| `完成` | 所有需求点已实现 |
| `部分完成` | 部分需求点已实现 |
| `未完成` | 需求点未实现 |
| `无法判断` | 证据不足或证据校验失败 |

可信度按有确认证据的需求点比例分级：全部完成为"高"，至少有一项为"中"，无确认为"低"。

## 错误处理

### 认证失败恢复

当 Token 失效时（exit code 2，stderr 含 `Token 已失效`/`认证失败` 等）：

1. 手动执行登录：
   ```bash
   zentao login -s <服务地址> -u <用户名> -p <密码>
   # 或
   zentao login -s <服务地址> -t <token>
   ```
2. 登录成功后重新执行原命令，无需再加 `--login` 参数

### Agent 响应解析失败

如果 Agent 返回内容无法解析为结构化 JSON，条目会被标记为可重试（`retryable: true`），stderr 会输出脱敏后的重试命令。用户确认后可重新执行：

- 批量分析时仅重试失败条目，不重做已成功条目
- 重试命令保留 `--output-root`，但不继承 `--output`

## 资料链接

- 禅道 CLI: https://www.zentao.net/book/zentaopms/2377.html
- Token 消耗模型: [`docs/TOKEN_COST.md`](docs/TOKEN_COST.md)
