---
name: xsoar-playbook-documentation
description: >
  Generates Confluence Data Center wiki-ready documentation from XSOAR 6.14
  playbook definitions. Supports full deep-dive and executive summary detail
  levels. Includes mermaid.js flow visualization.
---

## Detail Levels

This skill supports two documentation modes. Determine the mode from the user's prompt:

| Mode | Trigger Keywords | Default |
|------|-----------------|---------|
| **Full Deep-Dive** | "document", "full documentation", "deep-dive", or unspecified | Yes |
| **Executive Summary** | "summarize", "executive summary", "overview", "high-level" | No |

If the user's intent is ambiguous (e.g., "look at this playbook"), ask which mode they want.

---

## Confluence Data Center Formatting

All output must be formatted for clean rendering in Confluence Data Center:

- Use standard markdown headers (`#`, `##`, `###`) for section structure
- Use pipe tables (`| col | col |`) for all tabular data
- Use fenced code blocks (triple backticks with language hint) for code, JSON, and commands
- Mermaid diagrams use ` ```mermaid ` fencing — requires a Confluence mermaid plugin or separate rendering
- **No inline HTML** — Confluence DC markdown mode does not reliably render it
- Use bold-prefixed callouts instead of admonitions: **Note:**, **Warning:**, **Important:**
- Include a manual Table of Contents at the top with markdown anchor links to each section

---

## Mermaid Flowchart Generation

Generate a mermaid.js flowchart from the playbook's task graph. Follow this algorithm exactly:

### Step 1: Initialize

```
graph TD
```

Use top-down layout. Start from the task referenced by `starttaskid`.

### Step 2: Create Nodes

For each task in the `tasks` object, create a node using the task's key as the ID and `task.task.name` as the label. Use shapes to encode task type:

| Task Type | Mermaid Shape | Example |
|-----------|--------------|---------|
| `start` | Stadium | `0([Start])` |
| `regular` / `standard` | Rectangle | `5[Enrich Indicator]` |
| `condition` | Diamond | `8{Check Severity}` |
| `playbook` (sub-playbook) | Double-bordered | `12[[Block Indicators]]` |
| `title` (section header) | Filled rectangle | `3[/Enrichment Phase/]` |
| Terminal (no `nexttasks`) | Rounded | `15(Close Investigation)` |

### Step 3: Draw Edges

For each task, iterate its `nexttasks` map:

- `#default#` branch → plain arrow: `5 --> 6`
- Named branches (condition labels) → labeled arrow: `8 -->|malicious| 9`
- Multiple targets from one branch → one edge per target

### Step 4: Annotate Error Tolerance

Tasks with `continueonerror: true` — add a comment or style annotation:

```
5[Enrich Indicator]:::errorTolerant
classDef errorTolerant stroke-dasharray: 5 5
```

### Step 5: Validate

**Critical:** Every task ID referenced in any `nexttasks` value **must** appear as a node definition. If a referenced ID is missing from the `tasks` object, render it as:

```
99[⚠ Missing Task 99]:::missing
classDef missing fill:#f96,stroke:#333
```

And flag this in the documentation as a structural issue.

### Large Playbooks (30+ Tasks)

For playbooks with more than 30 tasks, generate a **grouped** flowchart:

1. Identify section boundaries using `title`-type tasks
2. Wrap each section's tasks in a mermaid `subgraph`
3. Show full detail within each subgraph
4. Show cross-section edges between subgraphs

This keeps the diagram readable without losing information.

```
subgraph Enrichment
    5[Enrich IP] --> 6[Enrich Domain]
end
subgraph Response
    10[Block IP] --> 11[Update Blocklist]
end
Enrichment --> Response
```

---

## Full Documentation Template

Use this template when generating **Full Deep-Dive** documentation:

```markdown
# Playbook Documentation: <playbook name>

**Generated:** <date>
**Playbook Version:** <version from playbook JSON, or "Not specified">
**XSOAR Compatibility:** <fromversion>+
**Total Tasks:** <count of entries in tasks object>

## Table of Contents

- [Overview](#overview)
- [Flow Diagram](#flow-diagram)
- [Playbook Inputs](#playbook-inputs)
- [Playbook Outputs](#playbook-outputs)
- [Task Reference](#task-reference)
- [Sub-Playbooks](#sub-playbooks)
- [Integration Dependencies](#integration-dependencies)
- [Error Handling](#error-handling)

## Overview

<2-4 sentences describing the playbook's purpose, trigger conditions, and expected
outcome. Derive from the playbook description field. If the description is empty
or generic, infer purpose from the task flow and note that the description was inferred.>

## Flow Diagram

` ``mermaid
graph TD
    <generated flowchart following the algorithm above>
