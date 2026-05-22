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
An explicit user-provided aid for finding relevant source code for a Zentao Item.
_Avoid_: Analysis result, proof, collected code

**Search Hint**:
A text hint written into the Agent prompt to guide repository search.
_Avoid_: Seed path, collected location, keyword clue

**Seed Path**:
A repository file path whose source content is read into the Agent prompt as starting context.
_Avoid_: Search hint, cited evidence, collected-only location

**Clues File**:
A user-provided file that maps Zentao Item IDs to item-specific Code Clues for batch analysis.
_Avoid_: Summary report, debug bundle

**Rejected Clue**:
A user-provided Seed Path that is not loaded because it violates run boundaries, such as pointing outside the repository.
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

**Seed Location**:
A source-code file and line range loaded from a Seed Path into the Agent prompt as starting context.
_Avoid_: Collected location, cited evidence, Agent search result

**Cited Evidence Location**:
A source-code file and line range explicitly referenced by the Agent as support for its conclusion.
_Avoid_: Search result, collected-only location

**Summary Report**:
A machine-readable index of analyzed Zentao Items, generated documents, analysis status, evidence counts, and diagnostic paths.
_Avoid_: PRD document, ISSUE document, full review report

**Analyzer Process**:
The analyzer runtime that owns generated outputs such as Debug Bundles, PRD Documents, ISSUE Documents, Summary Reports, explicit output files, and explicit log files.
_Avoid_: Agent CLI subprocess, code search agent

**Agent CLI Subprocess**:
An external Agent CLI invocation used by the Analyzer Process to search and read the Target Repository, then return an Analysis Result payload.
_Avoid_: Analyzer process, document writer

**Evidence Traceability Phase**:
A follow-up implementation phase that improves code clue inputs, seed locations, cited evidence locations, and debug-bundle auditability after the initial four-stage pipeline exists.
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
- A **Code Clue** may be either a **Search Hint** or a **Seed Path**.
- A **Clues File** provides item-specific **Code Clues** when a run analyzes multiple Zentao Items.
- A **Seed Path** must be a file inside the repository, otherwise it becomes a **Rejected Clue**.
- A **Search Hint** guides Agent search but is not itself **Code Evidence**.
- A **Search Hint** does not become a **Rejected Clue** because the analyzer does not load source content from it.
- **Code Evidence** constrains the confidence and conclusion of an **Analysis Result**.
- **Structured Evidence** is preferred for new Agent outputs; free-form evidence text exists only as a fallback.
- A **Debug Bundle** must include **Code Evidence** locations even when it does not include full source-code content.
- A **Debug Bundle** distinguishes **Seed Locations** from **Cited Evidence Locations**.
- A **Feature Item** produces exactly one **PRD Document** when document generation succeeds.
- A **Defect Item** produces exactly one **ISSUE Document** when document generation succeeds.
- A **PRD Document** or **ISSUE Document** shows key **Cited Evidence Locations**, not every **Seed Location**.
- A **Summary Report** indexes generated **PRD Documents** and **ISSUE Documents** for automation.
- An **Analysis Result** is derived from a **Zentao Item** and **Code Evidence**, and may be guided by **Code Clues**.
- The **Analyzer Process** is the only writer of generated analyzer outputs.
- An **Agent CLI Subprocess** must not write **PRD Documents**, **ISSUE Documents**, **Debug Bundles**, **Summary Reports**, source files, configuration files, test files, or build files.
- An **Agent CLI Subprocess** may read and search the **Target Repository** to produce an **Analysis Result** payload for the **Analyzer Process**.
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

> **Dev:** "Should a search term like `callback` become a collected location?"
> **Domain expert:** "No. That is a **Search Hint**. Only a **Seed Path** can be read into the prompt as starting source context."

## Flagged Ambiguities

- "ISSUE" was used to mean both a Zentao input and an output document type; resolved: **ISSUE Document** is output-only and must not be used as a Zentao input module.
- "SKILL" was used to mean both `SKILL.yaml` metadata and an installable Agent CLI skill; resolved: **Agent CLI Skill** means the installable wrapper, while `SKILL.yaml` remains project capability metadata.
- "clue" was used to mean both prompt search text and source paths loaded by the analyzer; resolved: **Search Hint** guides Agent search, while **Seed Path** provides source content.
- "collected location" implied the analyzer collected all relevant code; resolved: use **Seed Location** for source ranges preloaded from **Seed Paths**.
- "allowed writes" was ambiguous about whether an Agent CLI could write generated analyzer outputs; resolved: only the **Analyzer Process** writes generated outputs, while an **Agent CLI Subprocess** is read/search-only.
