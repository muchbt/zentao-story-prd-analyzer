# Phase 2: Code Scanning & Agent Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build code scanning, LLM prompt generation, and structured analysis result modules to support feature/defect analysis from Zentao items.

**Architecture:** Split into 5 new focused modules (analysis_result, code_collector, prompts, llm_client, analyzer) plus refactored main.py. Each module has a single responsibility and well-defined interface.

**Tech Stack:** Python 3.8+, subprocess (rg/git grep), dataclasses, unittest.mock

---

## File Map

| File | Responsibility | Status |
|------|---------------|--------|
| `analysis_result.py` | `AnalysisResult` dataclass + JSON parsing/validation | **Create** |
| `code_collector.py` | Code context collection with rg→git grep→os.walk fallback | **Create** |
| `prompts.py` | Feature & defect prompt templates | **Create** |
| `llm_client.py` | LLM call wrapper (Codex real, others placeholder) | **Create** |
| `analyzer.py` | Orchestration: collect → prompt → LLM → result | **Create** |
| `main.py` | CLI args + orchestration only, delegate to analyzer | **Modify** |
| `tests/test_analysis_result.py` | AnalysisResult parsing, validation, evidence check | **Create** |
| `tests/test_code_collector.py` | Search fallback chain, budget limits, incremental | **Create** |
| `tests/test_prompts.py` | Template rendering, keyword substitution | **Create** |
| `tests/test_llm_client.py` | Mock LLM calls, timeout, non-JSON, sanitization | **Create** |
| `tests/test_analyzer.py` | Type routing, empty code short-circuit, full flow mock | **Create** |

---

## Task 1: AnalysisResult Data Structure

**Files:**
- Create: `analysis_result.py`
- Test: `tests/test_analysis_result.py`

**Dependencies:** `zentao_client.ZentaoItem`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_analysis_result.py
import dataclasses
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis_result import AnalysisResult
from zentao_client import ZentaoItem

class TestAnalysisResult(unittest.TestCase):
    def test_from_llm_json_full(self):
        item = ZentaoItem(id="1", type="story", title="T")
        data = {
            "conclusion": "完成",
            "evidence": ["file.c:foo()"],
            "gaps": [],
            "suspected_causes": [],
            "affected_scope": [],
            "recommendations": ["建议1"],
            "verification": ["验证1"],
            "priority": "高",
            "confidence": "高",
            "output_md": "# PRD",
        }
        result = AnalysisResult.from_llm_json(item, data, raw_response="raw")
        self.assertEqual(result.item_id, "1")
        self.assertEqual(result.conclusion, "完成")
        self.assertEqual(result.confidence, "高")
        self.assertEqual(result.evidence, ["file.c:foo()"])
        self.assertEqual(result.raw_response, "raw")

    def test_from_llm_json_missing_fields(self):
        item = ZentaoItem(id="2", type="bug", title="B")
        data = {"conclusion": "已定位"}  # missing most fields
        result = AnalysisResult.from_llm_json(item, data)
        self.assertEqual(result.evidence, [])
        self.assertEqual(result.gaps, [])
        self.assertEqual(result.confidence, "")

    def test_is_insufficient_evidence_empty_evidence(self):
        item = ZentaoItem(id="3", type="story", title="S")
        result = AnalysisResult.from_llm_json(item, {"conclusion": "完成", "evidence": []})
        self.assertTrue(result.is_insufficient_evidence())

    def test_is_insufficient_evidence_low_confidence(self):
        item = ZentaoItem(id="4", type="story", title="S")
        result = AnalysisResult.from_llm_json(item, {"conclusion": "无法判断", "confidence": "低", "evidence": []})
        self.assertTrue(result.is_insufficient_evidence())

    def test_from_error(self):
        item = ZentaoItem(id="5", type="story", title="S")
        result = AnalysisResult.from_error(item, "LLM timeout")
        self.assertEqual(result.error, "LLM timeout")
        self.assertTrue(result.is_insufficient_evidence())

if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/code/zentao-story-prd-analyzer && python3 -m unittest tests.test_analysis_result -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis_result'`

