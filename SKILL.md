---
name: zentao-story-prd-analyzer
description: Use when the user wants to analyze a Zentao story, requirement, bug, task, ticket, or feedback against the current code repository and generate PRD/ISSUE documents, completion status, defect-cause analysis, code evidence, summary reports, or debug bundles.
---

# Zentao Story PRD Analyzer

This skill is a thin Agent CLI wrapper around the bundled analyzer CLI. It does not reimplement analysis logic. Use it to run the analyzer from a target code repository and produce PRD/ISSUE documents with traceable code evidence.

## When to Use

Use this skill when the user asks to:

- Analyze a Zentao `story` or `requirement` for implementation completion in the current repository.
- Analyze a Zentao `bug`, `ticket`, or `feedback` for suspected causes and affected code.
- Generate PRD/ISSUE Markdown documents, `summary_report.json`, or a debug bundle from a Zentao item.
- Provide code clues such as keywords, paths, symbols, or a clues JSON file for repository analysis.

Do not use this skill for Zentao-only lookup, status checks, field inspection, or comments. Prefer the official Zentao skill or direct `zentao` CLI for those cases.

## Terms

- **Target Repository**: the repository being analyzed. Default to the Agent CLI current working directory unless the user provides a repository path.
- **Analyzer Directory**: the installed skill directory containing this `SKILL.md`, `main.py`, and `zentao_analyzer/`.
- **Zentao Item**: the input item fetched by `--module` and `--id`, or by list filters.
- **PRD Document / ISSUE Document**: generated Markdown outputs under the target repository's `docs/` tree by default.

## Preconditions

Before running the analyzer:

1. Run from the Target Repository, or set `--repo-path` to the explicit Target Repository path.
2. Verify the bundled analyzer is available:

   ```bash
   python3 <ANALYZER_DIR>/main.py --help
   ```

3. Verify `zentao` CLI is available inside the same sandbox/session:

   ```bash
   command -v zentao
   ```

4. Verify Zentao authentication is available inside the sandbox/session. Do not assume host login state is visible.

   Prefer one of:

   ```bash
   export ZENTAO_CONFIG_FILE="$HOME/.config/zentao/zentao.json"
   ```

   ```bash
   export ZENTAO_SERVER="https://zentao.example.com/"
   export ZENTAO_TOKEN="<token>"
   ```

5. If using OpenAI/Codex backend, ensure `OPENAI_API_KEY` and `OPENAI_MODEL` are set. If using Claude backend, ensure `claude` CLI is available.

Never print tokens, passwords, API keys, Authorization headers, or full login commands containing secrets in final user-facing output.

## Invocation Rules

- Default to full analysis with `--analyze`.
- Default `--repo-path` to the Target Repository current working directory.
- Run the command with the Target Repository as the process working directory, while calling `<ANALYZER_DIR>/main.py` by absolute path.
- Do not parse or fabricate Zentao item content outside the analyzer. If fetching fails, stop and report the failure.
- Do not use `--module issue`; ISSUE is an output document type. Use real Zentao modules such as `story`, `requirement`, `bug`, `task`, `ticket`, or `feedback`.
- Add `--quiet` when stdout should remain machine-readable JSON.
- Add `--output-root <TARGET_REPO>/docs` if the working directory is not the Target Repository.

## Command Templates

Single feature item:

```bash
python3 <ANALYZER_DIR>/main.py \
  --module requirement \
  --id <zentao_id> \
  --analyze \
  --repo-path <target_repo> \
  --quiet
```

Single defect item:

```bash
python3 <ANALYZER_DIR>/main.py \
  --module bug \
  --id <zentao_id> \
  --analyze \
  --repo-path <target_repo> \
  --quiet
```

With explicit code clues:

```bash
python3 <ANALYZER_DIR>/main.py \
  --module requirement \
  --id <zentao_id> \
  --analyze \
  --repo-path <target_repo> \
  --keywords "keyword1,keyword2" \
  --paths "src/module,include/module" \
  --symbols "FunctionName,ClassName" \
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
  --quiet
```

Claude backend:

```bash
python3 <ANALYZER_DIR>/main.py \
  --module requirement \
  --id <zentao_id> \
  --analyze \
  --repo-path <target_repo> \
  --agent claude \
  --quiet
```

OpenAI/Codex backend:

```bash
python3 <ANALYZER_DIR>/main.py \
  --module requirement \
  --id <zentao_id> \
  --analyze \
  --repo-path <target_repo> \
  --agent codex \
  --model "$OPENAI_MODEL" \
  --quiet
```

## Failure Handling

If `zentao` is missing, tell the user the sandbox/session needs `zentao` CLI in `PATH`.

If authentication fails, tell the user to provide a readable `ZENTAO_CONFIG_FILE` or sandbox-visible `ZENTAO_SERVER` plus `ZENTAO_TOKEN` / `ZENTAO_USER` / `ZENTAO_PASSWORD`.

If network access to Zentao is blocked, report that the analyzer cannot fetch the Zentao Item from inside the current Agent CLI environment.

If LLM/Agent execution fails, report the analyzer error and point to the debug bundle path if one was created.

Never continue by inventing Zentao content, code evidence, completion status, defect cause, PRD, or ISSUE output.

## Output Interpretation

The analyzer prints final JSON to stdout unless `--output` is provided. Important fields:

- `items`: fetched Zentao Items.
- `analysis`: completion or defect-cause Analysis Results.
- `documents`: generated PRD/ISSUE Markdown paths.
- `summary_report`: machine-readable summary path.
- `debug_bundle`: diagnostic bundle path.

For user-facing summaries, report generated document paths, summary path, debug bundle path, and any fetch/auth/network/Agent errors. Keep raw JSON concise unless the user asks for it.
