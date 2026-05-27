---
name: zentao-story-prd-analyzer
description: Use when the user wants to analyze a Zentao story, requirement, bug, task, ticket, or feedback against the current code repository and generate PRD/ISSUE documents, completion status, defect-cause analysis, code evidence, summary reports, or debug bundles.
---

# Zentao Story PRD Analyzer

This skill is a thin Agent CLI wrapper around the bundled analyzer CLI. It runs the analyzer from a Target Repository and produces PRD/ISSUE documents with traceable code evidence.

## When to Use

Use this skill to analyze Zentao `story`, `requirement`, `bug`, `ticket`, or `feedback` items against the current repository. Do not use it for Zentao-only lookup, status checks, field inspection, or comments; prefer the official Zentao skill or direct `zentao` CLI for those cases.

## Terms

- **Target Repository**: the repository being analyzed. Default to the Agent CLI current working directory unless the user provides a repository path.
- **Analyzer Directory**: the installed skill directory containing this `SKILL.md`, `main.py`, and `zentao_analyzer/`.
- **Search Hint**: text passed via `--clues` or `clues_file.clues` to guide Agent repository search.
- **Seed Path**: a repository file passed via `--paths` or `clues_file.paths`; it is preloaded as starting context. Directories are not valid Seed Paths.

## Preconditions

1. Run from the Target Repository, or set `--repo-path` to the explicit Target Repository path.
2. Verify the bundled analyzer is available:

   ```bash
   python3 <ANALYZER_DIR>/main.py --help
   ```

3. Verify `zentao` CLI is available and a profile is selected when needed:

   ```bash
   command -v zentao
   zentao profile
   ```

   Do not use `zentao user` as an authentication check: it reads the user module rather than identifying the current session and may require unrelated permission. The analyzer's requested item fetch validates authentication and reports authentication failures.

4. Select the Agent backend to match the host CLI:
   - Claude Code: `--agent claude`
   - Codex: `--agent codex`
   - OpenCode: `--agent opencode`

Never print tokens, passwords, API keys, Authorization headers, or full login commands containing secrets.

## Invocation Rules

- Default to full analysis with `--analyze`.
- Default `--repo-path` to the Target Repository current working directory.
- Run the command with the Target Repository as the process working directory, while calling `<ANALYZER_DIR>/main.py` by absolute path.
- Always set `--agent` to the host CLI when invoked as a skill.
- Add `--quiet` when stdout should remain machine-readable JSON.
- Add `--output-root <TARGET_REPO>/docs` if the working directory is not the Target Repository.
- Do not use `--module issue`; ISSUE is an output document type. Use real Zentao modules such as `story`, `requirement`, `bug`, `task`, `ticket`, or `feedback`.
- When the user says "需求" or "requirement", use `--module requirement`. When the user says "缺陷", "Bug" or "bug", use `--module bug`. When the user says "Story" or "故事", use `--module story`. Do not map "需求" to the `story` module.
- Do not use removed options `--keywords`, `--symbols`, `--incremental`, or `--last-commit`.
- If providing clues, use `--clues` for Search Hints and `--paths` only for repository files.

The Agent CLI subprocess is read/search-only. It must return structured JSON to the analyzer and must not write Target Repository files, debug bundles, PRD/ISSUE documents, summaries, explicit output files, or log files. Only the analyzer process writes generated outputs.

## Command Templates

Single feature item (Zentao ID):

```bash
python3 <ANALYZER_DIR>/main.py \
  --module requirement \
  --id <zentao_id> \
  --analyze \
  --repo-path <target_repo> \
  --agent <claude|codex|opencode> \
  --agent-timeout 900 \
  --quiet
```

Provided Requirement (user-submitted requirement text):

```bash
python3 <ANALYZER_DIR>/main.py \
  --module requirement \
  --id <user_provided_id> \
  --title "Confirmed Requirement Title" \
  --requirement-file /tmp/requirement.txt \
  --analyze \
  --repo-path <target_repo> \
  --agent <claude|codex|opencode> \
  --agent-timeout 900 \
  --quiet
```

With Search Hints and Seed Paths:

```bash
python3 <ANALYZER_DIR>/main.py \
  --module requirement \
  --id <zentao_id> \
  --analyze \
  --repo-path <target_repo> \
  --agent <claude|codex|opencode> \
  --clues "keyword,SymbolName,src/module" \
  --paths "src/module/entry.c" \
  --agent-timeout 900 \
  --quiet
```

Batch/list analysis:

