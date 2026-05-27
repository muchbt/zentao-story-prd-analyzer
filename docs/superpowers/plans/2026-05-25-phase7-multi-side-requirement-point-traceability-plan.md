# 阶段七：多侧代码分析与需求点追溯 Implementation Plan

> **废弃说明（2026-05-27）**：本计划及其多侧范围方向均未进入实现，且已由新的“阶段七：深度 PRD 生成与双输入来源”取代。本文仅保留为历史记录，不得作为实施依据。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在显式启用多侧工程映射时，为 Feature Item 增加受范围约束的 MCU/SOC 等多侧分析、需求点级证据追溯和可审计的责任侧提示，同时保持普通单仓库调用兼容。

**Architecture:** 新增 `multi_side.py` 作为阶段七输入与范围策略边界，将 Code Side、Analysis Scope、Responsibility Hint 和严格搜索根计算从 `main.py` 中隔离。扩展 `AnalysisResult` 以承载 Requirement Point 与 Candidate Location；`prompts.py`/`analyzer.py` 负责 Agent 合约和本地位置校验；现有 document/summary/debug/main 只消费结构化结果并负责输出、前置拒绝和兼容字段。

**Tech Stack:** Python 3.8+, dataclasses, argparse, json, pathlib/os, unittest, unittest.mock, tempfile

---

## 实施约束

- 本计划已废弃，不得作为实施依据；替代设计与实施计划使用新的阶段七文档。
- 需求预期行为仅来自禅道原始描述；不得实现已废弃的补充需求内容入口。
- 阶段七仅在用户通过 `--code-side` 或 `--code-sides-file` 显式配置 Code Side 后激活；不得扫描目录名称自动开启。
- 普通单仓库分析的既有 stdout JSON、PRD/ISSUE、Prompt 与测试行为必须保持不变。
- `Responsibility Hint` 是责任归属元数据，不是 Code Clue；`Candidate Location` 是诊断材料，不是 Code Evidence。
- 语义性校验（例如提示是否唯一匹配 Agent 提议的 Requirement Point）只能在 Agent 返回结构后判定；纯结构和范围错误必须在启动 Agent 之前拒绝。

## File Map

| File | Responsibility | Action |
|------|----------------|--------|
| `zentao_analyzer/multi_side.py` | Code Side 配置、Analysis Scope、Responsibility Hint 解析与前置范围策略 | Create |
| `zentao_analyzer/analysis_result.py` | Requirement Point、Candidate Location、责任侧来源与嵌套证据数据模型 | Modify |
| `zentao_analyzer/code_clues.py` | clues file 保留现有线索并透传按条目责任提示结构 | Modify |
| `zentao_analyzer/prompts.py` | 显式多侧 Feature Prompt 与严格 JSON schema；保持默认 Prompt 不变 | Modify |
| `zentao_analyzer/analyzer.py` | 分析根目录、侧别边界、候选位置和需求点证据本地校验 | Modify |
| `zentao_analyzer/document_generator.py` | PRD 需求点表格、范围内结论、无效提示披露；不展示候选路径 | Modify |
| `zentao_analyzer/summary_report.py` | 可选阶段七索引字段与兼容顶层结论 | Modify |
| `zentao_analyzer/debug_bundle.py` | 多侧配置、提示应用/拒绝、候选位置审计输出 | Modify |
| `zentao_analyzer/main.py` | CLI、前置拒绝、按范围调用、跳过不应生成的产物、stdout 组装 | Modify |
| `SKILL.md` | 自然语言触发格式和拒绝补充需求输入边界 | Modify |
| `README.md` | 多侧命令、状态、产物与兼容说明 | Modify |
| `tests/test_multi_side.py` | 输入解析与范围策略单元测试 | Create |
| `tests/test_analysis_result.py` | 阶段七响应解析及旧结构兼容测试 | Modify |
| `tests/test_code_clues.py` | clues file 中责任提示读取测试 | Modify |
| `tests/test_prompts.py` | 多侧 Prompt 合约与默认 Prompt 回归测试 | Modify |
| `tests/test_analyzer.py` | Scope 证据/候选位置验证与搜索根测试 | Modify |
| `tests/test_document_generator.py` | PRD 需求点与范围内显示测试 | Modify |
| `tests/test_summary_report.py` | 可选 summary 字段及旧结构测试 | Modify |
| `tests/test_debug_bundle.py` | 责任提示和候选位置留痕测试 | Modify |
| `tests/test_main_phase7.py` | 阶段七 CLI 端到端编排与前置失败测试 | Create |

---

### Task 1: Multi-Side Input Model And Preflight Scope Policy

**Files:**
- Create: `zentao_analyzer/multi_side.py`
- Test: `tests/test_multi_side.py`

- [ ] **Step 1: Write failing tests for explicit activation, scope validation, hints and execution roots**

