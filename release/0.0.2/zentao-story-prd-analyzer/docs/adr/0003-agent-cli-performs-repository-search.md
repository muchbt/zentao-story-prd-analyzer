# Agent CLI performs repository search

The analyzer will stop using automatic natural-language keyword collection as the primary code search mechanism and will rely on repository-aware Agent CLI backends to search the Target Repository. Demo runs showed the keyword collector feeding unrelated source context while the Agent independently found the relevant code evidence, because Zentao prose keywords and code identifiers do not share a reliable search space.

## Considered Options

- Keep the local keyword collector and tune stop words, weighting, file filters, and grep behavior: lower architectural churn, but keeps spending prompt budget on noisy context and does not solve NL-to-code identifier mapping.
- Replace keyword extraction with structured Search Hints and optional Seed Paths while the Agent CLI searches the repository: chosen because user-supplied hints can guide the Agent without pretending to be evidence, and Seed Paths can provide focused starting context when the user knows the relevant files.
- Keep the OpenAI SDK backend as a fallback: rejected because an API-only backend cannot inspect the Target Repository and would require reintroducing local collection.

## Consequences

- Supported analysis backends must be Agent CLIs that can inspect the Target Repository, such as Claude CLI, Codex CLI, or OpenCode.
- Search Hints are prompt guidance, not Code Evidence.
- Seed Paths are optional repository files loaded as starting context; directories and paths outside the repository are rejected.
- Evidence locations returned by the Agent must be validated against the local repository because they are no longer limited to preloaded snippets.
