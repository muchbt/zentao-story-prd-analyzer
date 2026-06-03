# Debug bundle records code evidence locations

Debug bundles default to recording both collected source locations and Agent-cited evidence locations, while full source-code content remains opt-in via `--debug-include-code`. This preserves enough information to audit whether an analysis was based on the right files and line ranges without making every diagnostic bundle copy potentially sensitive code.

## Considered Options

- Save full code snippets by default: easier to replay, but larger and more likely to expose sensitive source code.
- Save only prompts and responses: smaller, but not enough to verify what code evidence the Agent actually saw.
- Save file names and line ranges by default, with full code behind an explicit flag: chosen as the default balance between traceability and data minimization.

## Consequences

- Debug bundle consumers can depend on location metadata being present even when code content is absent.
- PRD and ISSUE documents remain readable review artifacts; debug bundles carry the deeper run-reconstruction data.
