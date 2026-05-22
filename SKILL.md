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
   # Or equivalently:
   # cd <ANALYZER_DIR> && python3 -m zentao_analyzer.main --help
   ```

3. Verify `zentao` CLI is available inside the same sandbox/session:

   ```bash
   command -v zentao
   ```

4. Verify Zentao authentication is available inside the sandbox/session. Do not assume host login state is visible.

   Check authentication status first:

   ```bash
   # Check current profile (shows logged-in user with * marker)
   zentao profile

   # Verify token is still valid (returns user info or auth error)
   zentao user --format json --machine-readable
   ```

   If `zentao user` returns `code: 1004` or "Token 已失效", the session is expired and the user must re-login.

   Do not use `zentao whoami` — this command does not exist.

   Alternatively, set authentication via environment variables:

   ```bash
   export ZENTAO_CONFIG_FILE="$HOME/.config/zentao/zentao.json"
   ```

   ```bash
   export ZENTAO_SERVER="https://zentao.example.com/"
   export ZENTAO_TOKEN="<token>"
   ```

5. The `--agent` parameter selects the LLM backend. **It must match the host Agent CLI environment** — do not hardcode or guess. Detect as follows:
   - If the host is **Claude Code** (claude CLI): use `--agent claude`
   - If the host is **OpenCode**: use `--agent opencode`
   - If the host is **Codex** or a custom OpenAI-compatible endpoint: use `--agent codex` with `OPENAI_API_KEY` and `OPENAI_MODEL` set
   - If unsure, check the `LLM_AGENT` environment variable. If not set, default to `claude` when `claude` CLI is available, otherwise `codex`.
   Never use `--agent codex` when running inside Claude Code — it will fail with "openai 模块未安装".

Never print tokens, passwords, API keys, Authorization headers, or full login commands containing secrets in final user-facing output.

## Invocation Rules

- Default to full analysis with `--analyze`.
- Default `--repo-path` to the Target Repository current working directory.
- Run the command with the Target Repository as the process working directory, while calling `<ANALYZER_DIR>/main.py` by absolute path.
- Always set `--agent-timeout 900` (15 minutes) or higher. LLM analysis typically takes 3–10 minutes. Shorter timeouts cause incomplete results. If a timeout occurs, the analyzer prints a retry command with doubled timeout; use it.
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
  --agent-timeout 900 \
  --quiet
```

Single defect item:

```bash
python3 <ANALYZER_DIR>/main.py \
  --module bug \
  --id <zentao_id> \
  --analyze \
  --repo-path <target_repo> \
  --agent-timeout 900 \
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
  --agent-timeout 900 \
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
  --agent-timeout 900 \
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
  --agent-timeout 900 \
  --quiet
```

## Failure Handling

If `zentao` is missing, tell the user the sandbox/session needs `zentao` CLI in `PATH`.

If authentication fails (exit code 2, or stderr contains "Token 已失效"/"认证失败"/"未登录"/"auth"/"unauthorized"):

1. Read `ZENTAO_SERVER` from the environment or extract the server URL from the error context.
2. Prompt the user with a clear message and login command template:
   > 禅道认证失败（Token 已失效或未登录）。请在终端手动登录后继续：
   > `! zentao login -s <server_url> -u <username> -p <password>`
   >
   > 登录成功后，我将重新执行分析。
   Replace `<server_url>` with the actual `ZENTAO_SERVER` value if available; otherwise leave as a placeholder.
3. Wait for the user to confirm successful login.
4. Retry the original analysis command (same invocation, without `--login` flags — the zentao CLI stores the session after login).
5. If the retry also fails with an auth error, report the full error and stop — do not retry again.

Do not store, log, or echo the user's password or token. Do not hardcode server URLs.

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
