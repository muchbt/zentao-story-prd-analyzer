from typing import List, Optional

from .zentao_client import ZentaoItem


_COMMON_SCHEMA = '''  "evidence": [
    {
      "path": "文件路径",
      "line_start": 1,
      "line_end": 20,
      "symbol": "函数或类名，可为空",
      "reason": "该证据如何支持结论"
    }
  ],
  "gaps": [],
  "suspected_causes": [],
  "affected_scope": [],
  "recommendations": ["修改建议1", "..."],
  "verification": ["验证建议1", "..."],
  "priority": "高|中|低",
  "confidence": "高|中|低",
  "output_md": ""'''


_FEATURE_TEMPLATE = """你是高级代码分析 Agent。请根据以下禅道条目和目标代码仓库，判断功能实现完成度。

【禅道条目】
ID: {id}
标题: {title}
描述: {description}
类型: {type}
状态: {status}

【代码仓库】
路径: {repo_path}

【种子上下文】
{seed_context}

【搜索建议】
{search_hints}

【权限与写入边界】
- 只允许读取和搜索代码仓库。
- 不得修改、创建、删除目标仓库源码、配置、测试或构建文件。
- 只允许 analyzer 写入 debug bundle、PRD/ISSUE 文档、summary、显式 --output、显式 --log-file。

【任务要求】
1. 主动搜索代码仓库，查找与条目相关的代码实现。
2. 从需求描述和 Search Hint 中提取函数名、宏名、结构体名、枚举、文件名等标识符搜索。
3. 优先搜索项目源码目录，避开 third-party/vendor/build/generated 等低价值目录。
4. 输出严格 JSON，不要 Markdown 代码块，不要额外解释。
5. evidence 必须引用仓库中实际存在的文件和行号，禁止编造。
6. 如果代码仓库不足以判断，请设置 conclusion="无法判断"、confidence="低"，在 evidence 中说明"相关代码证据不足"。
7. confidence="高" 意味着有直接代码证据支持；confidence="中" 意味着有间接证据或推断；confidence="低" 意味着证据不足。
8. JSON Schema:
{{
  "conclusion": "完成|部分完成|未完成|无法判断",
{common_schema}
}}
"""

_DEFECT_TEMPLATE = """你是高级代码分析 Agent。请根据以下禅道缺陷条目和目标代码仓库，分析可能根因和影响范围。

【禅道条目】
ID: {id}
标题: {title}
描述: {description}
类型: {type}
状态: {status}

【代码仓库】
路径: {repo_path}

【种子上下文】
{seed_context}

【搜索建议】
{search_hints}

【权限与写入边界】
- 只允许读取和搜索代码仓库。
- 不得修改、创建、删除目标仓库源码、配置、测试或构建文件。
- 只允许 analyzer 写入 debug bundle、PRD/ISSUE 文档、summary、显式 --output、显式 --log-file。

【任务要求】
1. 主动搜索代码仓库，查找与缺陷描述相关的代码实现。
2. 从缺陷描述和 Search Hint 中提取函数名、宏名、结构体名、枚举、文件名等标识符搜索。
3. 优先搜索项目源码目录，避开 third-party/vendor/build/generated 等低价值目录。
4. 输出严格 JSON，不要 Markdown 代码块，不要额外解释。
5. evidence 必须引用仓库中实际存在的文件和行号，禁止编造。
6. 如果代码仓库不足以分析，请设置 conclusion="无法定位"、confidence="低"，在 suspected_causes 中说明"相关代码证据不足"。
7. confidence="高" 意味着有直接代码证据支持；confidence="中" 意味着有间接证据或推断；confidence="低" 意味着证据不足。
8. JSON Schema:
{{
  "conclusion": "已定位|部分定位|无法定位",
{common_schema}
}}
"""


def _format_seed_context(snippets):
    if not snippets:
        return "[未提供种子上下文]"
    parts = []
    for snippet in snippets:
        parts.append(
            f"--- 文件: {snippet['path']} (行 {snippet['line_start']}-{snippet['line_end']}) ---\n"
            f"{snippet['content']}"
        )
    return "\n\n".join(parts)


def _format_search_hints(search_hints: Optional[List[str]]) -> str:
    if not search_hints:
        return "[未提供搜索建议]"
    return ", ".join(str(item) for item in search_hints if str(item).strip())


def build_feature_prompt(item: ZentaoItem, repo_path: str, seed_snippets=None, search_hints=None) -> str:
    return _FEATURE_TEMPLATE.format(
        id=item.id,
        title=item.title,
        description=item.description,
        type=item.type,
        status=item.status,
        repo_path=repo_path,
        seed_context=_format_seed_context(seed_snippets or []),
        search_hints=_format_search_hints(search_hints),
        common_schema=_COMMON_SCHEMA,
    )


def build_defect_prompt(item: ZentaoItem, repo_path: str, seed_snippets=None, search_hints=None) -> str:
    return _DEFECT_TEMPLATE.format(
        id=item.id,
        title=item.title,
        description=item.description,
        type=item.type,
        status=item.status,
        repo_path=repo_path,
        seed_context=_format_seed_context(seed_snippets or []),
        search_hints=_format_search_hints(search_hints),
        common_schema=_COMMON_SCHEMA,
    )