```python
# tests/test_multi_side.py
import json
import os
import tempfile
import unittest

from zentao_analyzer.multi_side import (
    MultiSideInputError,
    build_multi_side_context,
    load_code_sides_file,
    parse_responsibility_hints,
)


class TestMultiSideInput(unittest.TestCase):
    def test_no_explicit_mapping_leaves_single_repo_mode_disabled(self):
        ctx = build_multi_side_context("/repo", cli_code_sides=[], code_sides_file="", analysis_scope="")
        self.assertFalse(ctx.enabled)
        self.assertEqual(ctx.analysis_root, "/repo")

    def test_code_sides_file_requires_explicit_scope_for_multiple_sides(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "sides.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"code_sides": {"mcu": "mcu_src", "soc": "soc_src"}}, f)
            with self.assertRaisesRegex(MultiSideInputError, "analysis_scope_required"):
                build_multi_side_context(td, [], path, "")

    def test_single_side_scope_uses_selected_side_as_agent_root(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "soc_src"))
            ctx = build_multi_side_context(td, ["soc=soc_src"], "", "soc")
            self.assertTrue(ctx.enabled)
            self.assertEqual(ctx.selected_sides, ["soc"])
            self.assertEqual(ctx.analysis_root, os.path.realpath(os.path.join(td, "soc_src")))
            self.assertTrue(ctx.is_scope_limited_analysis is False)

    def test_multi_subset_of_three_sides_is_rejected(self):
        with self.assertRaisesRegex(MultiSideInputError, "multi_side_subset_not_isolated"):
            build_multi_side_context("/repo", ["mcu=mcu", "soc=soc", "display=display"], "", "mcu,soc")

    def test_parse_hints_deduplicates_exact_values_and_rejects_conflicting_fragment(self):
        hints, duplicates = parse_responsibility_hints(
            ["发送终止服务信号=mcu", "发送终止服务信号=mcu"]
        )
        self.assertEqual(hints[0].sides, ["mcu"])
        self.assertEqual(len(duplicates), 1)
        with self.assertRaisesRegex(MultiSideInputError, "conflicting_responsibility_hint"):
            parse_responsibility_hints(["发送终止服务信号=mcu", "发送终止服务信号=soc"])
```

- [ ] **Step 2: Run the tests and confirm the new module is absent**

Run: `python3 -m pytest -q tests/test_multi_side.py`

Expected: FAIL because `zentao_analyzer.multi_side` does not exist.

- [ ] **Step 3: Add focused domain/input dataclasses and parsers**

```python
# zentao_analyzer/multi_side.py
import dataclasses
import json
import os
from typing import Dict, Iterable, List, Tuple


class MultiSideInputError(ValueError):
    pass


@dataclasses.dataclass
class ResponsibilityHint:
    fragment: str
    sides: List[str]
    source: str = "cli"


@dataclasses.dataclass
class MultiSideContext:
    enabled: bool = False
    repo_path: str = "."
    code_sides: Dict[str, str] = dataclasses.field(default_factory=dict)
    selected_sides: List[str] = dataclasses.field(default_factory=list)
    analysis_root: str = "."
    is_scope_limited_analysis: bool = False
    responsibility_hints: List[ResponsibilityHint] = dataclasses.field(default_factory=list)
    duplicate_responsibility_hints: List[ResponsibilityHint] = dataclasses.field(default_factory=list)


def parse_code_side_values(values: Iterable[str]) -> Dict[str, str]:
    result = {}
    for raw in values or []:
        if "=" not in str(raw):
            raise MultiSideInputError("invalid_code_side")
        name, path = (item.strip() for item in str(raw).split("=", 1))
        if not name or not path or name in result:
            raise MultiSideInputError("invalid_code_side")
        result[name] = path
    return result


def load_code_sides_file(path: str) -> Dict[str, str]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    sides = data.get("code_sides", {}) if isinstance(data, dict) else {}
    if not isinstance(sides, dict):
        raise MultiSideInputError("invalid_code_sides_file")
    return parse_code_side_values([f"{name}={value}" for name, value in sides.items()])


def parse_responsibility_hints(values, source="cli") -> Tuple[List[ResponsibilityHint], List[ResponsibilityHint]]:
    hints, duplicates, by_fragment = [], [], {}
    for raw in values or []:
        if "=" not in str(raw):
            raise MultiSideInputError("invalid_responsibility_hint")
        fragment, raw_sides = str(raw).split("=", 1)
        fragment = fragment.strip().strip('"')
        sides = sorted({side.strip() for side in raw_sides.split(",") if side.strip()})
        if not fragment or not sides:
            raise MultiSideInputError("invalid_responsibility_hint")
        hint = ResponsibilityHint(fragment=fragment, sides=sides, source=source)
        if fragment in by_fragment and by_fragment[fragment].sides != sides:
            raise MultiSideInputError("conflicting_responsibility_hint")
        if fragment in by_fragment:
            duplicates.append(hint)
        else:
            hints.append(hint)
            by_fragment[fragment] = hint
    return hints, duplicates
```

Implement `build_multi_side_context(repo_path, cli_code_sides, code_sides_file, analysis_scope, cli_responsibility_hints=None, clues_by_item=None, item_id="")` in the same module with these exact policies:

- no `--code-side` and no `--code-sides-file` returns `enabled=False`, without inspecting `mcu_src/` or `soc_src/`;
- `--code-side` mappings override same-name entries from file mappings;
- more than one configured side requires a non-empty `analysis_scope`;
- selected names must exist in the merged mapping;
- each mapped directory must resolve inside `repo_path` and exist as a directory;
- one selected side sets `analysis_root` to that side directory;
- selecting all configured sides sets `analysis_root` to `repo_path`;
- selecting multiple but fewer than all configured sides raises `multi_side_subset_not_isolated`;
- a hint side outside `selected_sides` raises `responsibility_outside_scope`.

- [ ] **Step 4: Run focused tests**

Run: `python3 -m pytest -q tests/test_multi_side.py`

Expected: PASS.

- [ ] **Step 5: Commit this unit**

```bash
git add zentao_analyzer/multi_side.py tests/test_multi_side.py
git commit -m "feat: add multi-side analysis input model"
```

---

### Task 2: Requirement Point And Candidate Location Result Contract

**Files:**
- Modify: `zentao_analyzer/analysis_result.py`
- Modify: `tests/test_analysis_result.py`

- [ ] **Step 1: Add failing tests for requirement-point parsing and legacy compatibility**

