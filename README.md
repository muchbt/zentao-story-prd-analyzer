## zentao-story-prd-analyzer

结合禅道命令行工具 `zentao` 和代码代理能力，完成从禅道条目获取、代码仓库分析、LLM 判断到 PRD/ISSUE 文档生成的闭环。

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
