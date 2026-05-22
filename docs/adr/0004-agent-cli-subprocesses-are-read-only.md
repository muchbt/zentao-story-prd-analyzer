# Agent CLI subprocesses are read-only

Agent CLI subprocesses must read and search the Target Repository but must not write analyzer outputs or repository files; the Analyzer Process is the only writer of Debug Bundles, PRD Documents, ISSUE Documents, Summary Reports, explicit output files, and explicit log files. Earlier defaults used broad skip-permission flags to reduce interaction, but demo runs showed that a repository-aware Agent CLI can overwrite generated documents after returning usable structured evidence. The default must therefore prefer command-level read-only tool constraints, with prompt text serving only as semantic reinforcement rather than the safety boundary.

This applies uniformly to Claude, Codex, and OpenCode backends. If a backend does not expose a stable read-only tool allowlist, the analyzer should not compensate by enabling broad permission bypass by default; it should rely on the host CLI's normal permission or sandbox behavior and document that the read-only guarantee depends on the host CLI's enforcement capabilities.

LLM responses must contain structured Analysis Result fields only. The legacy `output_md` field is removed because it let an Agent CLI influence document rendering outside the Analyzer Process template and blurred the boundary between structured analysis and generated documents.