```python
def test_from_llm_json_parses_multi_side_requirement_points(self):
    item = ZentaoItem(id="20", type="requirement", title="终止服务")
    result = AnalysisResult.from_llm_json(item, {
        "conclusion": "完成",
        "requirement_points": [{
            "description": "发送终止服务信号",
            "responsible_sides": ["mcu"],
            "responsibility_source": "agent_inferred",
            "responsibility_reason": "需求要求发送 MCU 总线消息",
            "status": "完成",
            "note": "发送逻辑存在",
            "evidence": [{
                "side": "mcu", "path": "mcu_src/tx.c",
                "line_start": 2, "line_end": 5, "symbol": "send_stop", "reason": "发送消息"
            }]
        }]
    }, multi_side_enabled=True)
    self.assertEqual(result.requirement_points[0].id, "RP-001")
    self.assertEqual(result.requirement_points[0].evidence[0].side, "mcu")
    self.assertEqual(result.requirement_points[0].responsibility_source, "agent_inferred")


def test_multi_side_response_keeps_candidates_separate_from_evidence(self):
    item = ZentaoItem(id="21", type="requirement", title="同步")
    result = AnalysisResult.from_llm_json(item, {
        "requirement_points": [{
            "description": "同步状态", "status": "责任侧待确认",
            "candidate_locations": [{"side": "soc", "path": "soc_src/a.c", "line_start": 1, "line_end": 1}]
        }]
    }, multi_side_enabled=True)
    self.assertEqual(len(result.requirement_points[0].candidate_locations), 1)
    self.assertEqual(result.cited_evidence_locations, [])


def test_default_response_has_no_phase7_payload(self):
    item = ZentaoItem(id="22", type="story", title="旧模式")
    result = AnalysisResult.from_llm_json(item, {"conclusion": "完成", "evidence": ["src/a.c:1-1 ok"]})
    self.assertEqual(result.requirement_points, [])
    self.assertFalse(result.multi_side_enabled)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python3 -m pytest -q tests/test_analysis_result.py`

Expected: FAIL because `RequirementPoint`, `CandidateLocation` and `multi_side_enabled` do not exist.

- [ ] **Step 3: Extend the structured model without changing old parsing**

Add these dataclasses and fields:

```python
@dataclasses.dataclass
class SideEvidenceLocation(EvidenceLocation):
    side: str = ""


@dataclasses.dataclass
class CandidateLocation:
    side: str
    path: str
    line_start: int
    line_end: int
    symbol: str = ""
    reason: str = ""


@dataclasses.dataclass
class RequirementPoint:
    id: str
    description: str
    responsible_sides: List[str] = dataclasses.field(default_factory=list)
    responsibility_source: str = "pending"
    responsibility_reason: str = ""
    status: str = "责任侧待确认"
    note: str = ""
    evidence: List[SideEvidenceLocation] = dataclasses.field(default_factory=list)
    candidate_locations: List[CandidateLocation] = dataclasses.field(default_factory=list)
```

Extend `AnalysisResult`:

```python
multi_side_enabled: bool = False
analysis_scope: List[str] = dataclasses.field(default_factory=list)
is_scope_limited_analysis: bool = False
scope_conclusion: str = ""
requirement_points: List[RequirementPoint] = dataclasses.field(default_factory=list)
invalid_responsibility_hints: List[Dict[str, Any]] = dataclasses.field(default_factory=list)
```

Change `from_llm_json(cls, item: ZentaoItem, data: Dict[str, Any], raw_response: str = "", multi_side_enabled: bool = False)` so old callers preserve the existing flat evidence contract. When `multi_side_enabled=True`, assign sequential `RP-001` IDs, parse nested evidence/candidates, and aggregate only nested formal evidence into `cited_evidence_locations`.

- [ ] **Step 4: Run result tests**

Run: `python3 -m pytest -q tests/test_analysis_result.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add zentao_analyzer/analysis_result.py tests/test_analysis_result.py
git commit -m "feat: model requirement point analysis results"
```

---

### Task 3: Clues File Responsibility Hint Input

**Files:**
- Modify: `zentao_analyzer/code_clues.py`
- Modify: `tests/test_code_clues.py`

- [ ] **Step 1: Add failing tests for structured responsibility hints**

```python
def test_load_clues_file_preserves_structured_responsibility_hints(self):
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "clues.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"5923": {
                "clues": ["StopServiceMsg"],
                "paths": ["soc_src/a.c"],
                "responsibility_hints": [{"fragment": "退出服务状态", "sides": ["soc"]}]
            }}, f, ensure_ascii=False)
        data = load_clues_file(path)
    self.assertEqual(data["5923"]["responsibility_hints"][0]["fragment"], "退出服务状态")
    self.assertEqual(data["5923"]["responsibility_hints"][0]["sides"], ["soc"])


def test_invalid_responsibility_hint_shape_raises_input_error(self):
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "clues.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"5923": {"responsibility_hints": [{"fragment": "", "sides": ["soc"]}]}}, f)
        with self.assertRaises(ValueError):
            load_clues_file(path)
```

- [ ] **Step 2: Run tests and observe missing field behavior**

Run: `python3 -m pytest -q tests/test_code_clues.py`

Expected: FAIL because `load_clues_file()` currently returns only `clues` and `paths`.

- [ ] **Step 3: Parse only the new structured array and keep existing clue behavior**

Import `ResponsibilityHint`/`MultiSideInputError` from `multi_side.py`, validate each file entry as `{"fragment": non_empty_string, "sides": non_empty_string_list}`, and add:

```python
normalized[str(item_id)] = {
    "clues": parse_csv_values(clues.get("clues")),
    "paths": parse_csv_values(clues.get("paths")),
    "responsibility_hints": responsibility_hints,
}
```

