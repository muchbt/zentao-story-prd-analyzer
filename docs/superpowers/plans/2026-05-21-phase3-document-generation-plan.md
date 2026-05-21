# Phase 3: PRD/ISSUE Document Generation Implementation Plan

> **For agentic workers:** implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate local PRD/ISSUE Markdown documents and a machine-readable summary report from `ZentaoItem` and `AnalysisResult`.

**Architecture:** Add three focused modules (`document_generator.py`, `summary_report.py`, `writeback.py`) and refactor `main.py` orchestration so phase 3 consumes phase 2 results without adding LLM calls or Zentao write operations.

**Tech Stack:** Python 3.8+, dataclasses, json, pathlib/os, unittest.mock, tempfile

---

## File Map

| File | Responsibility | Status |
|------|----------------|--------|
| `document_generator.py` | Render PRD/ISSUE/diagnostic Markdown, sanitize filenames, choose output path | **Create** |
| `summary_report.py` | Build and write `docs/summary_report.json` | **Create** |
| `writeback.py` | Reserved Zentao writeback interface returning `not_implemented` | **Create** |
| `main.py` | Delegate phase 3 document and summary generation after analysis | **Modify** |
| `tests/test_document_generator.py` | PRD/ISSUE/diagnostic output, LLM understanding, filename sanitization | **Create** |
| `tests/test_summary_report.py` | Summary fields, counts, writeback status, sensitive data exclusion | **Create** |
| `tests/test_writeback.py` | Default `not_implemented` behavior | **Create** |
| `tests/test_main_phase3.py` | Mock analysis and verify generated docs + summary from CLI path | **Create or extend** |

---

## Task 1: Writeback Placeholder

**Files:**
- Create: `writeback.py`
- Test: `tests/test_writeback.py`

**Dependencies:** None

- [ ] **Step 1: Write the failing test**

```python
# tests/test_writeback.py
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from writeback import prepare_writeback_status, writeback_to_zentao


class TestWriteback(unittest.TestCase):
    def test_prepare_writeback_status_not_implemented(self):
        status = prepare_writeback_status()
        self.assertEqual(status["supported"], False)
        self.assertEqual(status["status"], "not_implemented")

    def test_writeback_to_zentao_does_not_write(self):
        result = writeback_to_zentao(item_id="1")
        self.assertEqual(result["supported"], False)
        self.assertEqual(result["status"], "not_implemented")
        self.assertIn("阶段三不实现", result["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_writeback -v`

Expected: `ModuleNotFoundError: No module named 'writeback'`

- [ ] **Step 3: Implement placeholder**

```python
# writeback.py
def prepare_writeback_status():
    return {
        "supported": False,
        "status": "not_implemented",
    }


def writeback_to_zentao(*args, **kwargs):
    return {
        "supported": False,
        "status": "not_implemented",
        "message": "阶段三不实现禅道回写",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_writeback -v`

Expected: all tests pass.

- [ ] **Step 5: Commit if appropriate**

Commit only source and test files for this task.

---

## Task 2: Document Generator

**Files:**
- Create: `document_generator.py`
- Test: `tests/test_document_generator.py`

**Dependencies:** `zentao_client.ZentaoItem`, `analysis_result.AnalysisResult`, `writeback.prepare_writeback_status`

- [ ] **Step 1: Write failing tests**

Cover these cases:

- `story` generates `docs/prd/PRD-story-1-safe_title.md`.
- `requirement` generates a PRD.
- `bug` generates `docs/issue/ISSUE-bug-2-safe_title.md`.
- Unknown type generates ISSUE and includes unknown-type notice.
- Error or insufficient evidence generates diagnostic document.
- Every document includes `LLM 理解摘要`.
- Filename sanitization preserves Chinese, English, numbers, `_`, `-`, replaces invalid characters, compresses `_`, and truncates long titles.

Suggested test skeleton:

