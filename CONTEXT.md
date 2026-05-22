# Zentao Story PRD Analyzer

This context defines the domain language for turning Zentao items and local code evidence into reviewable PRD or ISSUE documents.

## Language

**Zentao Item**:
An input object fetched from Zentao, such as `story`, `requirement`, `bug`, `task`, `ticket`, or `feedback`.
_Avoid_: Issue, work item, object

**Feature Item**:
A Zentao Item whose purpose is to describe desired product behavior.
_Avoid_: PRD, feature document

**Defect Item**:
A Zentao Item whose purpose is to describe a problem, failure, or feedback needing investigation.
_Avoid_: ISSUE, issue input

**PRD Document**:
An output Markdown document that summarizes a Feature Item, code evidence, completion status, gaps, and recommendations.
_Avoid_: Story, requirement

**ISSUE Document**:
An output Markdown document that summarizes a Defect Item, code evidence, suspected causes, affected scope, and repair recommendations.
_Avoid_: Bug, ticket, feedback, issue input

**Analysis Result**:
A code-evidence-based conclusion about a Zentao Item's completion status, suspected cause, confidence, and recommendations.
_Avoid_: Raw Zentao data, fetched item

**Code Clue**:
An explicit hint used to find relevant source code for a Zentao Item, such as a keyword, file path, directory, or symbol name.
_Avoid_: Analysis result, proof

**Clues File**:
A user-provided file that maps Zentao Item IDs to item-specific Code Clues for batch analysis.
_Avoid_: Summary report, debug bundle

**Rejected Clue**:
A user-provided Code Clue that is not used because it violates run boundaries, such as pointing outside the repository.
_Avoid_: Missing evidence, ignored bug

**Code Evidence**:
A concrete source-code reference that supports or limits an Analysis Result.
_Avoid_: Search hint, assumption

**Structured Evidence**:
Code Evidence represented with explicit path, line range, symbol, and reason fields.
_Avoid_: Free-form evidence text

**Debug Bundle**:
A local diagnostic package that records the inputs, prompts, responses, logs, and code evidence locations needed to review an analyzer run.
_Avoid_: PRD document, ISSUE document

**Collected Location**:
A source-code file and line range included in the context sent to the Agent.
_Avoid_: Cited evidence

**Cited Evidence Location**:
A source-code file and line range explicitly referenced by the Agent as support for its conclusion.
_Avoid_: Search result, collected-only location

**Summary Report**:
A machine-readable index of analyzed Zentao Items, generated documents, analysis status, evidence counts, and diagnostic paths.
_Avoid_: PRD document, ISSUE document, full review report

**Evidence Traceability Phase**:
A follow-up implementation phase that improves code clue inputs, collected locations, cited evidence locations, and debug-bundle auditability after the initial four-stage pipeline exists.
_Avoid_: Phase 2 patch, Phase 4 patch

**Agent CLI Skill**:
A discoverable and installable skill package for Agent CLI environments such as Codex or Claude Code, allowing users to trigger Zentao analysis from another repository without manually entering this project directory.
_Avoid_: SKILL.yaml, command alias, Python package

**Target Repository**:
The local code repository being analyzed for a Zentao Item. When an Agent CLI Skill is invoked from another repository, the current working directory is the default Target Repository unless the user provides an explicit repository path.
_Avoid_: Skill repository, analyzer source tree, output directory

**Self-Contained Skill Package**:
An Agent CLI Skill package that includes `SKILL.md`, the analyzer entrypoint, and the analyzer source code needed to run without requiring a separate clone of this project.
_Avoid_: External path wrapper, metadata-only skill

**Official Zentao Skill**:
The Zentao-provided Agent skill or integration whose responsibility is fetching or interacting with Zentao data directly.
_Avoid_: PRD generator, code analyzer, Agent CLI Skill

## Relationships

- A **Zentao Item** is classified as either a **Feature Item** or a **Defect Item** before analysis.
- A **Zentao Item** alone does not contain an **Analysis Result**.
- A **Code Clue** may come from a **Zentao Item** or from the user.
- A **Clues File** provides item-specific **Code Clues** when a run analyzes multiple Zentao Items.
- A path-based **Code Clue** must stay inside the repository, otherwise it becomes a **Rejected Clue**.
- **Code Evidence** constrains the confidence and conclusion of an **Analysis Result**.
- **Structured Evidence** is preferred for new Agent outputs; free-form evidence text exists only as a fallback.
- A **Debug Bundle** must include **Code Evidence** locations even when it does not include full source-code content.
- A **Debug Bundle** distinguishes **Collected Locations** from **Cited Evidence Locations**.
- A **Feature Item** produces exactly one **PRD Document** when document generation succeeds.
- A **Defect Item** produces exactly one **ISSUE Document** when document generation succeeds.
- A **PRD Document** or **ISSUE Document** shows key **Cited Evidence Locations**, not every **Collected Location**.
- A **Summary Report** indexes generated **PRD Documents** and **ISSUE Documents** for automation.
- An **Analysis Result** is derived from a **Zentao Item**, **Code Clues**, and **Code Evidence**.
- An **ISSUE Document** is never a Zentao input module name.
- The **Evidence Traceability Phase** extends the four-stage pipeline without redefining the original stage boundaries.
- An **Agent CLI Skill** is an installation and invocation wrapper around the analyzer, not a new analysis stage.
- `SKILL.yaml` describes project capability metadata but is not itself an **Agent CLI Skill**.
- An **Agent CLI Skill** runs the analyzer against a **Target Repository**.
- The **Target Repository** defaults to the Agent CLI's current working directory.
- A first-version **Agent CLI Skill** should be delivered as a **Self-Contained Skill Package**.
- The **Official Zentao Skill** is the preferred tool for Zentao-only data access.
- This analyzer's **Agent CLI Skill** exists to connect **Zentao Items** with **Code Evidence**, **Analysis Results**, and generated **PRD Documents** or **ISSUE Documents**.

## Example Dialogue

> **Dev:** "Should users pass `--module issue` when they want defect analysis?"
> **Domain expert:** "No. They should pass the real Zentao module, such as `bug`, `ticket`, or `feedback`; ISSUE is only the generated document type."

> **Dev:** "Can we install `SKILL.yaml` as a Codex skill?"
> **Domain expert:** "No. `SKILL.yaml` is metadata; an Agent CLI Skill needs a `SKILL.md` wrapper that tells the Agent when and how to run the analyzer."

## Flagged Ambiguities

- "ISSUE" was used to mean both a Zentao input and an output document type; resolved: **ISSUE Document** is output-only and must not be used as a Zentao input module.
- "SKILL" was used to mean both `SKILL.yaml` metadata and an installable Agent CLI skill; resolved: **Agent CLI Skill** means the installable wrapper, while `SKILL.yaml` remains project capability metadata.
