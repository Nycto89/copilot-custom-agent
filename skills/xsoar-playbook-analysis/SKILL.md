---
name: xsoar-playbook-analysis
description: >
  XSOAR 6.14 playbook structure knowledge, best practices checklist,
  anti-pattern detection, and report template. Used by the xsoar-analyst
  agent for playbook quality analysis.
---

## XSOAR 6.14 Playbook Schema Reference

A playbook JSON export contains these key top-level fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique playbook identifier |
| `name` | string | Display name |
| `description` | string | Playbook purpose and scope |
| `starttaskid` | string | ID of the entry-point task |
| `tasks` | object | Map of task ID → task definition (the core of the playbook) |
| `inputs` | array | Playbook-level input definitions |
| `outputs` | array | Playbook-level output definitions |
| `view` | object | Visual layout metadata (canvas positions) |
| `version` | number | Playbook version counter |
| `fromversion` | string | Minimum XSOAR version compatibility |

### Task Object Structure

Each entry in `tasks` is keyed by a string task ID and contains:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Task instance ID |
| `taskid` | string | Task definition ID |
| `type` | string | Task type: `regular`, `condition`, `playbook`, `title`, `start`, `standard` |
| `task` | object | Inner task definition (see below) |
| `nexttasks` | object | Map of branch key → list of next task IDs. `#default#` is the default/else branch |
| `conditions` | array | Condition definitions (for `condition` type tasks) |
| `scriptarguments` | object | Arguments passed to the script/command |
| `separatecontext` | boolean | Whether a sub-playbook runs in isolated context |
| `loop` | object | Loop configuration (forEach, exit condition) |
| `continueonerror` | boolean | Whether to continue execution if this task fails |
| `continueonerrortype` | string | Error handling type when `continueonerror` is true |
| `note` | boolean | Whether task output is added to the war room |

### Inner Task Definition (`task.task`)

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name of the task |
| `description` | string | What this task does |
| `script` | string | Full script reference (may include brand prefix) |
| `scriptName` | string | Script/automation name |
| `brand` | string | Integration brand that provides the command |
| `playbookName` | string | Sub-playbook name (for `playbook` type tasks) |
| `type` | string | Inner type classifier |
| `iscommand` | boolean | Whether this executes a command vs manual task |

### Flow Control

- `nexttasks` defines the execution graph. Each key maps to a list of task IDs.
- `#default#` is the default/fallback branch (equivalent to "else").
- Condition tasks have named branches matching condition labels.
- A task with no `nexttasks` is a terminal node.

---

## Analysis Checklist

Evaluate every playbook against these eight categories. For each finding, assign a severity (Critical, High, Medium, Low, Info) using the shared standards taxonomy.

### 1. Error Handling

- **`continueonerror`**: Which tasks have it set? Is it used intentionally or as a blanket suppression?
- **OnError paths**: Do condition tasks include error/failure branches?
- **API-calling tasks**: Do tasks that call external integrations have timeout or retry consideration?
- **Catch-all handler**: Is there a final error handler or cleanup task reachable from failure paths?
- **Silent failures**: Are there tasks where errors are swallowed without logging or notification?

**What good looks like:** Critical integration calls have `continueonerror: true` with explicit error-branch handling that logs the failure and takes corrective action, not just continues silently.

### 2. Hardcoded Values

- **Literal values in `scriptarguments`**: Look for hardcoded IPs, URLs, hostnames, thresholds, email addresses, list names, or indicator values.
- **Should be inputs**: Values that may change between environments (dev/staging/prod) or between tenants should be playbook `inputs`.
- **Should be lists**: Values that represent a set of items (e.g., approved domains, blocked IPs) should reference XSOAR lists, not inline arrays.
- **Magic numbers**: Unexplained numeric thresholds (e.g., `severity > 2`) without documentation.

**What good looks like:** The playbook accepts all environment-specific values as inputs with default values and descriptions. No literal infrastructure references in task arguments.

### 3. Sub-Playbook Decomposition

- **Task count**: Playbooks with >20 tasks should be evaluated for extraction opportunities.
- **Repeated patterns**: Are there sequences of 3+ tasks that appear in multiple places (or could be reused by other playbooks)?
- **`separatecontext`**: Sub-playbooks that don't need parent context should use `separatecontext: true` to avoid context pollution.
- **Input/output mapping**: Are sub-playbook inputs explicitly mapped, or relying on implicit context inheritance?
- **Single responsibility**: Does each sub-playbook do one logical thing, or is it a "helper" that does many unrelated things?

**What good looks like:** Logical units of work are extracted into sub-playbooks. Sub-playbooks use separate context. Inputs and outputs are explicit.

### 4. Polling vs Sleep

- **Sleep/Wait tasks**: Any use of `Sleep` or `Pause` commands with hardcoded durations is a red flag.
- **GenericPolling**: Long-running operations should use `GenericPolling` sub-playbook or built-in polling.
- **Polling configuration**: Are timeout and interval values configurable (inputs) or hardcoded?
- **Timeout handling**: What happens when a polling operation times out? Is there a fallback?

**What good looks like:** No `Sleep` tasks. Long-running operations use polling with configurable timeout and interval. Polling timeouts trigger explicit handling.