` ``

**Note:** This diagram requires a Mermaid-compatible renderer. If your Confluence
instance does not have a Mermaid plugin, paste the diagram source into
mermaid.live to generate an image.

## Playbook Inputs

| Name | Description | Default Value | Required | Source |
|------|-------------|---------------|----------|--------|
| <for each entry in the inputs array> |

<If no inputs are defined, state: "This playbook accepts no inputs.">

## Playbook Outputs

| Name | Description | Type |
|------|-------------|------|
| <for each entry in the outputs array> |

<If no outputs are defined, state: "This playbook produces no outputs.">

## Task Reference

<Document each task in execution order (BFS traversal from starttaskid).
Organize by section when title-type tasks are present.>

### <section name, from title task — or "Main Flow" if no title tasks>

#### <task number>. <task name> (ID: <task key>)

| Property | Value |
|----------|-------|
| Type | <regular / condition / playbook / title / standard> |
| Command | <scriptName or script field, or "Manual" if not a command> |
| Integration | <brand field, or "Built-in" / "N/A"> |
| Continue on Error | <Yes / No> |
| Separate Context | <Yes / No — only for playbook-type tasks> |

**Purpose:** <task description field, or inferred purpose if empty — note when inferred>

**Arguments:**

| Argument | Value / Source |
|----------|---------------|
| <for each entry in scriptarguments — show the key and whether the value is literal, from context, or from an input> |

<Omit the arguments table if scriptarguments is empty or absent.>

**Next Tasks:**
- <branch label> → <target task name> (ID: <target id>)

---

## Sub-Playbooks

| Sub-Playbook Name | Called By Task | Separate Context | Inputs Passed |
|-------------------|---------------|------------------|---------------|
| <for each playbook-type task in the tasks object> |

<If no sub-playbooks are called, state: "This playbook does not call sub-playbooks.">

<If the sub-playbook JSON is available in investigation/playbooks/, note:
"Documentation available — run the documentation workflow on this sub-playbook for details.">

## Integration Dependencies

| Integration | Commands Used | Task(s) |
|-------------|--------------|---------|
| <aggregate from all tasks — group by brand, list distinct commands and which tasks use them> |

<If no integrations are used, state: "This playbook uses only built-in commands.">

## Error Handling

**Tasks with `continueonerror: true`:**
<bulleted list with task name and what happens on error>

**Tasks with explicit error branches:**
<bulleted list showing the error path and where it leads>

**Unhandled failure points:**
<bulleted list of tasks that call external APIs/integrations without error handling — these are risks>

<If error handling is comprehensive, state that and explain why.>
```

---

## Executive Summary Template

Use this template when generating **Executive Summary** documentation:

```markdown
# Playbook Summary: <playbook name>

**Generated:** <date>
**Version:** <version>
**Tasks:** <count> | **Sub-Playbooks:** <count> | **Integrations:** <count>

## Purpose

<1-2 sentences describing what this playbook does and when it runs.>

## High-Level Flow

` ``mermaid
graph TD
    <simplified flowchart — show only:
     - Section headers (title tasks) as nodes
     - Key decision points (condition tasks) as diamonds
     - Sub-playbook calls as double-bordered nodes
     - Start and end nodes
     Skip individual regular/standard tasks — represent them as phases.>
` ``

## Key Decision Points

| Decision | Branches | Criteria |
|----------|----------|----------|
| <condition task name> | <branch names, comma-separated> | <brief description of what determines each branch> |

## Dependencies

**Integrations:** <comma-separated list of unique brands>
**Sub-Playbooks:** <comma-separated list of sub-playbook names>
**Automations:** <comma-separated list of unique scriptNames, excluding integration commands>

## Inputs Required

| Name | Required | Description |
|------|----------|-------------|
| <list only required inputs, or top 5 most important if many are defined> |

<If no inputs, state: "This playbook requires no inputs.">
```

---

## Special Cases

### Sub-Playbooks
- Document the inputs passed to each sub-playbook and whether `separatecontext` is true
- If the sub-playbook's JSON is available in `investigation/playbooks/`, reference it
- If not available, note it and suggest fetching it for complete documentation

### Loops
- Document the `loop` configuration: forEach target, exit condition, max iterations
- Note whether the loop processes items in batch or one at a time

### Timer and Polling Tasks
- Document polling interval, timeout value, and what happens on timeout
- Note whether polling values are configurable (from inputs) or hardcoded

### Manual Tasks
- **Flag clearly** with a **Warning:** callout — these require human intervention
- Document what the operator needs to do and what happens after completion

### Empty Descriptions
- When a task has no `description` field, infer purpose from the command name, script arguments, and position in the flow
- Always note when a description was inferred: *(inferred from command and context)*

### Missing or Incomplete Data
- If the playbook `description` is empty, note it and provide an inferred overview
- If `inputs` or `outputs` arrays are empty, state it explicitly rather than omitting the section
- If task names are generic ("Task #12", "Untitled"), document them as-is and flag as a documentation gap

---

## Data Security

- Never include API keys, credentials, passwords, or tokens in documentation output
- Never include real indicator values (IPs, domains, hashes) from production data
- If playbook JSON contains embedded credentials, redact them and flag the issue
- Do not document incident data, war room entries, or investigation details
- Documentation output goes to `investigation/docs/` which is gitignored
