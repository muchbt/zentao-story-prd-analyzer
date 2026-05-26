# Zentao Story PRD Analyzer

This context defines the domain language for turning Zentao items and local code evidence into reviewable PRD or ISSUE documents.

## Language

**Zentao Item**:
An input object fetched from Zentao, such as `story`, `requirement`, `bug`, `task`, `ticket`, or `feedback`.
_Avoid_: Issue, work item, object

**Feature Item**:
A Zentao Item whose purpose is to describe desired product behavior.
_Avoid_: PRD, feature document

**Requirement Point**:
An independently verifiable expected-behavior unit within a Feature Item, such as an MCU message emission, a SOC state transition, or a cross-side protocol agreement.
_Avoid_: entire requirement, evidence item, code side

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

**LLM Understanding Summary**:
A natural-language restatement of what the Agent understood the Zentao Item to require or report before evaluating code evidence.
_Avoid_: Analysis Result, Code Evidence, recommendation list

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

**Candidate Location**:
A source-code file and line range found while investigating a responsibility-pending Requirement Point, retained for review without supporting a completion or gap conclusion.
_Avoid_: Cited evidence location, code evidence, seed location

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

**Code Side**:
A separately owned implementation domain inside a Target Repository, such as the MCU side or SOC side of an end-to-end vehicle feature.
_Avoid_: repository, module directory, evidence file

**Analysis Scope**:
The explicitly selected set of Code Sides that an analysis run is permitted to evaluate for a Zentao Item.
_Avoid_: search hint, target repository, unrestricted repository scan

**Responsibility Hint**:
User-provided ownership metadata identifying which Code Sides are responsible for implementing a Requirement Point, without adding or changing its expected behavior.
_Avoid_: supplemental requirement, code clue, analysis scope

**Self-Contained Skill Package**:
An Agent CLI Skill package that includes `SKILL.md`, the analyzer entrypoint, and the analyzer source code needed to run without requiring a separate clone of this project.
_Avoid_: External path wrapper, metadata-only skill

**Official Zentao Skill**:
The Zentao-provided Agent skill or integration whose responsibility is fetching or interacting with Zentao data directly.
_Avoid_: PRD generator, code analyzer, Agent CLI Skill

## Relationships

