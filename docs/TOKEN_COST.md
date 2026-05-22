# Token 消耗模型

## 概述

当前架构不再使用本地关键词 collector 预搜代码。分析阶段由 Agent CLI 在目标仓库中自主搜索，工具只把禅道条目、仓库路径、可选 Search Hint 和可选 Seed Path 片段放入 prompt。

token 估算仍按 4 字符约等于 1 token。

## 当前流程：Agent CLI 自主搜索

```text
禅道条目 + Target Repository
        │
        ├─ 可选 Search Hint（仅作为 prompt 搜索建议）
        ├─ 可选 Seed Path（读取仓库内文件作为起始上下文）
        ▼
  Agent CLI 自主搜索仓库
        ▼
  本地校验 evidence path/line
        ▼
  生成 PRD/ISSUE、summary、debug bundle
```

## Token 构成

| 组成部分 | 估算 token | 说明 |
|---------|-----------|------|
| Prompt 模板 | 700-1000 | 含 JSON Schema、搜索要求和写入边界 |
| 禅道条目 | 200-800 | 取决于标题和描述长度 |
| Search Hint | 0-300 | 用户显式提供时出现 |
| Seed Context | 默认 0-2000，硬上限 8000 | 只从 Seed Path 文件加载 |
| 单次初始 prompt 合计 | 900-10100 | 不包含 Agent CLI 后续自主搜索消耗 |

## 当前参数

| 参数 | 默认值 | 说明 |
|------|-------|------|
| `max_seed_files` | 3 | 最多预加载 3 个 Seed Path 文件 |
| `max_lines_per_seed` | 50 | 每个 Seed Path 最多 50 行 |
| `max_seed_tokens` | 2000 | 默认 Seed Context token 预算 |
| `max_seed_tokens_limit` | 8000 | Seed Context 硬上限 |
| `TOKEN_ESTIMATE_RATIO` | 4 chars/token | 估算比例 |

## 更新记录

| 版本 | 日期 | 方案 | 说明 |
|------|------|------|------|
| v2 | 2026-05-22 | Agent CLI 自主搜索 | 移除关键词 collector，使用 Search Hint 与 Seed Path |
| v1 | 2026-05-22 | 关键词预搜集 | 已废弃 |
