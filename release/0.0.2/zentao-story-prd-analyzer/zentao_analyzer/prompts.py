import os
from typing import Any, List, Optional

from .protocol_hints import ProtocolHint
from .repositories import RepositorySet
from .zentao_client import ZentaoItem


_DEFECT_EVIDENCE_SCHEMA = '''  "evidence": [
    {
      "role": "Repository Role，多仓必填，单仓可省略",
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
  "understanding_summary": "用自然语言概述你对禅道条目需求或问题的理解，不要重复证据、缺口、建议或验证步骤",
  "role_evidence_statuses": [],
  "protocol_traces": []'''


_FEATURE_RP_EVIDENCE_SCHEMA = '''          {
            "role": "Repository Role，多仓必填，单仓可省略",
            "path": "文件路径",
            "line_start": 1,
            "line_end": 20,
            "symbol": "函数或类名，可为空",
            "reason": "该证据如何支持此需求点结论"
          }'''


_SOURCE_SCHEMA = '"source": "requirement|code_context|insufficient"'

_INTERPRETATION_SCHEMA = '''  "requirement_interpretation": {
    "summary": "需求摘要，依据 Requirement Source 生成",
    "scope": [
      {"text": "范围项描述", "source": "requirement|code_context|insufficient"}
    ],
    "terms": [
      {"term": "术语", "definition": "术语定义", "source": "requirement|code_context|insufficient"}
    ],
    "rules": [
      {"title": "规则标题", "description": "规则描述", "source": "requirement"}
    ],
    "scenarios": [
      {
        "title": "场景标题",
        "precondition": "前置条件，可空",
        "trigger": "触发条件，可空",
        "expected_behavior": ["预期行为1", "预期行为2"],
        "source": "requirement|code_context|insufficient"
      }
    ],
    "matrix": {
      "title": "矩阵标题",
      "columns": ["列1", "列2"],
      "rows": [["行1列1", "行1列2"]],
      "source": "requirement|insufficient"
    },
    "flow": {
      "title": "流程标题",
      "content": "文本或 Mermaid/ASCII 流程描述",
      "source": "requirement|insufficient"
    },
    "pending_confirmations": ["待确认项1"]
  },'''

_CODE_IMPACT_SCHEMA = '''  "code_impact": {
    "related_locations": [
      {
        "component": "模块名称",
        "role": "Repository Role，多仓必填，单仓可省略",
        "path": "文件路径",
        "line_start": 1,
        "line_end": 20,
        "symbol": "函数或类名，可为空",
        "reason": "该位置与需求的关联说明"
      }
    ],
    "impact_notes": ["受需求影响的现有模块说明"]
  },'''