- A **Zentao Item** is classified as either a **Feature Item** or a **Defect Item** before analysis.
- A **Zentao Item** alone does not contain an **Analysis Result**.
- A **Feature Item** may contain multiple **Requirement Points** whose implementation responsibilities differ by **Code Side**.
- **Requirement Points** are proposed by the Agent from the original **Feature Item** description fetched from Zentao, and retained for reviewer inspection.
- **Requirement Points** are part of analysis for any **Feature Item**, regardless of whether its **Target Repository** has explicitly configured **Code Sides**.
- An **Analysis Result** for a **Feature Item** is based on its assessed **Requirement Points** by default; point-based assessment is not an optional multi-side mode.
- A **Requirement Point** may require evidence from zero, one, or multiple **Code Sides** before its implementation state can be confirmed.
- A **Requirement Point** is assessed independently before its result contributes to the aggregate **Analysis Result** for its **Feature Item**.
- An **LLM Understanding Summary** describes the intended meaning of a **Zentao Item** and must not duplicate the **Analysis Result** sections.
- The expected behavior evaluated for a **Feature Item** is sourced from its fetched **Zentao Item** description; user-provided analysis input may guide code discovery but does not add or redefine requirements.
- A **Responsibility Hint** may assign implementation ownership for an existing **Requirement Point** when Zentao does not carry that ownership metadata; it does not create, split, or alter the point's expected behavior.
- A **Responsibility Hint** and an **Analysis Scope** serve different purposes: the former identifies responsible **Code Sides**, while the latter limits which **Code Sides** an analysis run may evaluate.
- A **Responsibility Hint** identifies its intended **Requirement Point** through a requirement-text fragment before analysis; runtime-generated Requirement Point identifiers do not serve as input identities.
- A valid **Responsibility Hint** must identify only **Code Sides** included in the current **Analysis Scope**; for a multi-side hint, the scope must include every stated responsible side, otherwise it cannot evaluate the stated responsibility.
- A cross-side **Analysis Scope** does not require a **Responsibility Hint** before analysis; unresolved ownership remains visible as a responsibility-pending **Requirement Point**, not a preflight failure.
- A **Responsibility Hint** may override inferred implementation ownership, but it cannot contradict ownership explicitly stated in the fetched **Zentao Item**.
- A provided **Responsibility Hint** that cannot be applied must remain recorded with its rejection reason rather than being silently discarded or treated as confirmed ownership.
- An unapplied **Responsibility Hint** does not by itself prevent a **PRD Document**; ownership derived reliably from the **Zentao Item** may still support analysis, otherwise the affected **Requirement Point** remains responsibility-pending.
- Identical **Responsibility Hints** may be deduplicated with their duplication retained for review; contradictory hints for the same identified responsibility must not be silently merged.
- A **Code Clue** may be either a **Search Hint** or a **Seed Path**.
- A **Clues File** provides item-specific **Code Clues** when a run analyzes multiple Zentao Items.
- A **Seed Path** must be a file inside the repository, otherwise it becomes a **Rejected Clue**.
- A **Search Hint** guides Agent search but is not itself **Code Evidence**.
- A **Search Hint** may describe a behavior to search for, but it does not become expected behavior for a **Feature Item** or a source of **Requirement Points**.
- A **Search Hint** does not become a **Rejected Clue** because the analyzer does not load source content from it.
- **Code Evidence** constrains the confidence and conclusion of an **Analysis Result**.
- **Structured Evidence** is preferred for new Agent outputs; free-form evidence text exists only as a fallback.
- A **Cited Evidence Location** may support implemented behavior, a missing behavior, or a limiting condition; it is not by itself an implemented feature.
- Absence of **Code Evidence** prevents confirmation of gaps in a **Feature Item**; it is not itself a gap.
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
- A **Target Repository** may contain multiple **Code Sides**, such as MCU and SOC implementations.
- A **Code Side** is identified by a logical side name mapped to a directory within the **Target Repository**; directory names alone do not define the domain meaning of a side.
- A multi-side **Target Repository** is activated for scoped analysis only through an explicit side mapping supplied by configuration or by the user; directory names alone do not trigger multi-side behavior.
- An **Analysis Scope** selects one or more **Code Sides** for one analysis run and constrains which cross-side implementation conclusions may be made.
- An **Analysis Scope** is expressed as a set of logical **Code Side** names; selecting multiple sides represents cross-side analysis without requiring a special cross-side scope value.
- An **Analysis Scope** permits investigation of selected **Code Sides** but does not imply that every **Requirement Point** requires evidence from every selected side.
- Analysis of a multi-side **Target Repository** does not implicitly expand from one **Code Side** to every available **Code Side**.
- A multi-side **Target Repository** without an explicit **Analysis Scope** is not ready for analysis; the user must select scope before the analyzer evaluates code.
- A **Target Repository** without an explicit multi-side mapping retains ordinary single-repository analysis behavior and does not require an **Analysis Scope**, even if it contains directories named `mcu_src/` and `soc_src/`.
- A **Requirement Point** whose responsible **Code Sides** fall outside the current **Analysis Scope** is outside-scope and unassessed for that run; it is not a gap or insufficient-evidence conclusion.
- An **Analysis Result** that completes all in-scope **Requirement Points** while leaving outside-scope points unassessed reports scoped completion rather than completion of the full **Feature Item**.
- An **Analysis Result** over a proper subset of known **Code Sides** is scope-limited even when no specific outside-scope **Requirement Point** is identified; it cannot establish that unselected sides carry no relevant responsibility.
- When all selected **Code Sides** may be searched for a responsibility-pending **Requirement Point**, discovered code remains investigative material and cannot by itself establish its responsible side or completion.
- Candidate code found for a responsibility-pending **Requirement Point** belongs in its **Debug Bundle**, not in the **PRD Document** as a cited evidence location.
- A **Candidate Location** is validated against the selected **Analysis Scope** like a cited location, but it is not counted as **Code Evidence** and does not contribute to completion status or gaps.
- A **Candidate Location** belongs only to the diagnostic run that discovered it; a later analysis run does not automatically reuse it as a clue or evidence source.
- A formal **Analysis Result** may retain the adopted responsible **Code Sides** and whether they were explicit in Zentao, supplied by a **Responsibility Hint**, or inferred by the Agent; raw hints and **Candidate Locations** remain diagnostic material.
- Agent-inferred responsibility may support a completed **Requirement Point** only when the inference is reviewable and sufficiently grounded in the fetched **Zentao Item**; otherwise responsibility remains pending.
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
- "implemented feature" was proposed as a presentation of every **Cited Evidence Location**; resolved: cited evidence can also establish gaps or limitations, so documents retain the neutral code-evidence presentation unless positive implementation facts are modelled separately.
- "no code evidence" was considered as a feature gap; resolved: it means the analyzer cannot determine whether gaps exist, not that a missing behavior has been established.
- "manual requirement content" was considered as analysis input; resolved: requirements are sourced only from the fetched **Zentao Item**, and an explicit request to supplement requirement content must be rejected rather than treated as a **Code Clue** or used to add or redefine expected behavior.
- "code clue" may contain behavior-like text; resolved: when explicitly provided as a **Search Hint**, it guides code discovery only and cannot expand the requirement basis.
- "responsibility side" was ambiguous about whether it modifies requirement content; resolved: a user may provide a **Responsibility Hint** for an existing **Requirement Point** because Zentao lacks that ownership field, but it cannot add or change expected behavior.
- "requirement point ID" was considered for pre-analysis ownership input; resolved: `RP-xxx` identifiers exist only within an analysis result, while a **Responsibility Hint** binds by a requirement-text fragment that must match a proposed **Requirement Point** unambiguously.
- "responsibility outside scope" was ambiguous about whether to analyze partial responsibility; resolved: a **Responsibility Hint** naming a **Code Side** outside the current **Analysis Scope** is invalid input and analysis must not start.
- "multi-side responsibility with partial scope" was ambiguous about partial analysis; resolved: an **Analysis Scope** must contain every **Code Side** named by a multi-side **Responsibility Hint**, or analysis must not start.
- "responsibility hint required for cross-side analysis" was considered as a launch gate; resolved: it is optional, and missing ownership metadata affects Requirement Point conclusions only when responsibility cannot be inferred reliably.
- "responsibility hint conflicts with Zentao ownership" was ambiguous about precedence; resolved: explicit ownership in the fetched **Zentao Item** prevails, while a valid **Responsibility Hint** may replace only Agent-inferred ownership.
- "invalid responsibility hint" was ambiguous about auditability; resolved: an unapplied **Responsibility Hint** and its invalidity reason must be retained for review.
- "invalid responsibility hint" was ambiguous about whether it prevents formal analysis; resolved: it does not by itself block a **PRD Document**, but unresolved ownership prevents the affected **Requirement Point** from supporting a completed conclusion.
- "duplicate responsibility hints" was ambiguous about merging; resolved: identical hints may be deduplicated with an audit record, while contradictory ownership inputs cannot be interpreted as a multi-side responsibility declaration.
- "repository scope" was ambiguous when a target root contains both MCU and SOC implementations; resolved: a multi-side **Target Repository** requires an explicit **Analysis Scope**, and analysis stops for user selection rather than defaulting to unrestricted cross-side exploration or inferring scope from requirement text.
- "MCU/SOC directory" was ambiguous about whether side identity is defined or detected by fixed folder names; resolved: **Code Side** identity and multi-side mode require explicit mapping, and `mcu_src/` / `soc_src/` names alone do not activate an **Analysis Scope** requirement.
- "cross-side scope" was considered as a special fixed option; resolved: **Analysis Scope** is a set of **Code Side** names, so selecting `mcu` and `soc` already expresses cross-side evaluation and remains extensible to additional sides.
- "both selected sides need evidence" was considered as a rule for cross-side completion; resolved: evidence completeness is evaluated per **Requirement Point** and its responsible **Code Sides**, because a single **Feature Item** may contain independent MCU-only, SOC-only, and cross-side expected behaviors.
- "requirement point analysis" was coupled to multi-side mode; resolved: **Requirement Points** apply to all **Feature Items**, while **Code Sides** and **Analysis Scope** only extend responsibility and scoped-evaluation rules when multi-side analysis is explicitly enabled.
- "single-side analysis of a multi-side requirement" was ambiguous about full completion; resolved: it may evaluate in-scope **Requirement Points**, while points owned outside the **Analysis Scope** are reported as outside-scope and prevent an unconditional completed conclusion for the full **Feature Item**.
- "no identified outside-scope point" was ambiguous about full completion in a subset analysis; resolved: selecting fewer than all known **Code Sides** still yields a scope-limited conclusion, without inventing an additional **Requirement Point**.
- "found code for a responsibility-pending point" was ambiguous about ownership inference; resolved: searching all in-scope sides may yield review material, but code location cannot establish responsibility or a completed conclusion without a confirmed responsibility basis.
- "candidate code for a responsibility-pending point" was ambiguous about PRD presentation; resolved: it remains debug-only investigative material so readers do not confuse a search hit with confirmed **Code Evidence**.
- "candidate code location" was ambiguous about evidence storage; resolved: store it as a **Candidate Location** in `candidate_locations`, separate from evidence while applying the same location-boundary validation.
- "candidate location reuse on retry" was considered for responsibility-confirmed reruns; resolved: later runs do not automatically load earlier **Candidate Locations**, and any reused path must be provided explicitly as a new **Code Clue**.
- "responsibility metadata in result JSON" was ambiguous about diagnostic leakage; resolved: formal results expose adopted responsibility and its source category only, while raw **Responsibility Hints** and **Candidate Locations** remain in the **Debug Bundle**.
- "applied responsibility hint in PRD" was ambiguous about disclosing user input text; resolved: a **PRD Document** identifies responsibility supplied by user hint without displaying the original matching fragment, which remains in the **Debug Bundle**.
- "agent-inferred responsibility" was ambiguous about completion confidence; resolved: a reviewable inference grounded in Zentao-described behavior may support completion, while an unreliable inference remains responsibility-pending.
- "unconfigured ordinary repository" was ambiguous about requiring scope selection; resolved: without an explicit multi-side mapping, analysis continues under existing single-repository behavior without requiring an **Analysis Scope**.