```python
# tests/test_document_generator.py
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis_result import AnalysisResult
from document_generator import generate_document, sanitize_title
from zentao_client import ZentaoItem


class TestDocumentGenerator(unittest.TestCase):
    def test_story_generates_prd(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="1", type="story", title="新增 登录", description="用户可以登录", status="active")
            analysis = AnalysisResult(
                item_id="1",
                item_type="story",
                item_title="新增 登录",
                conclusion="部分完成",
                evidence=["src/auth.py: login exists"],
                gaps=["缺少异常提示"],
                recommendations=["补充错误提示"],
                verification=["验证错误密码"],
                priority="高",
                confidence="中",
            )
            doc = generate_document(item, analysis, output_root=td, generated_at="2026-05-21T10:00:00+08:00")
            self.assertEqual(doc.document_type, "PRD")
            self.assertIn(os.path.join("prd", "PRD-story-1-新增_登录.md"), doc.document_path)
            content = open(doc.document_path, encoding="utf-8").read()
            self.assertIn("# PRD: 新增 登录", content)
            self.assertIn("## LLM 理解摘要", content)
            self.assertIn("部分完成", content)

    def test_bug_generates_issue(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="2", type="bug", title="登录崩溃", description="点击登录崩溃")
            analysis = AnalysisResult(
                item_id="2",
                item_type="bug",
                item_title="登录崩溃",
                conclusion="部分定位",
                evidence=["src/auth.py"],
                suspected_causes=["空指针"],
                affected_scope=["登录模块"],
                recommendations=["增加空值检查"],
                verification=["复现登录"],
                priority="中",
                confidence="中",
            )
            doc = generate_document(item, analysis, output_root=td)
            self.assertEqual(doc.document_type, "ISSUE")
            content = open(doc.document_path, encoding="utf-8").read()
            self.assertIn("# ISSUE: 登录崩溃", content)
            self.assertIn("## 可能根因", content)

    def test_diagnostic_document_for_error(self):
        with tempfile.TemporaryDirectory() as td:
            item = ZentaoItem(id="3", type="requirement", title="T")
            analysis = AnalysisResult.from_error(item, "LLM 调用失败")
            doc = generate_document(item, analysis, output_root=td)
            self.assertTrue(doc.is_diagnostic)
            content = open(doc.document_path, encoding="utf-8").read()
            self.assertIn("诊断文档", content)
            self.assertIn("LLM 调用失败", content)

    def test_sanitize_title(self):
        self.assertEqual(sanitize_title("A/B C__中文!"), "A_B_C_中文")
        self.assertEqual(sanitize_title("!!!"), "untitled")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_document_generator -v`

Expected: `ModuleNotFoundError: No module named 'document_generator'`

- [ ] **Step 3: Implement minimal generator**

Implementation requirements:

- Define `DocumentResult` dataclass with fields from the SPEC.
- Implement `sanitize_title(title: str, max_len: int = 80) -> str`.
- Implement document type mapping:
  - PRD: `story`, `requirement`
  - ISSUE: `bug`, `ticket`, `feedback`, unknown
- Create directories using `os.makedirs(..., exist_ok=True)`.
- Render deterministic Markdown strings with sections from the SPEC.
- Render empty list values as `无`; empty strings as `未提供`.
- Generate LLM understanding:
  - If `analysis.output_md` is non-empty, use it.
  - Else build a short deterministic summary from structured fields.
  - If diagnostic, mention evidence/error limitations explicitly.
- Do not call LLM.
- Do not write summary.
- Do not include `analysis.raw_response`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_document_generator -v`

Expected: all tests pass.

- [ ] **Step 5: Commit if appropriate**

Commit only `document_generator.py` and `tests/test_document_generator.py`.

---

## Task 3: Summary Report

**Files:**
- Create: `summary_report.py`
- Test: `tests/test_summary_report.py`

**Dependencies:** `ZentaoItem`, `AnalysisResult`, `DocumentResult`

- [ ] **Step 1: Write failing tests**

Cover these cases:

- `build_summary_item()` emits all required fields.
- `write_summary_report()` writes valid JSON under `docs/summary_report.json` or `<output_root>/summary_report.json`.
- Count fields reflect list lengths.
- `writeback` status is preserved.
- Sensitive values and `raw_response` are not included.

Suggested test skeleton:

```python
# tests/test_summary_report.py
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis_result import AnalysisResult
from document_generator import DocumentResult
from summary_report import build_summary_item, write_summary_report
from zentao_client import ZentaoItem