- [ ] **Step 3: Write minimal implementation**

```python
# analysis_result.py
import dataclasses
from typing import Any, Dict, List

from zentao_client import ZentaoItem


@dataclasses.dataclass
class AnalysisResult:
    item_id: str
    item_type: str
    item_title: str
    conclusion: str = ""
    evidence: List[str] = dataclasses.field(default_factory=list)
    gaps: List[str] = dataclasses.field(default_factory=list)
    suspected_causes: List[str] = dataclasses.field(default_factory=list)
    affected_scope: List[str] = dataclasses.field(default_factory=list)
    recommendations: List[str] = dataclasses.field(default_factory=list)
    verification: List[str] = dataclasses.field(default_factory=list)
    priority: str = ""
    confidence: str = ""
    output_md: str = ""
    error: str = ""
    raw_response: str = dataclasses.field(default="", repr=False)

    @classmethod
    def from_llm_json(cls, item: ZentaoItem, data: Dict[str, Any], raw_response: str = "") -> "AnalysisResult":
        if not isinstance(data, dict):
            data = {}
        return cls(
            item_id=item.id,
            item_type=item.type,
            item_title=item.title,
            conclusion=data.get("conclusion", ""),
            evidence=data.get("evidence", []),
            gaps=data.get("gaps", []),
            suspected_causes=data.get("suspected_causes", []),
            affected_scope=data.get("affected_scope", []),
            recommendations=data.get("recommendations", []),
            verification=data.get("verification", []),
            priority=data.get("priority", ""),
            confidence=data.get("confidence", ""),
            output_md=data.get("output_md", ""),
            raw_response=raw_response,
        )

    @classmethod
    def from_error(cls, item: ZentaoItem, error: str, raw_response: str = "") -> "AnalysisResult":
        return cls(
            item_id=item.id,
            item_type=item.type,
            item_title=item.title,
            conclusion="无法判断" if item.type in ("story", "requirement") else "无法定位",
            error=error,
            raw_response=raw_response,
        )

    def is_insufficient_evidence(self) -> bool:
        if self.error:
            return True
        if self.confidence == "低":
            return True
        if not self.evidence:
            return True
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ubuntu/code/zentao-story-prd-analyzer && python3 -m unittest tests.test_analysis_result -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit (if in a git repo)**

```bash
if git rev-parse --git-dir > /dev/null 2>&1; then
  git add analysis_result.py tests/test_analysis_result.py
  git commit -m "feat(phase2): add AnalysisResult data structure with parsing and evidence check"
else
  echo "Not a git repository, skipping commit"
fi
```

---

## Task 2: Code Collector with Search Fallback Chain

**Files:**
- Create: `code_collector.py`
- Test: `tests/test_code_collector.py`

**Dependencies:** None (uses subprocess, os)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_code_collector.py
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from code_collector import collect

class TestCodeCollector(unittest.TestCase):
    def _create_repo(self, files_content):
        td = tempfile.mkdtemp()
        for path, content in files_content.items():
            full = os.path.join(td, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
        return td

    def test_os_walk_fallback_collects_files(self):
        td = self._create_repo({
            "src/main.c": "int main() { return 0; }\n",
            "README.md": "# readme\n",
        })
        snippets = collect(td, keywords=["main"], max_files=10, max_lines_per_file=100)
        paths = [s["path"] for s in snippets]
        self.assertTrue(any("main.c" in p for p in paths))
        self.assertFalse(any("README" in p for p in paths))

    def test_os_walk_no_match_returns_empty(self):
        td = self._create_repo({"src/foo.c": "void bar() {}\n"})
        snippets = collect(td, keywords=["nonexistent"])
        self.assertEqual(snippets, [])

    def test_max_files_limit(self):
        td = self._create_repo({f"src/f{i}.c": f"int x{i};\n" for i in range(10)})
        snippets = collect(td, keywords=["int"], max_files=3)
        self.assertLessEqual(len(snippets), 3)

    def test_max_lines_per_file(self):
        td = self._create_repo({"src/big.c": "line\n" * 500})
        snippets = collect(td, keywords=["line"], max_lines_per_file=10)
        self.assertLessEqual(len(snippets[0]["content"].splitlines()), 10)

    def test_modified_files_restricts_search(self):
        td = self._create_repo({
            "src/a.c": "int alpha;\n",
            "src/b.c": "int beta;\n",
        })
        snippets = collect(td, keywords=["int"], modified_files=[os.path.join(td, "src", "a.c")])
        paths = [s["path"] for s in snippets]
        self.assertTrue(any("a.c" in p for p in paths))
        self.assertFalse(any("b.c" in p for p in paths))

if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/code/zentao-story-prd-analyzer && python3 -m unittest tests.test_code_collector -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'code_collector'`

