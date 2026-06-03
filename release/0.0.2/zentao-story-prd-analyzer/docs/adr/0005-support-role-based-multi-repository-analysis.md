# Support role-based multi-repository analysis

The analyzer will support analyzing a Target Repository Set instead of only one Target Repository. Multi-repository analysis is needed for codebases where one Feature Item or Defect Item is implemented across multiple code roles, such as SoC and MCU repositories connected by a communication protocol; running separate single-repository analyses would lose the protocol-level evidence chain.

## Considered Options

- Keep one `--repo-path` and ask users to run the analyzer once per repository: rejected because completion and defect conclusions can require evidence from both sides of a communication path, and independent reports cannot prove a closed loop.
- Allow multiple anonymous repository paths: rejected because evidence locations would not carry the code role needed to interpret sender, receiver, protocol stack, application, bootloader, or vendor SDK responsibilities.
- Introduce role-based repositories through `--repo`, where single-repository mode is `--repo <path>` and multi-repository mode is `--repo <role>=<path>` repeated: chosen because it keeps single-repository usage small while making multi-repository evidence explicit.

## Consequences

- `--repo` becomes the preferred repository input. `--repo-path` remains a single-repository compatibility entry point, and using both inputs in one run is an error.
- In multi-repository mode every repository must have a unique Repository Role. Multiple anonymous `--repo` values, or mixing anonymous and role-qualified `--repo` values, fail during preprocessing.
- A single anonymous repository is normalized internally as the implicit `main` role, but single-repository documents do not display the role dimension.
- Protocol Hints are structured Search Hints for cross-role communication protocol clues. They support optional role scope and initial types `cmd_id`, `msg`, `field`, and `text`.
- Role order inside a Protocol Hint is not directional; it defines the search scope. Direction can be expressed later with an explicit field if needed.
- Complex multi-repository input is carried through a Structured Clue File, including repositories, item-specific Search Hints, Protocol Hints, role-qualified Seed Paths, and optional Primary Repository Role.
- Command-line repository inputs are authoritative for the run. `repositories` in a Structured Clue File are used only when no `--repo` or `--repo-path` input is provided; if both sources define repositories and disagree, preprocessing fails.
- Relative repository paths in a Structured Clue File are resolved from the clue file's directory. Relative repository paths passed on the command line are resolved from the process working directory.
- Role-qualified Seed Paths are always resolved from the corresponding repository root. In single-repository mode, legacy unqualified Seed Path arrays are normalized to the implicit `main` role.
- Agent CLI Skills may translate explicit user natural language into a Structured Clue File, but must ask for confirmation before guessing protocol hint type, repository role, or item ownership.
- Multi-repository evidence locations use Repository Role, repository-relative path, and line range as the primary identity. Absolute paths are only for local validation and debug bundles.
- Cross-role Completion Assessment cannot be confirmed from one side of the code evidence alone. Agent results must expose role-level evidence status and protocol trace status such as `closed_loop`, `partial`, `not_found`, or `ambiguous`.
- `closed_loop` means every scoped Repository Role has valid Code Evidence tied to the same Protocol Hint and the Agent can explain the protocol association. It does not by itself mean the Requirement Point is complete.
- Summary Reports include role-level evidence counts and protocol trace status counts, but do not expand full evidence details.
- Debug Bundles save the normalized structured clue input used for the run, including repositories, role-qualified Seed Paths, Protocol Hints, Primary Repository Role, and item ownership, without copying source code.
- Multi-repository analysis does not automatically scale the Agent timeout by repository count. Users must explicitly increase the timeout when needed.
- Agent multi-repository search should prefer a temporary role workspace that exposes repositories under their role names via symlinks. If symlinks are unavailable, the analyzer may fall back to absolute repository paths while still validating role-qualified evidence output.
