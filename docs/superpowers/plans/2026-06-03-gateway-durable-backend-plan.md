# Gateway Durable Backend Implementation Plan

**Goal:** Add a Gateway-backed Agent backend that uses ACP Agent Gateway durable sessions while preserving analyzer-owned Zentao handling, business analysis contracts, multi-repository role semantics, PRD/ISSUE generation, Summary Reports, and Debug Bundles.

**Architecture:** Introduce a `gateway` backend behind the existing analyzer AgentClient boundary. The backend invokes `acp-agent-gateway start-session` through the JSON CLI once per analyzed item, records Gateway metadata, and returns the same `AgentResult` shape expected by `analyzer.py`.

**Tech Stack:** Python 3.8+, argparse, dataclasses, json, shlex, shutil, subprocess, tempfile, unittest, unittest.mock

---

## Implementation Constraints

- Do not vendor `acp-agent-gateway` into this repository.
- Do not move analyzer business concepts into the Gateway repository.
- Do not change direct CLI default detection order in the first version.
- Do not auto-install Gateway or ACP adapters.
- Do not use `shell=True`.
- Do not let Gateway stderr JSONL participate in business JSON parsing.
- Do not write Gateway `sessionRef` into PRD/ISSUE documents.
- Do not automatically close, forget, or repair prompt sessions after a successful analysis.
- Do not drop role-based multi-repository support; `RoleWorkspace` remains part of the Gateway path.

---

## File Map

| File | Responsibility | Action |
| --- | --- | --- |
| `zentao_analyzer/agent_client.py` | Add Gateway backend or delegate to new module | Modify |
| `zentao_analyzer/gateway_client.py` | Gateway CLI resolution, request execution, event capture, error mapping | Create |
| `zentao_analyzer/app_config.py` | Add Gateway config fields and preserve legacy backend config | Modify |
| `zentao_analyzer/main.py` | Add CLI args and include Gateway metadata in result/debug flow | Modify |
| `zentao_analyzer/analysis_result.py` | Carry optional Gateway diagnostics if needed in Analysis Result | Modify if needed |
| `zentao_analyzer/debug_bundle.py` | Write Gateway events and Session Reference diagnostics | Modify |
| `zentao_analyzer/summary_report.py` | Include Gateway Session Reference and error diagnostics | Modify |
| `SKILL.md` | Prefer Gateway backend when triggered as a Skill | Modify |
| `SKILL.yaml` | Add `gateway` agent and `gateway_agent` input | Modify |
| `README.md` / `docs/skill-overview.md` | Document Gateway backend and fallback rules | Modify |
| `tests/test_agent_client.py` | Gateway AgentClient behavior with fake CLI | Modify |
| `tests/test_main_phase*.py` | CLI flow and output contract coverage | Modify |
| `tests/test_gateway_client.py` | Focused Gateway CLI tests | Create |
| `tests/fixtures/fake_gateway.py` | Fake Gateway CLI stdout/stderr cases | Create |

---

## Task 1: Add Gateway Runtime Configuration

**Tests first:**

- `--agent gateway --gateway-agent opencode` is accepted.
- `--agent gateway` without `--gateway-agent` fails with a configuration error before invoking an Agent.
- Existing `--agent claude|codex|opencode` behavior is unchanged.
- Direct CLI with no `--agent` keeps existing detection order and never silently selects Gateway.
- `--model` is preserved for Gateway request JSON.

**Implementation:**

- Add argparse option:

```python
parser.add_argument("--gateway-agent", choices=["opencode", "claude", "codex"], help="ACP Agent Gateway Agent Name")
parser.add_argument("--gateway-bin", help="ACP Agent Gateway CLI command; defaults to ACP_AGENT_GATEWAY_BIN or PATH")
parser.add_argument("--gateway-permission-policy", default="best-effort-read-only", ...)
parser.add_argument("--gateway-idle-timeout", type=int, default=300, ...)
```

- Extend `RuntimeConfig` with:
  - `gateway_agent`
  - `gateway_bin`
  - `gateway_permission_policy`
  - `gateway_idle_timeout`
- Keep legacy command fields for legacy backends only.

**Verification:**

```bash
python3 -m unittest tests/test_app_config.py tests/test_main_phase4.py
```

---

## Task 2: Implement Gateway CLI Client

**Tests first:**

- Uses `ACP_AGENT_GATEWAY_BIN` when set.
- Falls back to `shutil.which("acp-agent-gateway")`.
- Missing executable returns `error_kind=config`.
- Splits configured command with `shlex.split`.
- Never uses `shell=True`.
- Writes request JSON with `apiVersion: "v1"`, `prompt`, `model`, `permissionPolicy`, `timeoutMs`, and `idleTimeoutMs`.
- Invokes `start-session --agent <gateway-agent> --cwd <workspace> --input <request-file>`.
- Parses final stdout JSON and metadata stderr JSONL separately.

**Implementation:**

- Create `zentao_analyzer/gateway_client.py`:
  - `GatewayConfig`
  - `GatewayResult`
  - `resolve_gateway_command(config)`
  - `map_gateway_error(error_code)`
  - `call_gateway_start_session(prompt, cwd, config)`
- Use a temporary input JSON file rather than shell stdin to match Gateway CLI support and simplify fake CLI tests.
- Convert analyzer seconds to Gateway milliseconds.
- Capture stderr lines and parse JSON events where possible; preserve unparsable stderr as redacted diagnostics.

**Verification:**

```bash
python3 -m unittest tests/test_gateway_client.py
```

---

## Task 3: Adapt AgentClient to Gateway Backend

**Tests first:**