class TestSummaryReport(unittest.TestCase):
    def test_build_summary_item(self):
        item = ZentaoItem(id="1", type="story", title="Title")
        analysis = AnalysisResult(
            item_id="1",
            item_type="story",
            item_title="Title",
            conclusion="完成",
            evidence=["a"],
            recommendations=["b"],
            verification=["c"],
            priority="高",
            confidence="高",
            raw_response="secret raw",
        )
        document = DocumentResult("1", "story", "Title", "PRD", "docs/prd/a.md", False)
        writeback = {"supported": False, "status": "not_implemented"}
        data = build_summary_item(item, analysis, document, writeback)
        self.assertEqual(data["item_id"], "1")
        self.assertEqual(data["document_type"], "PRD")
        self.assertEqual(data["evidence_count"], 1)
        self.assertNotIn("raw_response", json.dumps(data, ensure_ascii=False))
        self.assertNotIn("secret raw", json.dumps(data, ensure_ascii=False))

    def test_write_summary_report(self):
        with tempfile.TemporaryDirectory() as td:
            path = write_summary_report(
                [{"item_id": "1"}],
                output_root=td,
                generated_at="2026-05-21T10:00:00+08:00",
            )
            data = json.load(open(path, encoding="utf-8"))
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["prd_dir"], os.path.join(td, "prd"))
            self.assertEqual(data["issue_dir"], os.path.join(td, "issue"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_summary_report -v`

Expected: `ModuleNotFoundError: No module named 'summary_report'`

- [ ] **Step 3: Implement summary report**

Implementation requirements:

- `build_summary_item()` returns fields specified in the SPEC.
- `has_error` is `bool(analysis.error or document.error)`.
- `insufficient_evidence` uses `analysis.is_insufficient_evidence()`.
- Counts use lengths of `evidence`, `recommendations`, `verification`.
- `write_summary_report()` creates `output_root` if needed and writes UTF-8 JSON with `ensure_ascii=False`, `indent=2`.
- Do not include raw response, full Markdown content, full code snippets, tokens, passwords, or API keys.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_summary_report -v`

Expected: all tests pass.

- [ ] **Step 5: Commit if appropriate**

Commit only `summary_report.py` and `tests/test_summary_report.py`.

---

## Task 4: Main Flow Integration

**Files:**
- Modify: `main.py`
- Test: `tests/test_main_phase3.py` or equivalent unit coverage

**Dependencies:** `analyzer.analyze`, `document_generator.generate_document`, `summary_report`, `writeback`

- [ ] **Step 1: Write failing integration test**

Use mocks so the test does not call real Zentao or real LLM.

Test expectations:

- When `--analyze` runs, `main.py` calls `analyze()`.
- For each item, phase 3 generates a document.
- Summary report is written.
- stdout remains parseable JSON when no `--output` is supplied.
- Existing stage 1 behavior without `--analyze` still returns Zentao item JSON only.

Suggested approach:

- Patch `ZentaoClient.get_item()` to return a `ZentaoItem`.
- Patch `analyzer.analyze()` to return an `AnalysisResult`.
- Run `main.main()` with patched `sys.argv`.
- Use a temporary output root if adding an `--output-root` argument, or patch generator functions if keeping default `docs`.

- [ ] **Step 2: Decide output-root CLI support**

Recommended: add `--output-root`, default `docs`.

Reason:

- Tests can write to a temporary directory.
- Users can redirect generated docs without changing repo docs.
- Default still matches SPEC: `docs/prd`, `docs/issue`, `docs/summary_report.json`.

- [ ] **Step 3: Modify main.py**

Required behavior:

- Import `analyze`, `generate_document`, `build_summary_item`, `write_summary_report`, `prepare_writeback_status`.
- Add CLI arg:

```python
parser.add_argument("--output-root", default="docs", help="PRD/ISSUE 文档输出根目录")
```

- Keep stage 1 output unchanged when `--analyze` is not set.
- When `--analyze` is set:
  - Run analysis for each item.
  - Generate document for each item.
  - Build summary item for each item.
  - Write summary report once after all items.
  - Print a single parseable JSON object to stdout:

```json
{
  "module": "requirement",
  "count": 1,
  "items": [
    {
      "id": "5939",
      "type": "requirement",
      "title": "需求标题"
    }
  ],
  "documents": [
    {
      "item_id": "5939",
      "document_type": "PRD",
      "document_path": "docs/prd/PRD-requirement-5939-title.md",
      "is_diagnostic": false
    }
  ],
  "summary_report": "docs/summary_report.json"
}
```

- If `--output` is provided, write that final JSON object to the output file and print only a short status message to stderr.
- Do not print multiple independent JSON objects to stdout.

- [ ] **Step 4: Run focused tests**

Run:

```bash
python3 -m unittest tests.test_main_phase3 -v
python3 -m py_compile main.py
```

Expected: tests pass and `main.py` compiles.

- [ ] **Step 5: Commit if appropriate**

Commit only `main.py` and `tests/test_main_phase3.py`.

---

## Task 5: Full Verification

- [ ] **Step 1: Run phase 3 tests**

```bash
python3 -m unittest tests.test_writeback tests.test_document_generator tests.test_summary_report tests.test_main_phase3 -v
```

Expected: all phase 3 tests pass.

- [ ] **Step 2: Run full suite**

```bash
python3 -m unittest discover -v tests
```

Expected: existing phase 1 and phase 2 tests still pass.

- [ ] **Step 3: Verify CLI help**

```bash
python3 main.py --help
```

Expected: help includes `--output-root`.

- [ ] **Step 4: Verify stage 1 regression**

Use mocks in tests for automated verification. For manual verification, after a valid Zentao login:

```bash
python3 main.py --module requirement --id 5939 2>/dev/null | python3 -m json.tool
```

Expected: valid JSON with Zentao item fields and no document generation side effects.

- [ ] **Step 5: Verify phase 3 output manually with a safe mock or test fixture**

Run an integration test that uses temporary output root.

Expected files:

- `<tmp>/prd/PRD-requirement-5939-*.md`
- `<tmp>/summary_report.json`

- [ ] **Step 6: Commit final verification if appropriate**

Commit only if verification changed tracked files. Do not commit `__pycache__`.

---

## Self-Review Checklist

### Spec Coverage

- [x] PRD documents for `story` and `requirement`.
- [x] ISSUE documents for `bug`, `ticket`, `feedback`, and unknown types.
- [x] PRD/ISSUE split into `docs/prd` and `docs/issue`.
- [x] Filename rules implemented.
- [x] LLM 理解摘要 included in every document.
- [x] Diagnostic documents for errors and insufficient evidence.
- [x] `summary_report.json` with document paths, conclusion, confidence, error state, counts, and writeback status.
- [x] Summary excludes raw response, full code snippets, and sensitive credentials.
- [x] `writeback.py` exists and returns `not_implemented`.
- [x] No real Zentao write operation.

### Scope Guard

- [x] No second LLM call for document generation.
- [x] No code modification automation.
- [x] No Git commit automation beyond explicit repository workflow.
- [x] No Zentao create/update/close/resolve operation.

### Test Coverage

- [x] Deterministic unit tests for generator, summary, writeback.
- [x] Main-flow test with mocks, no real Zentao or LLM.
- [x] Full test suite required before completion.