- [ ] **Step 3: Write minimal implementation**

```python
# code_collector.py
import os
import subprocess
from typing import Any, Dict, List, Optional


def _find_executable(name: str) -> bool:
    try:
        subprocess.run([name, "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _rg_search(repo_path: str, keywords: List[str]) -> List[str]:
    matched = set()
    for kw in keywords:
        try:
            result = subprocess.run(
                ["rg", "--files-with-matches", "-i", kw, repo_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        matched.add(line)
            elif result.stderr:
                print(f"[rg stderr] {result.stderr.strip()}", file=sys.stderr)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            break
    return list(matched)


def _git_grep_search(repo_path: str, keywords: List[str]) -> List[str]:
    matched = set()
    for kw in keywords:
        try:
            result = subprocess.run(
                ["git", "-C", repo_path, "grep", "-l", "-i", kw],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        matched.add(os.path.join(repo_path, line))
            elif result.stderr:
                print(f"[git grep stderr] {result.stderr.strip()}", file=sys.stderr)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            break
    return list(matched)


def _os_walk_search(repo_path: str, keywords: List[str]) -> List[str]:
    matched = []
    exts = (".c", ".cpp", ".h", ".hpp", ".sh", ".bat", ".py")
    build_files = {"Makefile", "CMakeLists.txt"}
    for root, _, files in os.walk(repo_path):
        for f in files:
            if f.endswith(exts) or f in build_files:
                path = os.path.join(root, f)
                if not keywords:
                    matched.append(path)
                    continue
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                        if any(kw.lower() in content.lower() for kw in keywords):
                            matched.append(path)
                except:
                    continue
    return matched


def _read_snippets(
    paths: List[str],
    max_lines_per_file: int,
    max_total_tokens: int,
) -> List[Dict[str, Any]]:
    snippets = []
    token_budget = max_total_tokens
    TOKEN_ESTIMATE_RATIO = 4  # chars per token
    truncated = False

    for path in paths:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                content_lines = lines[:max_lines_per_file]
                content = "".join(content_lines)
                estimated_tokens = len(content) // TOKEN_ESTIMATE_RATIO
                if estimated_tokens > token_budget:
                    # Truncate to fit budget
                    allowed_chars = token_budget * TOKEN_ESTIMATE_RATIO
                    content = content[:allowed_chars]
                    if not content:
                        truncated = True
                        break
                    content_lines = content.splitlines(keepends=True)
                    estimated_tokens = len(content) // TOKEN_ESTIMATE_RATIO
                    truncated = True

                token_budget -= estimated_tokens
                snippets.append({
                    "path": path,
                    "content": content,
                    "line_start": 1,
                    "line_end": len(content_lines),
                })

                if token_budget <= 0:
                    truncated = True
                    break
        except:
            continue

    if truncated and snippets:
        snippets[-1]["content"] += "\n[代码上下文已截断，仅展示部分相关文件]\n"
    return snippets


def collect(
    repo_path: str,
    keywords: List[str],
    modified_files: Optional[List[str]] = None,
    max_files: int = 50,
    max_lines_per_file: int = 200,
    max_total_tokens: int = 8000,
) -> List[Dict[str, Any]]:
    """
    Collect code context with fallback: rg -> git grep -> os.walk.
    Returns: [{"path": str, "content": str, "line_start": int, "line_end": int}]
    """
    if modified_files:
        candidates = [p for p in modified_files if os.path.exists(p)]
    else:
        candidates = []
        if _find_executable("rg"):
            candidates = _rg_search(repo_path, keywords)
        if not candidates and os.path.isdir(os.path.join(repo_path, ".git")):
            candidates = _git_grep_search(repo_path, keywords)
        if not candidates:
            candidates = _os_walk_search(repo_path, keywords)

    candidates = candidates[:max_files]
    return _read_snippets(candidates, max_lines_per_file, max_total_tokens)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ubuntu/code/zentao-story-prd-analyzer && python3 -m unittest tests.test_code_collector -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit (if in a git repo)**

```bash
if git rev-parse --git-dir > /dev/null 2>&1; then
  git add code_collector.py tests/test_code_collector.py
  git commit -m "feat(phase2): add code collector with rg->git grep->os.walk fallback"