Do not add any supplemental-requirement field and do not reinterpret `clues` as responsibility.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest -q tests/test_code_clues.py tests/test_multi_side.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add zentao_analyzer/code_clues.py tests/test_code_clues.py
git commit -m "feat: load responsibility hints from clues files"
```

---

### Task 4: Multi-Side Feature Prompt And Agent Contract

**Files:**
- Modify: `zentao_analyzer/prompts.py`
- Modify: `tests/test_prompts.py`

- [ ] **Step 1: Add failing Prompt tests**

```python
def test_multi_side_feature_prompt_separates_requirement_clues_scope_and_responsibility(self):
    item = ZentaoItem(id="5923", type="requirement", title="终止服务", description="发送终止服务信号")
    prompt = build_feature_prompt(
        item, repo_path="/root", search_hints=["StopServiceMsg"],
        multi_side={
            "analysis_scope": ["mcu", "soc"],
            "allowed_paths": {"mcu": "/root/mcu_src", "soc": "/root/soc_src"},
            "responsibility_hints": [{"fragment": "发送终止服务信号", "sides": ["mcu"]}],
        },
    )
    self.assertIn("【分析范围】", prompt)
    self.assertIn("【责任侧提示（不是需求内容）】", prompt)
    self.assertIn("仅来自【禅道条目】", prompt)
    self.assertIn('"requirement_points"', prompt)
    self.assertIn('"candidate_locations"', prompt)


def test_default_feature_prompt_does_not_request_phase7_fields(self):
    item = ZentaoItem(id="1", type="story", title="旧模式")
    prompt = build_feature_prompt(item, repo_path="/repo")
    self.assertNotIn("requirement_points", prompt)
    self.assertNotIn("责任侧提示", prompt)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python3 -m pytest -q tests/test_prompts.py`

Expected: FAIL because `build_feature_prompt()` has no `multi_side` contract.

- [ ] **Step 3: Add a separate phase-seven template path**

Keep `_FEATURE_TEMPLATE` unchanged for ordinary repositories. Add `_MULTI_SIDE_FEATURE_TEMPLATE` and:

```python
def build_feature_prompt(item, repo_path, seed_snippets=None, search_hints=None, multi_side=None):
    if not multi_side:
        return _FEATURE_TEMPLATE.format(
            id=item.id, title=item.title, description=item.description,
            type=item.type, status=item.status, repo_path=repo_path,
            seed_context=_format_seed_context(seed_snippets or []),
            search_hints=_format_search_hints(search_hints),
            common_schema=_COMMON_SCHEMA,
        )
    return _MULTI_SIDE_FEATURE_TEMPLATE.format(
        id=item.id, title=item.title, description=item.description,
        type=item.type, status=item.status, repo_path=repo_path,
        seed_context=_format_seed_context(seed_snippets or []),
        search_hints=_format_search_hints(search_hints),
        analysis_scope=_format_scope(multi_side["analysis_scope"], multi_side["allowed_paths"]),
        responsibility_hints=_format_responsibility_hints(multi_side["responsibility_hints"]),
    )
```

The new JSON schema must contain:

```json
{
  "conclusion": "完成|部分完成|未完成|无法判断",
  "scope_conclusion": "",
  "requirement_points": [{
    "description": "仅由禅道原文拆出的可验证行为",
    "responsible_sides": ["mcu"],
    "responsibility_source": "zentao_explicit|responsibility_hint|agent_inferred|pending",
    "responsibility_reason": "agent_inferred 时必填",
    "status": "完成|部分完成|未完成|无法判断|责任侧待确认|范围外未评估",
    "note": "",
    "evidence": [{"side": "mcu", "path": "", "line_start": 1, "line_end": 1, "symbol": "", "reason": ""}],
    "candidate_locations": []
  }],
  "invalid_responsibility_hints": []
}
```

The prompt must expressly forbid:

- treating Search Hint as a requirement;
- inferring responsibility from where code was found;
- using `candidate_locations` as evidence;
- emitting Candidate Location unless a point remains `责任侧待确认`.

- [ ] **Step 4: Run Prompt tests**

Run: `python3 -m pytest -q tests/test_prompts.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add zentao_analyzer/prompts.py tests/test_prompts.py
git commit -m "feat: add multi-side feature prompt contract"
```

---

### Task 5: Analyzer Scope Enforcement And Location Validation

**Files:**
- Modify: `zentao_analyzer/analyzer.py`
- Modify: `tests/test_analyzer.py`

- [ ] **Step 1: Add failing tests for scope-aware validation and analysis**

```python
def test_multi_side_analysis_passes_scope_contract_and_parses_points(self):
    with tempfile.TemporaryDirectory() as td:
        soc = os.path.join(td, "soc_src")
        os.makedirs(soc)
        with open(os.path.join(soc, "state.c"), "w", encoding="utf-8") as f:
            f.write("line\n")
        item = ZentaoItem(id="1", type="requirement", title="T", description="退出服务状态")
        context = MultiSideContext(
            enabled=True, repo_path=td, code_sides={"soc": soc},
            selected_sides=["soc"], analysis_root=soc,
        )
        response = {"requirement_points": [{
            "description": "退出服务状态", "responsible_sides": ["soc"],
            "responsibility_source": "responsibility_hint", "status": "完成",
            "evidence": [{"side": "soc", "path": "state.c", "line_start": 1, "line_end": 1}]
        }]}
        with patch("zentao_analyzer.analyzer.call_llm", return_value=response):
            result = analyze(item, soc, agent_config=MagicMock(), multi_side_context=context)
        self.assertEqual(result.requirement_points[0].status, "完成")
        self.assertEqual(result.evidence_validation_issues, [])