- `AgentClient(AgentConfig(agent="gateway", gateway_agent="opencode")).call(prompt)` returns `AgentResult.ok=True` when fake Gateway returns completed text containing business JSON.
- `AgentResult.raw_response` equals Gateway `text`, not stderr events.
- `AgentResult.json_data` uses existing `extract_json_object()` and quote repair behavior.
- Gateway failed result maps `error_kind` and preserves diagnostics.
- Unknown `gateway_error_code` maps to `runtime`.

**Implementation:**

- Extend `AgentConfig` with Gateway fields, or add a nested Gateway config returned by `RuntimeConfig.agent_config_dict()`.
- In `AgentClient.call()` dispatch `agent == "gateway"` to the Gateway client.
- Preserve existing `_parse_text()` path for Gateway completed text.
- Add optional diagnostic fields to `AgentResult`:
  - `gateway_error_code`
  - `gateway_session_ref`
  - `gateway_events`
  - `gateway_transport_error`

**Verification:**

```bash
python3 -m unittest tests/test_agent_client.py tests/test_gateway_client.py
```

---

## Task 4: Preserve RoleWorkspace as Gateway Workspace

**Tests first:**

- Multi-repository analysis creates `RoleWorkspace` and passes `workspace.path` as Gateway `--cwd`.
- Single-repository analysis passes the real repository path as Gateway `--cwd`.
- Prompt repository context still includes role search paths and original repository paths.
- Evidence validation still uses original `RepositorySet`, not role workspace symlink paths.

**Implementation:**

- Keep existing `analyzer.analyze()` `RoleWorkspace` block.
- Ensure `dataclasses.replace(agent_config, cwd=workspace.path or fallback_cwd)` still applies to Gateway backend.
- Do not alter `validate_evidence_locations()` or repository role semantics.

**Verification:**

```bash
python3 -m unittest tests/test_repositories.py tests/test_analyzer.py
```

---

## Task 5: Record Gateway Session and Events

**Tests first:**

- Completed Gateway result records `sessionRef` in analysis result diagnostics.
- Summary Report includes Gateway session reference for the item.
- Debug Bundle writes Gateway events JSONL or equivalent structured diagnostics.
- PRD/ISSUE document text does not contain the Gateway session reference.
- Failed Gateway result with reported `sessionRef` records it as diagnostic but does not mark it as known recoverable.

**Implementation:**

- Thread Gateway diagnostics from `AgentResult` into `AnalysisResult` or per-item metadata in `main.py`.
- Extend `debug_bundle.py` with:
  - `write_gateway_events(item_id, events)`
  - `write_gateway_diagnostics(item_id, payload)`
- Extend `summary_report.py` item fields with:
  - `gateway_session_ref`
  - `gateway_error_code`
  - `gateway_backend_agent`
- Do not modify document generator to render these fields.

**Verification:**

```bash
python3 -m unittest tests/test_debug_bundle.py tests/test_summary_report.py tests/test_document_generator.py
```

---

## Task 6: Update Skill and User Documentation

**Tests first:**

- Documentation examples include `--agent gateway --gateway-agent <host-agent>`.
- `SKILL.yaml` lists `gateway` as a supported agent and has `gateway_agent` input.
- Skill text still states that `SKILL.md` invokes analyzer CLI and does not call Gateway directly.
- Skill fallback behavior is documented.

**Implementation:**

- Update `SKILL.md`:
  - Preconditions mention Gateway CLI and ACP adapters.
  - Invocation rules prefer Gateway backend when available.
  - Command templates use `--agent gateway --gateway-agent <host-agent>`.
  - Failure handling notes Gateway missing/config errors and fallback.
- Update `SKILL.yaml`:
  - `agents: [gateway, codex, claude, opencode]`
  - add `gateway_agent`
- Update `README.md` and `docs/skill-overview.md` with the same boundary.

**Verification:**

```bash
python3 -m unittest tests/test_main_phase4.py
```

---

## Task 7: End-to-End Fake Gateway Flow

**Tests first:**

- Fake Gateway completed run produces a valid PRD/ISSUE and summary/debug entries.
- Fake Gateway parse failure produces retryable analyzer failure and records sessionRef.
- Fake Gateway timeout maps to analyzer timeout behavior.
- Fake Gateway stderr event content is present in debug/log output and absent from raw response.
- Batch run creates one Gateway start-session call per item.

**Implementation:**

- Add `tests/fixtures/fake_gateway.py` supporting modes via env vars:
  - completed
  - failed with errorCode
  - invalid stdout
  - completed with stderr JSONL events
- Drive analyzer with `ACP_AGENT_GATEWAY_BIN="python3 tests/fixtures/fake_gateway.py"`.

**Verification:**

```bash
python3 -m unittest tests/test_main_phase4.py tests/test_main_phase8.py tests/test_gateway_client.py
```

---

## Rollout

1. Merge Gateway backend behind explicit `--agent gateway`.
2. Update `SKILL.md` to prefer Gateway path for Skill-triggered formal analysis.
3. Keep legacy direct CLI defaults unchanged.
4. Run fake Gateway unit and integration tests in CI.
5. Run optional real Gateway smoke manually with one single-repository item and one multi-repository item.
6. After successful use in real projects, decide separately whether direct CLI defaults should move to Gateway.

---

## Out of Scope

- Making Gateway the direct CLI default.
- Automatically installing Gateway or ACP adapters.
- Automatically sending JSON repair prompts.
- Automatically closing or forgetting durable sessions after success.
- `strict-read-only` default support for `/tmp` role workspaces.
- Moving analyzer code, tests, or Python dependencies into `acp-agent-gateway`.