```bash
python3 <ANALYZER_DIR>/main.py \
  --module requirement \
  --project <project_id> \
  --status open \
  --limit 10 \
  --analyze \
  --repo-path <target_repo> \
  --agent <claude|codex|opencode> \
  --agent-timeout 900 \
  --quiet
```

## Provided Requirement Mode

When a user provides complete requirement text instead of a Zentao ID:

1. Accept the full requirement text from the user.
2. If the user has not provided a requirement ID, ask for one. The ID is only used for output file naming and does not trigger a Zentao read.
3. Recommend or confirm the requirement title with the user before proceeding.
4. Write the text to a temporary file, then invoke the analyzer with `--requirement-file`, `--id`, and `--title`.

Rules:
- `--requirement-file` is only valid with `--module requirement` or `--module story`.
- `--requirement-file` requires both `--id` and `--title`.
- In Provided Requirement mode, the analyzer does **not** call `ZentaoClient.get_item()`, `list_items()`, or login. The ID does not trigger a Zentao lookup or content merge.
- The requirement source is labeled `provided_requirement` in the output and PRD.
- Logs and stderr do not echo the full requirement text.

## PRD Content Boundaries

The PRD separates three types of formal content:

| Content Type | Source & Purpose | Disallowed |
| --- | --- | --- |
| Requirement Interpretation | Summarize scope, terms, rules, scenarios, matrix, and flow from the Requirement Source | Writing code search results or unconfirmed speculation as requirement facts |
| Code Impact Analysis | Identify related existing modules, files, and symbols; locations must pass validation | Counting "related locations" as completion evidence |
| Completion Assessment | Derive completion, gaps, and confidence from Requirement Points and valid Code Evidence only | Supporting formal conclusions with ungrounded explanations or Implementation Recommendations |

Items with `source: "code_context"` display a label: "代码侧候选上下文，不构成需求定义". Items with `source: "insufficient"` display: "原始需求未提供足够信息".

Implementation Recommendations (section 5) are clearly advisory and do not represent existing implementations.

When `requirement_interpretation` or `code_impact` is missing or structurally invalid but `requirement_points` and Completion Assessment are valid, the PRD is still generated. The affected sections display "分析结果未提供有效内容" and the Summary Report and Debug Bundle record the degradation.

## Clues File

```json
{
  "5939": {
    "clues": ["callback", "CallBackMode", "src/ecall"],
    "paths": ["src/ecall/xcall.c"]
  }
}
```

## Failure Handling

If `zentao` is missing or authentication fails, report the analyzer error and stop.

If LLM/Agent execution fails, report the analyzer error and point to the debug bundle path if one was created. If an `analysis[]` item marks a failure as `retryable: true` with `retry_reason: "agent_response_parse_failed"`, state that the Agent returned an unparseable structured response for that Zentao Item and ask the user whether to rerun the analyzer command. Do not rerun automatically. In batch analysis, offer the analyzer's item-specific `--id <zentao_id>` retry command only for failed items; do not suggest rerunning successfully analyzed items. Present only the analyzer-provided redacted retry command; never reconstruct credential, login, or other sensitive parameters in host output. An item-specific rerun must not reuse a previous combined-output `--output` file path. `has_retryable_failure` is the top-level shortcut for detecting whether such items exist.

After an analyzer failure, do not fetch the Zentao Item independently, inspect the Target Repository independently, or produce a replacement analysis/PRD/ISSUE in the host Agent. Never invent or substitute Zentao content, code evidence, completion status, defect cause, PRD, or ISSUE output.

If the user explicitly confirms a rerun and it succeeds, treat the latest generated PRD/ISSUE and summary as the primary output. The earlier failure remains reviewable through its Debug Bundle.

## Output Interpretation

The analyzer prints final JSON to stdout unless `--output` is provided. Important fields:

- `items`: fetched Zentao Items or provided requirement item.
- `analysis`: completion or defect-cause Analysis Results.
  - `requirement_source`: `"zentao"` or `"provided_requirement"`.
  - `requirement_interpretation`: structured interpretation (scope, terms, rules, scenarios, matrix, flow, pending confirmations) when present.
  - `code_impact`: related code locations and impact notes when present.
  - `requirement_points`: per-point completion assessment.
  - `rich_content_issues`: list of issues when interpretation or code impact is missing or invalid.
- `documents`: generated PRD/ISSUE Markdown paths.
- `summary_report`: machine-readable summary path.
- `debug_bundle`: diagnostic bundle path.
- `analysis[].retryable` / `analysis[].retry_reason`: whether an item's failed analysis can be retried by explicit user choice and why.
- `has_retryable_failure`: whether any analyzed item has such a retryable failure.