def test_evidence_side_mismatch_is_invalid(self):
    issue = validate_scoped_location(
        SideEvidenceLocation(side="mcu", path="soc_src/state.c", line_start=1, line_end=1),
        repo_path="/root", code_sides={"mcu": "/root/mcu_src", "soc": "/root/soc_src"},
        selected_sides=["mcu", "soc"],
    )
    self.assertEqual(issue.reason, "side_path_mismatch")


def test_candidate_location_is_validated_but_does_not_become_evidence(self):
    with tempfile.TemporaryDirectory() as td:
        soc = os.path.join(td, "soc_src")
        os.makedirs(soc)
        with open(os.path.join(soc, "state.c"), "w", encoding="utf-8") as f:
            f.write("line\n")
        item = ZentaoItem(id="2", type="requirement", title="T", description="同步状态")
        context = MultiSideContext(
            enabled=True, repo_path=td, code_sides={"soc": soc},
            selected_sides=["soc"], analysis_root=soc,
        )
        response = {"requirement_points": [{
            "description": "同步状态", "responsibility_source": "pending",
            "status": "责任侧待确认",
            "candidate_locations": [{"side": "soc", "path": "state.c", "line_start": 1, "line_end": 1}]
        }]}
        with patch("zentao_analyzer.analyzer.call_llm", return_value=response):
            result = analyze(item, soc, agent_config=MagicMock(), multi_side_context=context)
    self.assertEqual(len(result.requirement_points[0].candidate_locations), 1)
    self.assertEqual(result.cited_evidence_locations, [])
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python3 -m pytest -q tests/test_analyzer.py`

Expected: FAIL because scoped location and multi-side analysis parameters are not implemented.

- [ ] **Step 3: Add scope-aware analyzer entry and validators**

Extend:

```python
def analyze(
    item, repo_path, agent="claude", agent_config=None, seed_paths=None,
    search_hints=None, rejected_seed_paths=None, max_seed_files=3,
    max_lines_per_seed=50, max_seed_tokens=2000, debug_recorder=None,
    multi_side_context=None,
) -> AnalysisResult:
    prompt_repo_path = repo_path
    if item.type in ("story", "requirement") and multi_side_context and multi_side_context.enabled:
        prompt = build_feature_prompt(
            item, prompt_repo_path, seed_result.snippets, search_hints,
            multi_side=multi_side_context.to_prompt_dict(),
        )
        result = AnalysisResult.from_llm_json(
            item, llm_data, raw_response=llm_data.get("raw", ""), multi_side_enabled=True
        )
        result.analysis_scope = list(multi_side_context.selected_sides)
        result.is_scope_limited_analysis = multi_side_context.is_scope_limited_analysis
        result.evidence_validation_issues = validate_requirement_point_locations(multi_side_context, result)
    else:
        # existing flow unchanged
```

Add validation helpers that:

- resolve paths relative to the selected-side analysis root for single-side mode and relative to repository root for all-side mode;
- require formal evidence `side` to be selected and path to live under that side mapping;
- validate Candidate Location with the same file/line/side checks but never append it to `cited_evidence_locations`;
- lower confidence and prevent `完成` when formal evidence fails validation;
- leave `责任侧待确认` candidates as debug-only data.

- [ ] **Step 4: Run focused tests**

Run: `python3 -m pytest -q tests/test_analyzer.py tests/test_prompts.py tests/test_analysis_result.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add zentao_analyzer/analyzer.py tests/test_analyzer.py
git commit -m "feat: enforce multi-side analysis boundaries"
```

---

### Task 6: PRD, Summary And Debug Bundle Outputs

**Files:**
- Modify: `zentao_analyzer/document_generator.py`
- Modify: `zentao_analyzer/summary_report.py`
- Modify: `zentao_analyzer/debug_bundle.py`
- Modify: `tests/test_document_generator.py`
- Modify: `tests/test_summary_report.py`
- Modify: `tests/test_debug_bundle.py`

- [ ] **Step 1: Add failing output tests**

```python
def test_multi_side_prd_renders_requirement_points_without_candidates(self):
    analysis = AnalysisResult(
        item_id="1", item_type="requirement", item_title="T",
        conclusion="无法判断", multi_side_enabled=True,
        analysis_scope=["soc"], is_scope_limited_analysis=True,
        scope_conclusion="范围内完成",
        requirement_points=[
            RequirementPoint("RP-001", "退出服务状态", ["soc"], "agent_inferred",
                             "状态处理属于 SOC", "完成", "已找到状态逻辑"),
            RequirementPoint("RP-002", "发送终止消息", ["mcu"], "pending",
                             "", "范围外未评估", "未选择 MCU",
                             candidate_locations=[CandidateLocation("mcu", "mcu_src/a.c", 1, 1)]),
        ],
    )
    doc = generate_document(item, analysis, output_root=td)
    content = open(doc.document_path, encoding="utf-8").read()
    self.assertIn("## 需求点完成情况", content)
    self.assertIn("范围内完成", content)
    self.assertIn("本次结论仅覆盖所选 Code Side", content)
    self.assertIn("责任侧来源", content)
    self.assertNotIn("mcu_src/a.c", content)


def test_summary_adds_phase7_fields_only_for_multi_side_results(self):
    data = build_summary_item(item, multi_side_analysis, document, {"supported": False})
    self.assertEqual(data["scope_conclusion"], "范围内完成")
    self.assertTrue(data["is_scope_limited_analysis"])
    self.assertNotIn("candidate_locations", json.dumps(data, ensure_ascii=False))
    old = build_summary_item(item, ordinary_analysis, document, {"supported": False})
    self.assertNotIn("analysis_scope", old)