else
  echo "Not a git repository, skipping commit"
fi
```

---

## Task 3: Prompt Templates

**Files:**
- Create: `prompts.py`
- Test: `tests/test_prompts.py`

**Dependencies:** `zentao_client.ZentaoItem`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_prompts.py
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompts import build_feature_prompt, build_defect_prompt
from zentao_client import ZentaoItem

class TestPrompts(unittest.TestCase):
    def test_feature_prompt_contains_fields(self):
        item = ZentaoItem(id="1", type="story", title="Add feature", description="Desc", status="active")
        snippets = [{"path": "src/main.c", "content": "int foo() {}", "line_start": 1, "line_end": 1}]
        prompt = build_feature_prompt(item, snippets)
        self.assertIn("Add feature", prompt)
        self.assertIn("Desc", prompt)
        self.assertIn("src/main.c", prompt)
        self.assertIn("完成|部分完成|未完成|无法判断", prompt)
        self.assertIn("禁止编造", prompt)

    def test_defect_prompt_contains_fields(self):
        item = ZentaoItem(id="2", type="bug", title="Crash bug", description="Crashes", status="active")
        snippets = [{"path": "src/bug.c", "content": "void bad() {}", "line_start": 1, "line_end": 1}]
        prompt = build_defect_prompt(item, snippets)
        self.assertIn("Crash bug", prompt)
        self.assertIn("Crashes", prompt)
        self.assertIn("src/bug.c", prompt)
        self.assertIn("已定位|部分定位|无法定位", prompt)
        self.assertIn("禁止编造", prompt)

    def test_feature_vs_defect_distinct(self):
        item = ZentaoItem(id="1", type="story", title="T")
        snippets = [{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]
        p1 = build_feature_prompt(item, snippets)
        p2 = build_defect_prompt(item, snippets)
        self.assertNotEqual(p1, p2)
        self.assertIn("功能实现完成度", p1)
        self.assertIn("可能根因", p2)

if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/code/zentao-story-prd-analyzer && python3 -m unittest tests.test_prompts -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prompts'`

- [ ] **Step 3: Write minimal implementation**

