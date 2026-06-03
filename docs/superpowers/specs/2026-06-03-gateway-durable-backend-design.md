# Gateway Durable Backend Design

**Date**: 2026-06-03
**Status**: accepted for implementation

## Context

`zentao-story-prd-analyzer` currently owns the full formal analysis workflow: it fetches or accepts a Feature Item or Defect Item, builds business prompts, validates structured Analysis Results, checks code evidence, writes PRD/ISSUE documents, writes Summary Reports, and writes Debug Bundles. Its `AgentClient` directly invokes `claude`, `codex`, or `opencode` CLI subprocesses and normalizes their final text into analyzer-owned JSON.

`acp-agent-gateway` now provides a reusable TypeScript ACP Coding Agent gateway with a language-neutral JSON CLI, verified `opencode`, `claude`, and `codex` ACP adapters, permission policies, metadata-only events, and durable Managed Session lifecycle commands. The analyzer should consume this gateway without moving Zentao, PRD, evidence, or document-generation concepts into the gateway repository.

## Decision

Add a new analyzer backend selected by `--agent gateway`. This backend invokes ACP Agent Gateway through its JSON CLI and uses one durable Managed Session per analyzed Zentao Item.

The analyzer remains the Business Consumer:

- It owns Zentao access, Provided Requirement handling, business prompts, Analysis Result parsing, evidence validation, document generation, summaries, and debug bundles.
- Gateway owns ACP adapter invocation, model selection, permission policy enforcement, metadata events, durable Session References, and Agent Turn execution.
- The Python analyzer repository remains separate from the Gateway repository.

## CLI Shape

Analyzer CLI:

```bash
python3 main.py --module requirement --id 5939 \
  --analyze \
  --repo soc=/path/to/soc \
  --repo mcu=/path/to/mcu \
  --agent gateway \
  --gateway-agent opencode \
  --model opencode-go/qwen3.6-plus
```

Semantics:

- `--agent gateway` selects the analyzer Gateway backend.
- `--gateway-agent opencode|claude|codex` is the ACP Agent Gateway Agent Name.
- `--model` remains the model value and is passed into the Gateway request JSON.
- Existing `--claude-command`, `--codex-command`, `--opencode-command`, `--claude-prompt-via`, and `--claude-extra-arg` do not affect Gateway adapter launch. Gateway resolves adapters through its controlled registry.
- Direct analyzer CLI default detection remains unchanged: `claude -> codex -> opencode`. Gateway is enabled only when `--agent gateway` is explicit.

Gateway executable resolution:

1. Use `ACP_AGENT_GATEWAY_BIN` when set.
2. Otherwise resolve `acp-agent-gateway` from `PATH`.
3. If no executable is available, return a configuration error.
4. Command strings are split with `shlex.split`; never use `shell=True`.
5. The analyzer does not install, build, or download Gateway or ACP adapters.

## Session Lifecycle

Each analyzed Zentao Item uses its own durable Managed Session.

For the first and only automatic Agent Turn in an item analysis, the Gateway backend calls:

```bash
acp-agent-gateway start-session \
  --agent <gateway-agent> \
  --cwd <workspace> \
  --input <request-json>
```

The request JSON includes:

```json
{
  "apiVersion": "v1",
  "prompt": "<business prompt>",
  "model": "<optional model>",
  "permissionPolicy": "best-effort-read-only",
  "timeoutMs": 900000,
  "idleTimeoutMs": 300000
}
```

Rules:

- Default `permissionPolicy` is `best-effort-read-only` to preserve current analyzer behavior.
- `strict-read-only` is a later compatibility item because Gateway Bubblewrap replaces `/tmp` with tmpfs, while analyzer multi-repository `RoleWorkspace` currently uses `tempfile.TemporaryDirectory()`.
- The analyzer does not automatically send a second `prompt` turn to repair malformed JSON.
- Successful sessions are retained by default. The analyzer records the reported Session Reference for diagnostics and possible follow-up; it does not automatically `close` or `forget`.
- If Gateway reports a `sessionRef` on failure, the analyzer records it as reported diagnostic data but does not assume it is recoverable.

## Multi-Repository Workspace

Existing role-based multi-repository behavior must be preserved.

For multi-repository analysis, the analyzer continues to create a `RoleWorkspace` that exposes each Target Repository under its Repository Role name with symlinks. The Gateway `--cwd` is the role workspace path.

The analyzer still validates evidence against the original Target Repository Set, not against Gateway internals:

- Prompt repository context lists role workspace search paths and original repository paths.
- Agent evidence must remain role-qualified in multi-repository mode.
- Summary Reports and Debug Bundles record repository roles, original paths, and evidence status.
- PRD/ISSUE documents do not include Gateway Session References.

## Output Handling

Gateway stdout contains the final Gateway JSON result and is the only source of Agent final text.

When stdout result is completed:

- `stdout.text` becomes the analyzer raw Agent response.
- Existing analyzer JSON extraction and repair logic parses the business Analysis Result.
- `sessionRef` is recorded in Summary Report and Debug Bundle.

Gateway stderr contains metadata-only JSONL events:

- Events are written to analyzer run logs and Debug Bundle diagnostics.
- Events are not mixed into `raw_response`.
- Events do not participate in business JSON parsing or evidence validation.

## Error Mapping

The analyzer keeps its existing `error_kind` vocabulary and records Gateway-specific diagnostics separately.

Mapping:

```text
adapter_not_found, unsupported_agent, unsupported_model,
unsupported_permission_policy, sandbox_unavailable, invalid_request
=> config

timeout, idle_timeout, cancelled
=> timeout

protocol_error, adapter_spawn_failed, internal_error,
unsupported_session_recovery, incompatible_session,
session_cleanup_failed, invalid_session_state
=> runtime
```

The analyzer also records:

- `gateway_error_code`
- `gateway_error`
- `gateway_session_ref` when reported
- `gateway_events` in debug/log output

If Gateway stdout is not valid Gateway JSON, or the Gateway process fails without stdout JSON, the analyzer returns `error_kind=runtime` and records `gateway_transport_error`.

## Skill Triggering

`SKILL.md` remains a thin wrapper around the analyzer CLI. It must not call Gateway directly and bypass analyzer-owned validation or document generation.

When the analyzer is invoked through `SKILL.md`, the preferred formal-analysis path is:

```bash
python3 <ANALYZER_DIR>/main.py ... \
  --agent gateway \
  --gateway-agent <host-agent>
```

Rules:

- Codex host: `--gateway-agent codex`
- Claude Code host: `--gateway-agent claude`
- OpenCode host: `--gateway-agent opencode`
- User-provided `--gateway-agent` wins.
- The Skill does not infer Gateway Agent Name from `PATH`.
- If Gateway is unavailable, the Skill may fall back to the legacy host CLI backend.

Direct analyzer CLI defaults remain unchanged so existing scripts and local workflows do not gain a new Gateway installation prerequisite.

## Testing Boundary

Python tests use a fake Gateway CLI and do not call real Gateway adapters or models.

Required coverage:

- `--agent gateway --gateway-agent <name>` command and request JSON assembly.
- Multi-repository `RoleWorkspace` passed as Gateway `--cwd`.
- Completed Gateway stdout `text` parsed through existing business JSON extraction.
- Failed Gateway stdout mapped to analyzer `error_kind` while preserving `gateway_error_code`.
- Gateway stderr JSONL events written to logs/debug bundle and excluded from raw response.
- `sessionRef` recorded in Summary Report and Debug Bundle, not PRD/ISSUE documents.

Real Gateway runs remain optional smoke tests.