def test_debug_bundle_writes_hints_and_candidates(self):
    bundle.write_multi_side_details([{
        "item_id": "1",
        "responsibility_hints": [{"fragment": "退出服务状态", "sides": ["soc"]}],
        "invalid_responsibility_hints": [{"fragment": "终止", "reason": "ambiguous_match"}],
        "candidate_locations": [{"side": "soc", "path": "soc_src/a.c", "line_start": 1, "line_end": 1}],
    }])
    self.assertTrue(os.path.exists(os.path.join(bundle.path, "multi_side_analysis.json")))
```

- [ ] **Step 2: Run tests and confirm missing output behavior**

Run: `python3 -m pytest -q tests/test_document_generator.py tests/test_summary_report.py tests/test_debug_bundle.py`

Expected: FAIL because phase-seven rendering and debug output methods are absent.

- [ ] **Step 3: Implement phase-seven presentation without changing ISSUE/default PRD rendering**

In `document_generator.py`:

- add `_render_requirement_points(analysis)` only when `analysis.multi_side_enabled` is true;
- insert `## 需求点完成情况` after `## 实现完成度`;
- render responsibility source labels as `禅道明确` / `用户提示` / `推断` / `待确认`;
- show `responsibility_reason` only for inferred responsibility;
- show `范围内完成` and the scope-limited disclaimer in the PRD when applicable;
- show a warning if `invalid_responsibility_hints` is non-empty;
- never render `candidate_locations` or count them in key evidence.

In `summary_report.py`, append keys only for `analysis.multi_side_enabled`:

```python
data.update({
    "analysis_scope": analysis.analysis_scope,
    "is_scope_limited_analysis": analysis.is_scope_limited_analysis,
    "scope_conclusion": analysis.scope_conclusion,
    "requirement_point_count": len(analysis.requirement_points),
    "requirement_point_status_counts": status_counts,
    "responsibility_source_counts": source_counts,
    "agent_inferred_responsibility_point_count": source_counts.get("agent_inferred", 0),
    "has_out_of_scope_requirement_points": status_counts.get("范围外未评估", 0) > 0,
    "invalid_responsibility_hint_count": len(analysis.invalid_responsibility_hints),
    "has_invalid_responsibility_hints": bool(analysis.invalid_responsibility_hints),
    "has_unconfirmed_requirement_points": any(
        point.status in ("无法判断", "责任侧待确认") for point in analysis.requirement_points
    ),
})
```

In `debug_bundle.py`, add `write_multi_side_details(items)` writing `multi_side_analysis.json` through the existing redaction path.

- [ ] **Step 4: Run output tests**

Run: `python3 -m pytest -q tests/test_document_generator.py tests/test_summary_report.py tests/test_debug_bundle.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add zentao_analyzer/document_generator.py zentao_analyzer/summary_report.py zentao_analyzer/debug_bundle.py tests/test_document_generator.py tests/test_summary_report.py tests/test_debug_bundle.py
git commit -m "feat: render multi-side requirement point outputs"
```

---

### Task 7: CLI Orchestration, Preflight Failures And Stdout Compatibility

**Files:**
- Modify: `zentao_analyzer/main.py`
- Create: `tests/test_main_phase7.py`
- Modify: `tests/test_main_phase4.py`
- Modify: `tests/test_main_phase5.py`

- [ ] **Step 1: Add failing CLI integration tests**

