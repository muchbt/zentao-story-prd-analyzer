---
name: zentao-story-prd-analyzer
description: Use when the user wants to analyze a Zentao story, requirement, bug, task, ticket, or feedback against the current code repository and generate PRD/ISSUE documents, completion status, defect-cause analysis, code evidence, summary reports, or debug bundles.
---

# Zentao Story PRD Analyzer

Thin wrapper around the bundled analyzer CLI. It analyzes Zentao items against a Target Repository Set and writes PRD/ISSUE documents, summaries, and debug bundles with traceable code evidence.

## Use

Use for Zentao `story`, `requirement`, `bug`, `task`, `ticket`, or `feedback` analysis. Do not use for Zentao-only lookup, status checks, field inspection, or comments; use the Zentao CLI/skill for those.

Terms:
- **Target Repository Set**: one or more repositories analyzed for the same item.
- **Repository Role**: role name such as `soc`, `mcu`, `app`, or `bootloader`.
- **Analyzer Directory**: installed directory containing `main.py` and `zentao_analyzer/`.
- **Search Hint**: `--clues` or `clues_file.clues`.
- **Seed Path**: repository file passed by `--paths` or `clues_file.paths`; directories are invalid.
- **Protocol Hint**: `--protocol-hint` or `clues_file.items.<id>.protocol_hints`; types: `cmd_id`, `msg`, `field`, `text`.

## Preconditions

- Run from the single target repository, or pass repeated `--repo <role>=<path>` for multi-repo analysis.
- Check the analyzer with `python3 <ANALYZER_DIR>/main.py --help`.
- Check `zentao` with `command -v zentao` and, when needed, `zentao profile`. Do not use `zentao user` as an auth check; the analyzer item fetch validates auth.
- Prefer Gateway: `--agent gateway --gateway-agent <opencode|claude|codex>`. Legacy direct backends are `--agent claude`, `--agent codex`, and `--agent opencode`.
- Never print tokens, passwords, API keys, Authorization headers, or login commands containing secrets.

## Invocation

Base command:

```bash
python3 <ANALYZER_DIR>/main.py --module <module> --id <zentao_id> --analyze \
  --repo-path <target_repo> --agent gateway --gateway-agent <opencode|claude|codex> \
  --agent-timeout 900 --quiet
```

Rules:
- Call `<ANALYZER_DIR>/main.py` by absolute path and run with the Target Repository as cwd. Add `--output-root <TARGET_REPO>/docs` if cwd differs.
- Default to `--analyze`; add `--quiet` when stdout must stay machine-readable JSON.
- Prefer `--repo`; keep `--repo-path` only for compatible single-repo calls.
- Use real Zentao modules only: `story`, `requirement`, `bug`, `task`, `ticket`, `feedback`. Never use `--module issue`; ISSUE is an output type.
- Map user language carefully: "需求"/`requirement` => `--module requirement`; "缺陷"/`bug` => `--module bug`; "Story"/"故事" => `--module story`.
- Do not use removed options: `--keywords`, `--symbols`, `--incremental`, `--last-commit`.
- Use `--clues` for Search Hints and `--paths` only for repository files. Multi-repo Seed Paths need `role=relative/path.c` or a Structured Clue File.
- Use `--protocol-hint roles:type=value`, e.g. `--protocol-hint soc,mcu:cmd_id=0x1234`; ask before guessing hint type, role, or item ownership.
- For batches, replace `--id` with list filters such as `--project <id> --status open --limit 10`.
- If Gateway is unavailable (`gateway_transport_error` or `gateway_error`), fall back to the matching legacy host CLI backend.

The Agent subprocess is read/search-only. It must return structured JSON to the analyzer and must not write Target Repository files, debug bundles, PRD/ISSUE documents, summaries, explicit output files, or logs. Only the analyzer writes outputs.

## Provided Requirement

When the user provides requirement text instead of a Zentao ID:
- Ask for an ID if missing; it is only for output naming and must not trigger a Zentao lookup.
- Confirm the title, write the text to a temp file, and call with `--requirement-file`, `--id`, and `--title`.
- `--requirement-file` is valid only with `--module requirement` or `--module story`, and requires both `--id` and `--title`.
- The analyzer must not call `ZentaoClient.get_item()`, `list_items()`, or login; output source is `provided_requirement`.
- Logs and stderr must not echo the full requirement text.

Example:

```bash
python3 <ANALYZER_DIR>/main.py --module requirement --id <provided_id> \
  --title "Confirmed Requirement Title" --requirement-file /tmp/requirement.txt \
  --analyze --repo-path <target_repo> --agent gateway --gateway-agent <agent> --quiet
```

## PRD Boundaries

Keep these content sources separate:
- **Requirement Interpretation**: scope, terms, rules, scenarios, matrix, and flow from the Requirement Source. Do not treat code search or speculation as requirement facts.
- **Code Impact Analysis**: related modules/files/symbols with validated locations. Related locations are not completion evidence by themselves.
- **Completion Assessment**: completion, gaps, and confidence from Requirement Points plus valid Code Evidence only; recommendations are advisory.

Labels: `source: "code_context"` means "代码侧候选上下文，不构成需求定义"; `source: "insufficient"` means "原始需求未提供足够信息". If `requirement_interpretation` or `code_impact` is missing/invalid but Requirement Points are valid, still generate the PRD, show "分析结果未提供有效内容", and record the degradation in summary/debug bundle.

## Clue Files

Single-repo compact form:

```json
{"5939":{"clues":["callback","CallBackMode"],"paths":["src/ecall/xcall.c"]}}
```

Multi-repo Structured Clue File:

```json
{
  "repositories": {"soc": "../soc", "mcu": "../mcu"},
  "items": {
    "5939": {
      "primary_role": "soc",
      "clues": ["callback mode"],
      "protocol_hints": [{"roles": ["soc","mcu"], "type": "cmd_id", "value": "0x1234"}],
      "paths": {"soc": ["src/send.c"], "mcu": ["src/recv.c"]}
    }
  }
}
```

Protocol Hints guide search and protocol-trace reporting; they are not Requirement Sources or Code Evidence.

## Failure Handling

- If `zentao` is missing or authentication fails, report the analyzer error and stop.
- If LLM/Agent execution fails, report the analyzer error and debug bundle path if present.
- For `analysis[].retryable == true` with `retry_reason == "agent_response_parse_failed"`, say the Agent returned an unparseable structured response and ask before rerun. Do not rerun automatically.
- In batch analysis, offer only the analyzer-provided redacted retry command for failed items; do not suggest rerunning successful items.
- Never reconstruct credential/login/sensitive parameters in host output. A retry must not reuse a previous combined-output `--output` path. Use `has_retryable_failure` as the top-level shortcut.
- After analyzer failure, do not independently fetch Zentao content, inspect the repository, or produce replacement analysis/PRD/ISSUE in the host Agent. Never invent or substitute Zentao content, code evidence, completion status, defect cause, PRD, or ISSUE output.
- If the user confirms rerun and it succeeds, treat the latest generated PRD/ISSUE and summary as primary; earlier failure remains in its Debug Bundle.

## Output

The analyzer prints JSON to stdout unless `--output` is provided. Key fields:
- `items`: fetched Zentao items or provided requirement item.
- `analysis`: result objects including `requirement_source`, `requirement_interpretation`, `code_impact`, `requirement_points`, `rich_content_issues`, `retryable`, and `retry_reason`.
- `documents`: generated PRD/ISSUE Markdown paths.
- `summary_report`: machine-readable summary path.
- `debug_bundle`: diagnostic bundle path.
- `has_retryable_failure`: whether any item has a retryable parse failure.
