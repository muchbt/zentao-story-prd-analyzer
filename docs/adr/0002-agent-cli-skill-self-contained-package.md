# Agent CLI skill uses a self-contained package

The first Agent CLI Skill version will be delivered as a self-contained package that includes `SKILL.md`, the analyzer entrypoint, and the analyzer source code required to run the Zentao analysis pipeline. This lets Codex, Claude Code, or another Agent CLI invoke the analyzer from a Target Repository without requiring users to manually enter or configure a separate clone of this project.

## Considered Options

- Metadata-only skill that references an external project path: lighter to install, but fragile because every Agent CLI environment must know where the analyzer repository was cloned.
- Thin `SKILL.md` wrapper bundled with the full analyzer code: larger package, but stable after installation and easier to use from any Target Repository.
- Python package with console script plus `SKILL.md`: cleaner long-term CLI ergonomics, but unnecessary for the first Agent CLI Skill version and adds packaging decisions before invocation behavior is proven.

## Consequences

- The Skill can be installed and used without separately cloning this repository.
- `SKILL.md` remains a thin wrapper: it tells the Agent when to call the analyzer, how to collect parameters, and how to interpret outputs, but it does not duplicate the analysis logic.
- The Target Repository defaults to the Agent CLI current working directory unless the user provides an explicit repository path.
- Upgrades require reinstalling or replacing the self-contained Skill package.
- A future version can still add `pyproject.toml` and a console script after the command surface stabilizes.
