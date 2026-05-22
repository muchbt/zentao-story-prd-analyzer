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

3. Verify `zentao` CLI is available and authenticated:

   ```bash
   command -v zentao
   zentao profile
   zentao user --format json --machine-readable
   ```

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
- Do not use removed options `--keywords`, `--symbols`, `--incremental`, or `--last-commit`.
- If providing clues, use `--clues` for Search Hints and `--paths` only for repository files.

The analyzer uses Agent CLI permissions intended to reduce interactive prompts. The Agent must not modify, create, or delete Target Repository source, config, test, or build files. Allowed writes are limited to debug bundle, PRD/ISSUE documents, summary, explicit `--output`, and explicit `--log-file`.

## Command Templates

Single feature item:

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

If `zentao` is missing or authentication fails, report the analyzer error and stop. If LLM/Agent execution fails, report the analyzer error and point to the debug bundle path if one was created. Never invent Zentao content, code evidence, completion status, defect cause, PRD, or ISSUE output.

## Output Interpretation

The analyzer prints final JSON to stdout unless `--output` is provided. Important fields:

- `items`: fetched Zentao Items.
- `analysis`: completion or defect-cause Analysis Results.
- `documents`: generated PRD/ISSUE Markdown paths.
- `summary_report`: machine-readable summary path.
- `debug_bundle`: diagnostic bundle path.