### 5. Conditional Logic

- **Default branches**: Do all condition tasks have a `#default#` (else) branch? Missing defaults can cause silent dead-ends.
- **Nesting depth**: Conditions nested more than 3 levels deep are hard to follow and maintain.
- **Expression complexity**: Are condition expressions readable? Complex boolean logic should be simplified or documented.
- **Redundant conditions**: Are there conditions that always evaluate the same way, or that duplicate earlier checks?
- **Dead branches**: Are all condition branches connected to downstream tasks?

**What good looks like:** Every condition has a default branch. Conditions are flat (minimal nesting). Complex logic is documented in task descriptions.

### 6. Documentation Quality

- **Playbook description**: Is the top-level `description` field populated with meaningful content?
- **Task names**: Are tasks named descriptively (e.g., "Enrich indicator via VirusTotal") or generically ("Task #12", "Untitled")?
- **Task descriptions**: Do complex tasks have descriptions explaining their purpose?
- **Input descriptions**: Are playbook inputs documented with descriptions and expected formats?
- **Output descriptions**: Are outputs described so downstream consumers know what they're getting?

**What good looks like:** A new team member can understand the playbook's purpose and flow from names and descriptions alone, without reading every script argument.

### 7. Structure and Readability

- **Section headers**: Are `title`-type tasks used to organize the playbook into logical sections?
- **Linear flow**: Is the task graph unnecessarily branched where a linear sequence would be clearer?
- **Unreachable tasks**: Are there tasks that are not reachable from `starttaskid` via `nexttasks` chains?
- **Entry point**: Does `starttaskid` point to a valid task?
- **Consistent patterns**: Does the playbook follow a consistent pattern (enrich → decide → act → report)?

**What good looks like:** The playbook reads top-to-bottom in logical sections. No orphaned tasks. Clear phases (triage, enrichment, response, closure).

### 8. Performance Considerations

- **Sequential vs parallel**: Are there independent tasks running sequentially that could run in parallel?
- **Loop efficiency**: Are loops processing items one-at-a-time when batch commands are available?
- **Context size**: Are large data objects being stored in context without cleanup? (Context bloat slows execution.)
- **Unnecessary API calls**: Are there redundant calls to the same endpoint for the same data?

**What good looks like:** Independent enrichment tasks run in parallel. Batch commands are used where available. Context keys are cleaned up after use.

---

## Anti-Pattern Reference

| Anti-Pattern | Description | Severity |
|-------------|-------------|----------|
| God Playbook | 50+ tasks doing everything — enrichment, decision, response, notification — in one flat flow | High |
| Sleep Loop | Using `Sleep` + condition check instead of `GenericPolling` or native polling | Medium |
| Hardcoded Infrastructure | Literal server URLs, IPs, or API endpoints in task arguments | High |
| Silent Error Swallowing | `continueonerror: true` with no error-branch handling | Critical |
| Context Pollution | Sub-playbooks running without `separatecontext: true`, leaking variables into parent | Medium |
| Orphan Tasks | Tasks not reachable from any execution path | Low |
| Missing Default Branch | Condition tasks without `#default#`, causing potential dead-ends | High |
| Unnamed Tasks | Tasks left as "Task #N" or "Untitled" with no description | Medium |
| Duplicate Logic | Same sequence of tasks repeated instead of extracted to a sub-playbook | Medium |
| Unused Inputs/Outputs | Input or output definitions that are never referenced in tasks | Low |
| Over-Permissive Loops | Loops without exit conditions or with unreasonably high iteration limits | High |
| No Cleanup | Large context keys created during execution but never deleted | Low |

---

## Report Template

When writing an analysis report to `investigation/reports/`, use this structure:

```markdown
# Playbook Analysis: <playbook name>

**Analyzed:** <date>
**Version:** <playbook version if available>
**Total Tasks:** <count>
**Sub-Playbooks Referenced:** <count and names>

## Summary

<2-3 sentence overall assessment. Lead with the most important finding.>

## Severity Summary

| Severity | Count |
|----------|-------|
| Critical | N |
| High     | N |
| Medium   | N |
| Low      | N |
| Info     | N |

## Findings

### Error Handling
<findings or "No issues found">

### Hardcoded Values
<findings or "No issues found">

### Sub-Playbook Decomposition
<findings or "No issues found">

### Polling Patterns
<findings or "No issues found">

### Conditional Logic
<findings or "No issues found">

### Documentation
<findings or "No issues found">

### Structure and Readability
<findings or "No issues found">

### Performance
<findings or "No issues found">

## Recommendations

Prioritized list of recommended changes, starting with the highest-impact items.

1. **[Severity]** <recommendation>
2. **[Severity]** <recommendation>
3. ...
```

---

## Data Security

- Never request, fetch, or display incident data, war room entries, evidence, or investigation details
- Never include API keys, credentials, or tokens in analysis output
- If playbook JSON contains embedded credentials (which it should not), redact them and flag the issue
- Analysis reports must not contain real indicator values (IPs, domains, hashes) from production data
- The fetch-integrations script strips credentials automatically — do not circumvent this