```python
# prompts.py
from zentao_client import ZentaoItem


_FEATURE_TEMPLATE = """你是高级代码分析 Agent。请根据以下禅道条目和代码上下文，判断功能实现完成度。

【禅道条目】
ID: {id}
标题: {title}
描述: {description}
类型: {type}
状态: {status}

【代码上下文】
{code_context}

【任务要求】
1. 对比条目描述与代码实现，判断功能是否完成。
2. 输出严格 JSON，不要 Markdown 代码块，不要额外解释。
3. JSON Schema:
{{
  "conclusion": "完成|部分完成|未完成|无法判断",
  "evidence": ["文件路径:函数名 已实现的功能说明", "..."],
  "gaps": ["未实现点1", "..."],
  "suspected_causes": [],
  "affected_scope": [],
  "recommendations": ["修改建议1", "..."],
  "verification": ["验证建议1", "..."],
  "priority": "高|中|低",
  "confidence": "高|中|低",
  "output_md": ""
}}

4. 如果代码上下文不足以判断，请设置 conclusion="无法判断"、confidence="低"，并在 evidence 中说明"相关代码证据不足"。禁止编造不存在的证据。
5. confidence="高" 意味着你有直接代码证据支持结论；confidence="中" 意味着有间接证据或推断；confidence="低" 意味着证据不足。
"""

_DEFECT_TEMPLATE = """你是高级代码分析 Agent。请根据以下禅道缺陷条目和代码上下文，分析可能根因和影响范围。

【禅道条目】
ID: {id}
标题: {title}
描述: {description}
类型: {type}
状态: {status}

【代码上下文】
{code_context}

【任务要求】
1. 分析缺陷描述对应的代码区域，找出可能根因。
2. 输出严格 JSON，不要 Markdown 代码块，不要额外解释。
3. JSON Schema:
{{
  "conclusion": "已定位|部分定位|无法定位",
  "evidence": ["文件路径:函数名 与缺陷相关的代码说明", "..."],
  "gaps": [],
  "suspected_causes": ["可能根因1", "..."],
  "affected_scope": ["文件A", "模块B"],
  "recommendations": ["修复方向1", "..."],
  "verification": ["复现步骤或验证建议", "..."],
  "priority": "高|中|低",
  "confidence": "高|中|低",
  "output_md": ""
}}

4. 如果代码上下文不足以分析，请设置 conclusion="无法定位"、confidence="低"，并在 suspected_causes 中说明"相关代码证据不足"。禁止编造不存在的根因。
5. confidence="高" 意味着你有直接代码证据支持结论；confidence="中" 意味着有间接证据或推断；confidence="低" 意味着证据不足。
"""


def _format_code_context(snippets):
    if not snippets:
        return "[未提供代码上下文]"
    parts = []
    for s in snippets:
        parts.append(f"--- 文件: {s['path']} (行 {s['line_start']}-{s['line_end']}) ---\n{s['content']}")
    return "\n\n".join(parts)


def build_feature_prompt(item: ZentaoItem, code_snippets) -> str:
    return _FEATURE_TEMPLATE.format(
        id=item.id,
        title=item.title,
        description=item.description,
        type=item.type,
        status=item.status,
        code_context=_format_code_context(code_snippets),
    )


def build_defect_prompt(item: ZentaoItem, code_snippets) -> str:
    return _DEFECT_TEMPLATE.format(
        id=item.id,
        title=item.title,
        description=item.description,
        type=item.type,
        status=item.status,
        code_context=_format_code_context(code_snippets),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ubuntu/code/zentao-story-prd-analyzer && python3 -m unittest tests.test_prompts -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit (if in a git repo)**

```bash
if git rev-parse --git-dir > /dev/null 2>&1; then
  git add prompts.py tests/test_prompts.py
  git commit -m "feat(phase2): add feature and defect prompt templates"
else
  echo "Not a git repository, skipping commit"