_FEATURE_TEMPLATE = """你是高级代码分析 Agent。请根据以下禅道条目和目标代码仓库，分析功能实现完成度。

【条目信息】
ID: {id}
标题: {title}
描述: {description}
类型: {type}
状态: {status}
来源: {requirement_source}

【代码仓库】
{repository_context}

【种子上下文】
{seed_context}

【搜索建议】
{search_hints}

【通信协议线索】
{protocol_hints}

【权限与写入边界】
- 只允许读取和搜索代码仓库。
- 你是 Agent CLI 子进程，只能返回 JSON 分析结果，不能写入任何文件。
- 不得修改、创建、删除目标仓库源码、配置、测试或构建文件。
- 只有 analyzer 进程可以写入 debug bundle、PRD/ISSUE 文档、summary、显式 --output、显式 --log-file。

【任务要求】
1. 主动搜索代码仓库，查找与条目相关的代码实现。
2. 从需求描述和 Search Hint 中提取函数名、宏名、结构体名、枚举、文件名等标识符搜索。
3. 优先搜索项目源码目录，避开 third-party/vendor/build/generated 等低价值目录。
4. 输出严格 JSON，不要 Markdown 代码块，不要额外解释。
5. JSON 字符串值中不得使用未转义的 ASCII 双引号（"），中文引述请用中文引号""或单引号，或用 \\\" 转义。

【需求点拆分要求】
6. 将原始需求描述拆分为一个或多个可独立验证的需求点（Requirement Point）。
7. 每个需求点描述一个可独立验证的预期行为单元，不是代码文件名或测试步骤。
8. 需求点描述只能依据原始需求，不能从用户搜索建议或代码线索中推导新需求。
9. 为每个需求点独立判断实现状态、给出判定理由、关联代码证据和确认缺口。
10. 如果代码仓库不足以判断某个需求点，该需求点状态设为"无法判断"，reason 说明证据不足。

【状态与缺口约束】
11. 需求点状态只能是：完成、部分完成、未完成、无法判断。
12. 状态为"未完成"或"部分完成"时，gaps 必须包含至少一条确认的实现缺失或差异。没有确认缺口时，状态不得为"未完成"或"部分完成"，应设为"无法判断"。
13. 状态为"完成"或"无法判断"时，gaps 必须为空数组。
14. 完全没有有效代码证据的需求点，reason 中可说明"无代码证据"，但这不等同于确认缺口。

【证据约束】
15. evidence 必须引用仓库中实际存在的文件和行号，禁止编造。
16. 每条 evidence 的 reason 必须说明该证据如何支持此需求点的结论。
17. code_impact.related_locations 与 requirement_points.evidence 是独立的：related_locations 只说明需求与代码的关联，不作为完成度证据。
18. 多仓模式下每条证据必须包含 Repository Role；跨 Repository Role 的完成度不能由单侧 Code Evidence 单独确认。
19. Protocol Hint 只用于指导通信协议搜索，不能新增需求点，也不能直接作为 Code Evidence。

【需求解读约束】
20. requirement_interpretation 的每个字段都应基于 Requirement Source（原始需求正文）整理。
21. source 枚举值为 requirement（来自需求正文）、code_context（来自代码侧候选上下文）、insufficient（原文信息不足）。
22. source 为 code_context 的内容仅表明仓库中存在相关命名或模块，不构成需求定义或完成度证据。
23. source 为 insufficient 时不可编造内容，该字段展示"原始需求未提供足够信息"。
24. 章节内容不足时，必须以 source: "insufficient" 标明，不能为了填满模板补造事实。

【其他字段】
25. understanding_summary 只概述你对需求本身的理解，不要重复需求点判定、证据、缺口或建议。
26. priority 和 verification 分别为整体优先级和验证建议。
27. recommendations 为建议性内容，可包含新模块、新接口或测试策略建议，但必须明确标记为建议，不得描述为已有实现。

【JSON Schema】
{{
  "requirement_interpretation": {{
    "summary": "需求摘要",
    "scope": [{{"text": "范围项", {source_schema}}}],
    "terms": [{{"term": "术语", "definition": "定义", {source_schema}}}],
    "rules": [{{"title": "规则标题", "description": "规则描述", {source_schema}}}],
    "scenarios": [{{"title": "场景标题", "precondition": "前置条件", "trigger": "触发条件", "expected_behavior": ["行为1"], {source_schema}}}],
    "matrix": {{"title": "矩阵标题", "columns": ["列1"], "rows": [["行1"]], {source_schema}}},
    "flow": {{"title": "流程标题", "content": "流程描述", {source_schema}}},
    "pending_confirmations": ["待确认项"]
  }},
  "code_impact": {{
    "related_locations": [
      {{
        "component": "模块名称",
        "role": "Repository Role，多仓必填，单仓可省略",
        "path": "文件路径",
        "line_start": 1,
        "line_end": 20,
        "symbol": "函数或类名，可为空",
        "reason": "该位置与需求的关联说明"
      }}
    ],
    "impact_notes": ["受需求影响的现有模块说明"]
  }},
  "requirement_points": [
    {{
      "description": "可独立验证的需求点描述",
      "status": "完成|部分完成|未完成|无法判断",
      "reason": "判定说明",
      "gaps": ["确认的实现缺失或差异，状态为未完成或部分完成时必须非空"],
      "evidence": [
{rp_evidence_schema}
      ]
    }}
  ],
  "understanding_summary": "自然语言概述对需求本身的理解",
  "priority": "高|中|低",
  "recommendations": ["修改建议1", "..."],
  "verification": ["验证建议1", "..."],
  "role_evidence_statuses": [
    {{"role": "Repository Role", "status": "found|not_found|ambiguous|not_searched", "searched_for": ["搜索词"], "explanation": "命中或未命中说明"}}
  ],
  "protocol_traces": [
    {{
      "hint": {{"roles": ["soc", "mcu"], "type": "cmd_id|msg|field|text", "value": "协议线索"}},
      "status": "closed_loop|partial|not_found|ambiguous",
      "role_statuses": [{{"role": "soc", "status": "found|not_found|ambiguous|not_searched", "searched_for": ["搜索词"], "explanation": "说明"}}],
      "evidence": [{{"role": "soc", "path": "文件路径", "line_start": 1, "line_end": 20, "symbol": "符号", "reason": "协议关联说明"}}],
      "explanation": "跨角色协议关联说明"
    }}
  ]
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
{repository_context}

【种子上下文】
{seed_context}

【搜索建议】
{search_hints}

【通信协议线索】
{protocol_hints}

【权限与写入边界】
- 只允许读取和搜索代码仓库。
- 你是 Agent CLI 子进程，只能返回 JSON 分析结果，不能写入任何文件。
- 不得修改、创建、删除目标仓库源码、配置、测试或构建文件。
- 只有 analyzer 进程可以写入 debug bundle、PRD/ISSUE 文档、summary、显式 --output、显式 --log-file。

【任务要求】
1. 主动搜索代码仓库，查找与缺陷描述相关的代码实现。
2. 从缺陷描述和 Search Hint 中提取函数名、宏名、结构体名、枚举、文件名等标识符搜索。
3. 优先搜索项目源码目录，避开 third-party/vendor/build/generated 等低价值目录。
4. 输出严格 JSON，不要 Markdown 代码块，不要额外解释。
5. JSON 字符串值中不得使用未转义的 ASCII 双引号（"），中文引述请用中文引号""或单引号，或用 \\\" 转义。
6. evidence 必须引用仓库中实际存在的文件和行号，禁止编造。
7. 如果代码仓库不足以分析，请设置 conclusion="无法定位"、confidence="低"，在 suspected_causes 中说明"相关代码证据不足"。
8. confidence="高" 意味着有直接代码证据支持；confidence="中" 意味着有间接证据或推断；confidence="低" 意味着证据不足。
9. understanding_summary 只概述你对缺陷或反馈本身的理解，不要复制 conclusion、evidence、suspected_causes、recommendations 或 verification。
10. 多仓模式下每条 evidence 必须包含 Repository Role；Protocol Hint 只指导搜索，不是证据。
11. JSON Schema:
{{
  "conclusion": "已定位|部分定位|无法定位",
{defect_evidence_schema}
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


def _format_repository_context(repo_path: str, repo_set: Optional[RepositorySet], workspace: Any = None, primary_role: str = "") -> str:
    if not repo_set or not repo_set.show_roles:
        return f"路径: {repo_path}"
    lines = ["Target Repository Set:"]
    for repo in repo_set.repositories:
        search_path = os.path.join(workspace.path, repo.role) if workspace and workspace.available else repo.path
        lines.append(f"- {repo.role}: 搜索路径 {search_path}；原始路径 {repo.path}")
    if primary_role:
        lines.append(f"- Primary Repository Role: {primary_role}（仅影响搜索与展示优先级）")
    return "\n".join(lines)


def _format_protocol_hints(protocol_hints: Optional[List[ProtocolHint]]) -> str:
    if not protocol_hints:
        return "[未提供通信协议线索]"
    return "\n".join(f"- roles={','.join(hint.roles)}; {hint.type}={hint.value}" for hint in protocol_hints)


def build_feature_prompt(
    item: ZentaoItem,
    repo_path: str,
    seed_snippets=None,
    search_hints=None,
    repo_set: Optional[RepositorySet] = None,
    workspace: Any = None,
    protocol_hints: Optional[List[ProtocolHint]] = None,
    primary_role: str = "",
) -> str:
    return _FEATURE_TEMPLATE.format(
        id=item.id,
        title=item.title,
        description=item.description,
        type=item.type,
        status=item.status,
        requirement_source=getattr(item, "requirement_source", "zentao") or "zentao",
        repository_context=_format_repository_context(repo_path, repo_set, workspace, primary_role),
        seed_context=_format_seed_context(seed_snippets or []),
        search_hints=_format_search_hints(search_hints),
        protocol_hints=_format_protocol_hints(protocol_hints),
        rp_evidence_schema=_FEATURE_RP_EVIDENCE_SCHEMA,
        source_schema=_SOURCE_SCHEMA.strip(),
        interpretation_schema=_INTERPRETATION_SCHEMA.strip(),
        code_impact_schema=_CODE_IMPACT_SCHEMA.strip(),
    )


def build_defect_prompt(
    item: ZentaoItem,
    repo_path: str,
    seed_snippets=None,
    search_hints=None,
    repo_set: Optional[RepositorySet] = None,
    workspace: Any = None,
    protocol_hints: Optional[List[ProtocolHint]] = None,
    primary_role: str = "",
) -> str:
    return _DEFECT_TEMPLATE.format(
        id=item.id,
        title=item.title,
        description=item.description,
        type=item.type,
        status=item.status,
        repository_context=_format_repository_context(repo_path, repo_set, workspace, primary_role),
        seed_context=_format_seed_context(seed_snippets or []),
        search_hints=_format_search_hints(search_hints),
        protocol_hints=_format_protocol_hints(protocol_hints),
        defect_evidence_schema=_DEFECT_EVIDENCE_SCHEMA,
    )
