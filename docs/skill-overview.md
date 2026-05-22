# zentao-story-prd-analyzer Skill 说明

`zentao-story-prd-analyzer` 用于从禅道获取需求或缺陷条目，并让具备仓库搜索能力的 Agent CLI 分析目标代码仓库，生成 PRD/ISSUE 文档、summary report 和 debug bundle。

## 支持的 Agent CLI

| Agent | 调用方式 |
| --- | --- |
| `claude` | 本机 `claude` CLI |
| `codex` | 本机 `codex exec` |
| `opencode` | 本机 `opencode run` |

直接运行 `main.py` 且未显式指定 `--agent` 时，默认检测顺序为 `claude`、`codex`、`opencode`。通过 `SKILL.md` 触发时应显式传入与宿主 CLI 一致的 `--agent`。

## 输入线索

| 类型 | 参数 | 说明 |
| --- | --- | --- |
| Search Hint | `--clues` / clues file 的 `clues` | 写入 prompt，指导 Agent 搜索 |
| Seed Path | `--paths` / clues file 的 `paths` | 预加载到 prompt 的仓库内文件 |

Seed Path 只接受 `repo_path` 内的文件，不接受目录。目录、模块名、函数名和符号名应作为 Search Hint 提供。

## Clues File 示例

```json
{
  "5939": {
    "clues": ["callback", "CallBackMode", "src/ecall"],
    "paths": ["src/ecall/xcall.c"]
  }
}
```

## 输出内容

- `docs/prd/` 或 `docs/issue/` 下的 PRD/ISSUE Markdown 文档。
- `docs/summary_report.json`。
- debug bundle，包含 prompt、response、seed locations、cited evidence locations、evidence validation issues 和 rejected seed paths。

## 安全边界

Agent CLI 子进程只应读取和搜索目标仓库，并把结构化 JSON 分析结果返回给 analyzer。它不得修改、创建或删除目标仓库源码、配置、测试、构建文件，也不得直接写 debug bundle、PRD/ISSUE 文档、summary、显式 `--output` 或显式 `--log-file`；这些输出只能由 analyzer 进程写入。