fi
```

---

## Task 4: LLM Client

**Files:**
- Create: `llm_client.py`
- Test: `tests/test_llm_client.py`

**Dependencies:** None (uses openai when available)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm_client.py
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_client import call_llm

class TestLLMClient(unittest.TestCase):
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_codex_returns_json(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"conclusion":"完成"}'

        with patch("openai.ChatCompletion.create", return_value=mock_response):
            result = call_llm("test prompt", agent="codex")
        self.assertEqual(result["conclusion"], "完成")

    def test_claude_placeholder(self):
        result = call_llm("test", agent="claude")
        self.assertIn("error", result)
        self.assertIn("未实现", result["error"])

    def test_opencode_placeholder(self):
        result = call_llm("test", agent="opencode")
        self.assertIn("error", result)
        self.assertIn("未实现", result["error"])

    def test_unknown_agent(self):
        result = call_llm("test", agent="unknown")
        self.assertIn("error", result)
        self.assertIn("未识别", result["error"])

    def test_non_json_response(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not json"

        with patch("openai.ChatCompletion.create", return_value=mock_response):
            result = call_llm("test", agent="codex")
        self.assertIn("error", result)
        self.assertEqual(result["raw"], "not json")

if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/code/zentao-story-prd-analyzer && python3 -m unittest tests.test_llm_client -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'llm_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# llm_client.py
import json
import os
from typing import Any, Dict


def call_llm(prompt: str, agent: str = "codex") -> Dict[str, Any]:
    """
    调用 LLM，返回原始 JSON 字典。
    若失败，返回 {"error": "错误描述", "raw": "原始响应文本"}。
    """
    agent_lower = agent.lower()

    if agent_lower == "codex":
        try:
            import openai
            openai.api_key = os.environ.get("OPENAI_API_KEY")
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            text = response.choices[0].message.content
        except Exception as exc:
            return {"error": f"LLM 调用失败: {exc}", "raw": ""}
    elif agent_lower == "claude":
        return {"error": "Claude 适配尚未实现，请配置 OPENAI_API_KEY 使用 Codex", "raw": ""}
    elif agent_lower == "opencode":
        return {"error": "OpenCode 适配尚未实现，请配置 OPENAI_API_KEY 使用 Codex", "raw": ""}
    else:
        return {"error": f"未识别 agent: {agent}", "raw": ""}

    # Try to extract JSON from Markdown code block if wrapped
    cleaned = text.strip()
    if cleaned.startswith("```json") and "```" in cleaned:
        cleaned = cleaned[len("```json"):].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    elif cleaned.startswith("```") and "```" in cleaned:
        cleaned = cleaned[len("```"):].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "LLM 返回非 JSON", "raw": text}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ubuntu/code/zentao-story-prd-analyzer && python3 -m unittest tests.test_llm_client -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit (if in a git repo)**

```bash
if git rev-parse --git-dir > /dev/null 2>&1; then
  git add llm_client.py tests/test_llm_client.py
  git commit -m "feat(phase2): add LLM client with Codex support and Claude/OpenCode placeholders"
else
  echo "Not a git repository, skipping commit"
fi
```

---

## Task 5: Analyzer Orchestrator

**Files:**
- Create: `analyzer.py`
- Test: `tests/test_analyzer.py`

**Dependencies:** `code_collector`, `prompts`, `llm_client`, `analysis_result`, `zentao_client.ZentaoItem`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_analyzer.py
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer import analyze
from zentao_client import ZentaoItem