```python
# tests/test_main_phase7.py
def make_item(description="退出服务状态"):
    item = MagicMock()
    item.id = "1"
    item.type = "requirement"
    item.title = "终止服务"
    item.description = description
    item.status = "active"
    item.priority = "1"
    item.project = item.product = item.execution = ""
    item.assigned_to = item.created_by = item.created_date = ""
    return item


def run_main_code(argv, item=None, analysis=None):
    stdout = io.StringIO()
    with patch.object(main.ZentaoClient, "get_item", return_value=item or make_item()):
        if analysis is None:
            with patch.object(sys, "argv", ["zentao_analyzer.main.py"] + argv):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                    return main.main(), stdout.getvalue()
        with patch("zentao_analyzer.main.analyze", return_value=analysis):
            with patch.object(sys, "argv", ["zentao_analyzer.main.py"] + argv):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                    return main.main(), stdout.getvalue()


def run_success(argv, result):
    stdout = io.StringIO()
    with patch.object(main.ZentaoClient, "get_item", return_value=make_item()):
        with patch("zentao_analyzer.main.analyze", return_value=result) as mock_analyze:
            with patch.object(sys, "argv", ["zentao_analyzer.main.py"] + argv):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                    code = main.main()
    assert code == 0
    return json.loads(stdout.getvalue()), mock_analyze.call_args.kwargs


class TestMainPhase7(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.td = self.tmp.name
        os.makedirs(os.path.join(self.td, "mcu_src"))
        os.makedirs(os.path.join(self.td, "soc_src"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_ordinary_repo_output_has_no_phase7_fields(self):
        parsed = run_main(["--module", "requirement", "--id", "1", "--analyze", "--repo-path", self.td])
        self.assertNotIn("analysis_scope", parsed["analysis"][0])

    def test_explicit_multi_side_without_scope_fails_before_analyze_or_outputs(self):
        argv = ["--module", "requirement", "--id", "1", "--analyze", "--repo-path", self.td,
                "--code-side", "mcu=mcu_src", "--code-side", "soc=soc_src"]
        with patch("zentao_analyzer.main.analyze") as mock_analyze:
            code, stdout = run_main_code(argv)
        self.assertEqual(code, 3)
        mock_analyze.assert_not_called()
        self.assertEqual(stdout, "")

    def test_single_selected_side_sets_agent_cwd_and_emits_phase7_result(self):
        argv = ["--module", "requirement", "--id", "1", "--analyze", "--repo-path", self.td,
                "--code-side", "mcu=mcu_src", "--code-side", "soc=soc_src",
                "--analysis-scope", "soc", "--clues", "StopServiceMsg"]
        parsed, kwargs = run_success(argv, result=make_multi_side_analysis())
        self.assertEqual(kwargs["repo_path"], os.path.join(self.td, "soc_src"))
        self.assertEqual(parsed["analysis"][0]["scope_conclusion"], "范围内完成")
        self.assertEqual(parsed["analysis"][0]["conclusion"], "无法判断")

    def test_cross_side_without_explicit_code_clue_is_preflight_error(self):
        argv = ["--module", "requirement", "--id", "1", "--analyze", "--repo-path", self.td,
                "--code-side", "mcu=mcu_src", "--code-side", "soc=soc_src",
                "--analysis-scope", "mcu,soc", "--quiet"]
        with patch("zentao_analyzer.main.analyze") as mock_analyze:
            code, stdout = run_main_code(argv)
        self.assertEqual(code, 3)
        self.assertEqual(stdout, "")
        mock_analyze.assert_not_called()

    def test_hint_conflicting_with_explicit_zentao_side_is_preflight_error(self):
        item = make_item(description="MCU 发送终止服务信号")
        argv = ["--module", "requirement", "--id", "1", "--analyze", "--repo-path", self.td,
                "--code-side", "mcu=mcu_src", "--code-side", "soc=soc_src",
                "--analysis-scope", "mcu,soc",
                "--responsibility-hint", "MCU 发送终止服务信号=soc",
                "--clues", "StopServiceMsg", "--quiet"]
        with patch.object(main.ZentaoClient, "get_item", return_value=item):
            with patch("zentao_analyzer.main.analyze") as mock_analyze:
                code, stdout = run_main_code(argv)
        self.assertEqual(code, 3)
        self.assertEqual(stdout, "")
        mock_analyze.assert_not_called()

    def test_unreliable_point_split_writes_diagnostics_but_no_prd(self):
        result = make_multi_side_analysis()
        result.error = "无法从需求描述拆分可验证需求点"
        result.error_kind = "requirement_points_unresolved"
        result.requirement_points = []
        argv = ["--module", "requirement", "--id", "1", "--analyze", "--repo-path", self.td,
                "--code-side", "soc=soc_src", "--analysis-scope", "soc", "--quiet"]
        parsed, unused_kwargs = run_success(argv, result=result)
        self.assertEqual(parsed["documents"], [])
        self.assertTrue(parsed["debug_bundle"])
        self.assertTrue(os.path.exists(parsed["summary_report"]))
```

- [ ] **Step 2: Run the new CLI tests and verify failure**

Run: `python3 -m pytest -q tests/test_main_phase7.py`

Expected: FAIL because new CLI options and orchestration do not exist.

- [ ] **Step 3: Wire CLI arguments and preflight before creating outputs**

Add arguments:

```python
parser.add_argument("--code-sides-file", help="Code Side 逻辑名称到目录的 JSON 映射文件")
parser.add_argument("--code-side", action="append", help="单次运行 Code Side 映射，可重复：name=path")
parser.add_argument("--analysis-scope", help="本次允许分析的 Code Side 名称，逗号分隔")
parser.add_argument("--responsibility-hint", action="append", help="需求片段到责任侧的提示，可重复：fragment=side[,side]")
```

After item fetch and before `build_debug_bundle(enabled=runtime_config.debug_bundle_enabled, base_dir=runtime_config.debug_bundle_dir, module=args.module, run_id=run_id, include_code=runtime_config.debug_include_code)`:

```python
try:
    multi_side_context = build_multi_side_context(
        repo_path=args.repo_path,
        cli_code_sides=args.code_side or [],
        code_sides_file=args.code_sides_file or "",
        analysis_scope=args.analysis_scope or "",
        cli_responsibility_hints=args.responsibility_hint or [],
        clues_by_item=clues_by_item,
        item_id=args.id or "",
    )
    validate_cross_side_start_gate(multi_side_context, args.clues, args.paths, clues_by_item, items)
    validate_explicit_responsibility_conflicts(items, multi_side_context)
except MultiSideInputError as exc:
    print(f"[错误] 多侧分析输入无效: {exc}", file=sys.stderr)
    return 3
```

Structural preflight must execute before Debug Bundle/document/summary creation. For each item:

- implement `validate_explicit_responsibility_conflicts(items, context)` before the Agent call: when a Responsibility Hint fragment matches text that explicitly contains a configured Code Side logical name (case-insensitive, for example `MCU` / `mcu`) and the hint does not include that side, raise `responsibility_conflicts_with_zentao_explicit_side`; do not attempt to infer ownership from source files;
- pass `multi_side_context.analysis_root` to `analyze()` and set `AgentConfig.cwd` consistently;
- pass the context into `analyze()` only for feature items;
- if the result declares unresolved requirement-point splitting, write diagnostic debug/summary but do not call `generate_document()`;
- append phase-seven stdout fields only when `multi_side_context.enabled`;
- preserve the existing timeout/parse manual retry behavior; add new options to `_build_parse_retry_command()` only when they were present.

- [ ] **Step 4: Add semantic result handling tests**

Add cases proving:

- an Agent-returned unmatched responsibility hint appears in debug and PRD warning but does not stop document generation;
- a point with `status="责任侧待确认"` never yields top-level `conclusion="完成"`;
- candidates do not appear in stdout JSON;
- subset scope maps human `范围内完成` to stdout `conclusion="无法判断"` plus `scope_conclusion`.