class TestAnalyzer(unittest.TestCase):
    def _create_repo(self):
        td = tempfile.mkdtemp()
        with open(os.path.join(td, "main.c"), "w") as f:
            f.write("int main() { return 0; }\n")
        return td

    def test_empty_code_returns_insufficient(self):
        item = ZentaoItem(id="1", type="story", title="T")
        with patch("code_collector.collect", return_value=[]):
            result = analyze(item, ".", agent="codex")
        self.assertTrue(result.is_insufficient_evidence())
        self.assertEqual(result.conclusion, "无法判断")

    def test_feature_type_uses_feature_prompt(self):
        item = ZentaoItem(id="2", type="story", title="Feature")
        with patch("code_collector.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("llm_client.call_llm", return_value={"conclusion": "完成", "evidence": ["a.c"], "confidence": "高"}) as mock_llm:
                analyze(item, ".", agent="codex")
        prompt = mock_llm.call_args[0][0]
        self.assertIn("功能实现完成度", prompt)

    def test_bug_type_uses_defect_prompt(self):
        item = ZentaoItem(id="3", type="bug", title="Bug")
        with patch("code_collector.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("llm_client.call_llm", return_value={"conclusion": "已定位", "evidence": ["a.c"], "confidence": "高"}) as mock_llm:
                analyze(item, ".", agent="codex")
        prompt = mock_llm.call_args[0][0]
        self.assertIn("可能根因", prompt)

    def test_llm_error_returns_error_result(self):
        item = ZentaoItem(id="4", type="story", title="S")
        with patch("code_collector.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("llm_client.call_llm", return_value={"error": "timeout", "raw": ""}):
                result = analyze(item, ".", agent="codex")
        self.assertEqual(result.error, "timeout")
        self.assertTrue(result.is_insufficient_evidence())

    def test_force_insufficient_when_evidence_empty(self):
        item = ZentaoItem(id="5", type="story", title="S")
        with patch("code_collector.collect", return_value=[{"path": "a.c", "content": "x", "line_start": 1, "line_end": 1}]):
            with patch("llm_client.call_llm", return_value={"conclusion": "完成", "evidence": [], "confidence": "高"}):
                result = analyze(item, ".", agent="codex")
        self.assertTrue(result.is_insufficient_evidence())
        self.assertEqual(result.conclusion, "无法判断")

if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ubuntu/code/zentao-story-prd-analyzer && python3 -m unittest tests.test_analyzer -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analyzer'`

- [ ] **Step 3: Write minimal implementation**

```python
# analyzer.py
from typing import Any, Dict, List, Optional

from zentao_client import ZentaoItem
from code_collector import collect
from prompts import build_feature_prompt, build_defect_prompt
from llm_client import call_llm
from analysis_result import AnalysisResult


def analyze(
    item: ZentaoItem,
    repo_path: str,
    agent: str = "codex",
    modified_files: Optional[List[str]] = None,
    max_files: int = 50,
    max_lines_per_file: int = 200,
    max_total_tokens: int = 8000,
) -> AnalysisResult:
    """
    完整分析流程：收集代码 -> 选择模板 -> 调用 LLM -> 解析结果 -> 证据不足检查。
    """
    code_snippets = collect(
        repo_path,
        keywords=item.keywords,
        modified_files=modified_files,
        max_files=max_files,
        max_lines_per_file=max_lines_per_file,
        max_total_tokens=max_total_tokens,
    )

    if not code_snippets:
        return AnalysisResult.from_error(item, "未找到相关代码证据")

    if item.type in ("story", "requirement"):
        prompt = build_feature_prompt(item, code_snippets)
    else:
        prompt = build_defect_prompt(item, code_snippets)

    llm_data = call_llm(prompt, agent=agent)

    if "error" in llm_data:
        return AnalysisResult.from_error(item, llm_data["error"], raw_response=llm_data.get("raw", ""))

    result = AnalysisResult.from_llm_json(item, llm_data, raw_response=llm_data.get("raw", ""))

    # Post-hoc evidence check
    if result.is_insufficient_evidence():
        result.conclusion = "无法判断" if item.type in ("story", "requirement") else "无法定位"
        result.confidence = "低"
        msg = "分析依据不足：未找到与条目直接相关的代码证据。"
        if item.type in ("story", "requirement"):
            if msg not in result.evidence:
                result.evidence.append(msg)
        else:
            if msg not in result.suspected_causes:
                result.suspected_causes.append(msg)

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ubuntu/code/zentao-story-prd-analyzer && python3 -m unittest tests.test_analyzer -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit (if in a git repo)**

```bash
if git rev-parse --git-dir > /dev/null 2>&1; then
  git add analyzer.py tests/test_analyzer.py
  git commit -m "feat(phase2): add analyzer orchestrator with type routing and evidence checks"
else
  echo "Not a git repository, skipping commit"
fi
```

---

## Task 6: Refactor main.py to Use New Modules

**Files:**
- Modify: `main.py`
- Test: `tests/test_main.py` (optional integration test)

- [ ] **Step 1: Replace old analysis logic with analyzer import**

In `main.py`, remove these functions and their calls:
- `get_modified_files()` → keep but simplify (already fixed in phase 1)
- `collect_code()` → remove
- `generate_code_summary()` → remove
- `generate_prompt()` → remove
- `call_llm()` → remove
- `create_prd_file()` → keep for now (phase 3 will refactor)

Replace the `--analyze` block with:

```python
from analyzer import analyze

# In main():
if args.analyze:
    analysis_results = []
    for item in items:
        result = analyze(
            item,
            repo_path=args.repo_path,
            agent=args.agent,
            modified_files=modified_files if args.incremental else None,
        )
        analysis_results.append({
            "item_id": result.item_id,
            "item_type": result.item_type,
            "conclusion": result.conclusion,
            "evidence": result.evidence,
            "gaps": result.gaps,
            "suspected_causes": result.suspected_causes,
            "affected_scope": result.affected_scope,
            "recommendations": result.recommendations,
            "verification": result.verification,
            "priority": result.priority,
            "confidence": result.confidence,
            "error": result.error,
        })

    combined_output = {
        "module": args.module,
        "count": len(items),
        "items": [
            {
                "id": item.id,
                "type": item.type,
                "title": item.title,
                "description": item.description,
                "status": item.status,
                "priority": item.priority,
                "project": item.project,
                "product": item.product,
                "execution": item.execution,
                "assigned_to": item.assigned_to,
                "created_by": item.created_by,
                "created_date": item.created_date,
                "keywords": item.keywords,
            }
            for item in items
        ],
        "analysis": analysis_results,
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(combined_output, f, ensure_ascii=False, indent=2)
        print(f"分析结果已写入: {args.output}", file=sys.stderr)
    else:
        print(json.dumps(combined_output, ensure_ascii=False, indent=2))
```

- [ ] **Step 2: Remove unused imports**

Remove: `re`, `ThreadPoolExecutor` (if no longer used), `subprocess` (if `get_modified_files` moved).
Actually keep `subprocess` and `re` if still needed by other functions.

- [ ] **Step 3: Verify main.py compiles and existing tests pass**

Run: `cd /home/ubuntu/code/zentao-story-prd-analyzer && python3 -m py_compile main.py`
Run: `python3 -m unittest discover -v tests`
Expected: All 18 existing tests still PASS + new tests PASS

- [ ] **Step 4: Commit (if in a git repo)**

```bash
if git rev-parse --git-dir > /dev/null 2>&1; then
  git add main.py
  git commit -m "refactor(phase2): main.py delegates analysis to analyzer module"
else
  echo "Not a git repository, skipping commit"
fi
```

---

## Task 7: Integration Verification

- [ ] **Step 1: Run full test suite**

Run: `cd /home/ubuntu/code/zentao-story-prd-analyzer && python3 -m unittest discover -v tests`
Expected: 18 (phase 1) + 5 (analysis_result) + 5 (code_collector) + 3 (prompts) + 5 (llm_client) + 5 (analyzer) = **41 tests ALL PASS**

- [ ] **Step 2: Verify CLI help works**

Run: `python3 main.py --help`
Expected: Help text displays without error

- [ ] **Step 3: Verify stage 1 still works (regression check)**

Run: `python3 main.py --module requirement --id 5939 2>/dev/null | python3 -m json.tool`
Expected: Valid JSON with item fields (stage 1 unchanged)

- [ ] **Step 4: Final commit (if in a git repo)**

```bash
if git rev-parse --git-dir > /dev/null 2>&1; then
  git add -A
  git commit -m "test(phase2): verify full test suite passes, 41 tests OK"
else
  echo "Not a git repository, skipping commit"
fi
```

---

## Self-Review Checklist

### Spec Coverage
- [x] `AnalysisResult` data structure with JSON parsing → Task 1
- [x] Code collector with rg→git grep→os.walk fallback → Task 2
- [x] Prompt templates for feature/defect → Task 3
- [x] LLM client with Codex + placeholders → Task 4
- [x] Analyzer orchestrator with type routing → Task 5
- [x] Evidence check (empty evidence → insufficient) → Tasks 1, 5
- [x] main.py refactor → Task 6
- [x] Budget limits (max_files, max_lines, max_tokens) → Task 2
- [x] Incremental mode (modified_files) → Task 2

### Placeholder Scan
- [x] No TBD, TODO, "implement later", "fill in details" in plan
- [x] Every step contains actual code or exact commands
- [x] No "similar to Task N" references

### Type Consistency
- [x] `AnalysisResult` fields match between `analysis_result.py` and `analyzer.py`
- [x] `ZentaoItem` type strings consistent (`story`, `requirement`, `bug`, etc.)
- [x] `call_llm` return type (`Dict[str, Any]`) consistent across `llm_client.py` and `analyzer.py`