- [ ] **Step 5: Run orchestration and regression tests**

Run:

```bash
python3 -m pytest -q tests/test_main_phase7.py tests/test_main_phase4.py tests/test_main_phase5.py tests/test_analyzer.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add zentao_analyzer/main.py tests/test_main_phase7.py tests/test_main_phase4.py tests/test_main_phase5.py
git commit -m "feat: orchestrate explicit multi-side analyses"
```

---

### Task 8: Skill And User Documentation

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`

- [ ] **Step 1: Update `SKILL.md` invocation and refusal rules**

Add terms and templates matching the confirmed interface:

```md
- **Code Side**: an explicitly mapped implementation side such as `mcu=mcu_src`.
- **Analysis Scope**: the explicitly selected Code Sides for this run.
- **Responsibility Hint**: an ownership hint for an existing Zentao-described requirement point; it is not requirement content.

Multi-side feature analysis:

```bash
python3 <ANALYZER_DIR>/main.py \
  --module requirement --id <zentao_id> --analyze \
  --repo-path <target_repo> \
  --code-side mcu=mcu_src --code-side soc=soc_src \
  --analysis-scope mcu,soc \
  --responsibility-hint '发送终止服务信号=mcu' \
  --clues 'StopServiceMsg' \
  --agent <claude|codex|opencode> --quiet
```
```

Add the natural-language extraction contract:

```text
代码侧: mcu=mcu_src, soc=soc_src；
分析范围: mcu,soc；
责任侧提示: "发送终止服务信号"=mcu；
代码线索: StopServiceMsg
```

Add the strict rejection statement: when the user supplies `补充需求内容: <内容>`, report that requirements must be updated in Zentao and do not start analysis or reinterpret it as a Code Clue.

- [ ] **Step 2: Update `README.md`**

Document:

- explicit multi-side activation only via `--code-side` or `--code-sides-file`;
- no automatic activation from `mcu_src/` / `soc_src/` directories;
- `--analysis-scope` and multi-side Code Clue gate;
- `--responsibility-hint` and clues-file JSON structure;
- PRD `需求点完成情况`, `责任侧待确认`, `范围外未评估`, human `范围内完成`;
- stdout compatibility (`scope_conclusion`, no new top-level conclusion enum);
- Debug Bundle `multi_side_analysis.json` and `candidate_locations`;
- requirement content originates only from Zentao.

- [ ] **Step 3: Check removed capability terminology**

Run:

```bash
rg -n "supplemental-requirement-context|补充需求内容" SKILL.md README.md
```

Expected: any match exists only in the explicit refusal/removed-capability explanation, not as a supported argument or invocation template.

- [ ] **Step 4: Commit**

```bash
git add SKILL.md README.md
git commit -m "docs: describe explicit multi-side requirement analysis"
```

---

### Task 9: Final Verification And Installed Skill Synchronization

**Files:**
- Verify: all phase-seven files and existing tests
- Synchronize after explicit approval, if deployment is required: `/home/ubuntu/.claude/skills/zentao-story-prd-analyzer/`

- [ ] **Step 1: Run the focused phase-seven suite**

Run:

```bash
python3 -m pytest -q \
  tests/test_multi_side.py \
  tests/test_analysis_result.py \
  tests/test_code_clues.py \
  tests/test_prompts.py \
  tests/test_analyzer.py \
  tests/test_document_generator.py \
  tests/test_summary_report.py \
  tests/test_debug_bundle.py \
  tests/test_main_phase7.py
```

Expected: PASS.

- [ ] **Step 2: Run the complete regression suite and diff hygiene check**

Run:

```bash
python3 -m pytest -q
git diff --check
```

Expected: all tests pass and `git diff --check` prints no errors.

- [ ] **Step 3: Run CLI smoke checks**

Run:

```bash
python3 main.py --help
python3 -m zentao_analyzer.main --help
```

Expected: both help outputs include `--code-side`, `--code-sides-file`, `--analysis-scope`, and `--responsibility-hint`.

- [ ] **Step 4: Synchronize an installed Claude skill only when the user requests deployment**

This repository is the implementation source. Do not write outside the workspace during implementation unless the user confirms synchronization. After approval, update only changed skill runtime/documentation files in the installed directory and verify them with `cmp` plus `python3 <installed>/main.py --help`.

- [ ] **Step 5: Commit verification/document completion changes if any**

```bash
git add README.md SKILL.md docs/superpowers/specs/2026-05-26-phase7-multi-side-scope-responsibility-design.md
git commit -m "docs: finalize phase seven multi-side analysis"
```

---

## Self-Review

- **Spec coverage:** Tasks 1/3/7 cover explicit Code Side activation, Analysis Scope, input conflicts and preflight failures; Tasks 2/4/5 cover Requirement Point, responsibility sources, evidence scope and candidates; Task 6 covers PRD/Summary/Debug/stdout presentation; Task 8 covers Skill invocation and removal of supplemental requirements; Task 9 covers compatibility and verification.
- **Compatibility:** The plan explicitly preserves default single-repository Prompt/output behavior and prevents the new human conclusion `范围内完成` from becoming a new top-level machine enum.
- **Safety:** Structural input/range failures occur before output creation; responsibility-pending candidates do not become evidence; Agent remains read/search-only; installed skill synchronization remains approval-gated.
- **Input timing:** Syntactic errors, scope violations, repeated-fragment conflicts and conflicts with an explicitly named configured Code Side in Zentao text are rejected before Agent invocation; ambiguity that exists only after Requirement Point decomposition is retained as an execution-time invalid-hint diagnostic.
