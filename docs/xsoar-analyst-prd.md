# XSOAR Playbook Analyst Agent — Product Requirements Document

## Problem Statement

Manual playbook review in Cortex XSOAR is slow, inconsistent, and depends on tribal knowledge. As the SOC automation library grows, playbook quality varies widely. Common issues — silent error swallowing, hardcoded values, poor documentation, and monolithic "god playbooks" — degrade reliability and make maintenance difficult. There is no systematic way to audit playbook quality against established best practices.

## Target User

SOC automation developers maintaining and building XSOAR playbooks in a financial institution environment. Users are technically sophisticated, familiar with XSOAR task types and the playbook editor, and work primarily in VS Code.

## Solution

A GitHub Copilot custom agent that:
1. Fetches playbook definitions from the XSOAR REST API
2. Analyzes them against an 8-category best practices checklist
3. Produces both conversational feedback in Copilot Chat and structured markdown reports

The agent runs entirely within VS Code using GitHub Copilot Chat (GPT-4.1) with `run_in_terminal` for script execution. No external services, no MCP servers, no cloud dependencies beyond the XSOAR API itself.

## Scope

### Phase 1 — Analyze (Current)
- Fetch playbooks by name or ID from XSOAR 6.14 REST API
- Fetch automations and integrations for supporting context
- Analyze playbooks against 8 best-practice categories
- Produce chat summaries and written reports
- Credential stripping on all integration metadata

### Phase 1.5 — Document (Current)
- Generate Confluence Data Center wiki-ready documentation from playbook JSON
- Configurable detail levels: Full Deep-Dive (task-by-task) or Executive Summary
- Mermaid.js flowchart generation from the playbook task graph
- Grouped/collapsed diagrams for large playbooks (30+ tasks)
- Documentation output to `investigation/docs/`

### Phase 1.6 — Document Full Workflow (Current)
- Recursive fetch of a root playbook's entire dependency tree (sub-playbooks, automations, integrations)
- One-shot fetch of reference catalogs (incident fields, indicator types) for cross-linking, tolerant of limited-permission API keys
- Cycle-safe via visited-set; unlimited depth
- Linked document set with cross-references — shared components documented once and referenced from every consumer
- Per-workflow output folder: `investigation/docs/<root>/` with `README.md`, `glossary.md`, `playbooks/`, `automations/`, `integrations/` subfolders
- README includes a **runbook narrative** (3–5 prose paragraphs walking trigger → phases → decisions → outcomes → operator interventions) plus dependency graph, component tables, incident-fields-used table, and cross-reference index
- Per-playbook docs include a task-by-task walkthrough, decision map, manual-task catalog, loops/polling, and error-handling surface — not just a high-level summary
- Per-automation docs surface execution environment (docker image, run-as, run-once, sensitive, tags) and invocation sites (which playbook tasks call them with which arguments)
- Per-integration docs render a full per-command reference with argument schemas, output schemas, and invocation sites for every command used in the workflow
- `glossary.md` defines every XSOAR concept the docs use, linked from first occurrence — supports mixed SOC audience (engineers + analysts + managers)
- Manifest JSON drives doc generation and link resolution, with `tasks_by_id`, `invocations[]`, `command_schemas{}`, `workflow_incident_fields`, and `reference_catalogs` surfaces

### Phase 2 — Refactor (Future)
- Suggest specific code changes to fix identified issues
- Generate refactored playbook YAML/JSON
- Extract sub-playbooks from god playbooks
- Replace sleep loops with polling patterns

### Phase 3 — Create (Future)
- Generate new playbooks from natural language prompts
- Follow established patterns and reference existing sub-playbooks
- Wire up integrations and automations from the environment
- Apply all best practices from Phase 1 analysis

---

## Architecture

```
VS Code + GitHub Copilot Chat (GPT-4.1)
    |
    |--- Copilot Agent: xsoar-analyst.agent.md
    |       |
    |       |--- Skill: shared-standards/SKILL.md (tone, formatting, security)
    |       |--- Skill: xsoar-playbook-analysis/SKILL.md (domain knowledge)
    |       |--- Skill: xsoar-playbook-documentation/SKILL.md (single-playbook doc generation)
    |       |--- Skill: xsoar-workflow-documentation/SKILL.md (linked workflow doc set)
    |       |
    |       |--- Tool: run_in_terminal → Python fetch scripts
    |       |--- Tool: read_file → Read downloaded playbook JSON
    |       |--- Tool: edit_file → Write analysis reports
    |       |--- Tool: list_files → Browse investigation/ directory
    |
    |--- Python Scripts (scripts/python/)
    |       |--- xsoar_client.py (shared API client)
    |       |--- fetch-playbook.py
    |       |--- fetch-automations.py
    |       |--- fetch-integrations.py
    |       |--- fetch-workflow.py (recursive dependency crawler, writes manifest)
    |
    |--- Local Storage (investigation/ — gitignored)
            |--- playbooks/    (downloaded playbook JSON)
            |--- automations/  (downloaded automation JSON)
            |--- integrations/ (sanitized integration JSON)
            |--- reference/    (one-shot catalogs: incident fields, indicator types)
            |--- reports/      (analysis report markdown)
            |--- docs/         (playbook documentation markdown)
            |     |--- <root>/ (per-workflow folder: README.md, glossary.md, manifest.json, playbooks/, automations/, integrations/)
```

---

## Component Inventory

| File | Purpose | Dependencies |
|------|---------|-------------|
| `agents/xsoar-analyst/xsoar-analyst.agent.md` | Agent definition — role, workflow, constraints, output format | Both skills |
| `skills/shared-standards/SKILL.md` | Repo-wide tone, formatting, security baseline | None |
| `skills/xsoar-playbook-analysis/SKILL.md` | XSOAR 6.14 schema reference, 8-category analysis checklist, anti-patterns, report template | None |
| `skills/xsoar-playbook-documentation/SKILL.md` | Confluence DC doc templates (full + summary), mermaid generation algorithm, formatting guidelines | None |
| `skills/xsoar-workflow-documentation/SKILL.md` | Linked workflow doc set — overview template, per-component templates, cross-reference rules, dependency diagram generation | `xsoar-playbook-documentation` |
| `scripts/python/xsoar_client.py` | Shared XSOAR REST API client — auth, headers, error handling, file I/O | `requests` |
| `scripts/python/fetch-playbook.py` | Fetch playbook by name or ID, save to investigation/playbooks/ | `xsoar_client` |
| `scripts/python/fetch-automations.py` | Fetch automations by name, ID, or playbook reference | `xsoar_client` |
| `scripts/python/fetch-integrations.py` | Fetch integration metadata with credential stripping | `xsoar_client` |
| `scripts/python/fetch-workflow.py` | Recursive dependency crawler — fetches root playbook's entire tree, writes manifest.json | `xsoar_client` |
| `scripts/python/requirements.txt` | Python dependencies | None |
| `templates/agents/agent-template.agent.md` | Generic agent template for creating new agents | None |

---

## XSOAR API Endpoints

All endpoints are relative to `XSOAR_URL`. Authentication is via the `Authorization` header with the API key value.

### Playbooks

**Search by name:**
```
POST /playbook/search
Content-Type: application/json

{
    "query": "name:\"Playbook Name\"",
    "page": 0,
    "size": 5
}
```

Response contains `playbooks` array with full playbook definitions.

**Get by ID:**
```
GET /playbook/{playbook-id}
```

Returns the full playbook JSON directly.

### Automations

**Search by name:**
```
POST /automation/search
Content-Type: application/json

{
    "query": "name:\"AutomationName\"",
    "page": 0,
    "size": 5
}
```

Response contains `scripts` array.

### Integrations

**Search by name:**
```
POST /settings/integration/search
Content-Type: application/json

{
    "query": "name:\"Integration Name\"",
    "page": 0,
    "size": 5
}
```

Response contains `configurations` array. **Credential fields must be stripped before saving.**

### Connection Validation

```
GET /user
```

Returns current user info. Used to verify API key is valid.

---

## Security Controls

| Control | Implementation |
|---------|---------------|
| No hardcoded credentials | All auth via `XSOAR_URL` and `XSOAR_API_KEY` environment variables |
| Credential stripping | `fetch-integrations.py` removes password, apikey, token, secret, and hidden fields before writing |
| No incident data access | Agent constraints explicitly prohibit fetching `/incidents`, `/evidence`, `/entry` endpoints |
| Gitignored scratch space | `investigation/` directory is in `.gitignore` — no playbook data committed to the repo |
| Agent-level enforcement | Agent instructions and skill both state data security rules |
| No secrets in arguments | Scripts read credentials from env vars, never accept them as CLI arguments |

---

## Environment Requirements

| Requirement | Details |
|-------------|---------|
| IDE | VS Code with GitHub Copilot extension |
| Copilot Plan | Copilot Pro or higher with agent mode enabled |
| LLM | GPT-4.1 (unlimited via enterprise Copilot) |
| Python | 3.8+ with `requests` library (`pip install -r scripts/python/requirements.txt`) |
| XSOAR | Version 6.14 with REST API access enabled |
| API Key | XSOAR API key with read permissions for playbooks, automations, and integrations |
| Network | Connectivity from the dev machine to the XSOAR server |
| SSL | If using self-signed certs, set `XSOAR_VERIFY_SSL=false` |

### Environment Variable Setup

```bash
# Linux/Mac
export XSOAR_URL="https://xsoar.example.com"
export XSOAR_API_KEY="your-api-key-here"

# Windows PowerShell
$env:XSOAR_URL = "https://xsoar.example.com"
$env:XSOAR_API_KEY = "your-api-key-here"

# Optional: disable SSL verification for self-signed certs
export XSOAR_VERIFY_SSL="false"
```

---

## Analysis Categories

The agent evaluates playbooks against these 8 categories (full details in the analysis skill):

| # | Category | Key Checks |
|---|----------|-----------|
| 1 | Error Handling | `continueonerror` usage, OnError paths, timeout handling, catch-all handlers |
| 2 | Hardcoded Values | Literal IPs/URLs/thresholds in `scriptarguments`, missing inputs |
| 3 | Sub-Playbook Decomposition | Task count >20, `separatecontext`, I/O mapping, single responsibility |
| 4 | Polling vs Sleep | `Sleep` tasks, `GenericPolling` usage, configurable timeouts |
| 5 | Conditional Logic | Missing `#default#` branches, nesting depth, dead branches |
| 6 | Documentation | Playbook description, task names, input/output descriptions |
| 7 | Structure/Readability | Section headers, unreachable tasks, consistent flow patterns |
| 8 | Performance | Sequential vs parallel tasks, loop batching, context cleanup |

---

## Success Criteria — Phase 1 (Analyze)

- [ ] Python scripts successfully connect to XSOAR and fetch playbook data
- [ ] Agent can be invoked in Copilot Chat and understands the workflow
- [ ] Agent fetches a named playbook via `run_in_terminal`
- [ ] Agent reads the playbook JSON and analyzes against all 8 categories
- [ ] Agent produces a conversational summary in chat with severity ratings
- [ ] Agent writes a structured markdown report to `investigation/reports/`
- [ ] Integration metadata has all credentials stripped
- [ ] No incident data or secrets appear in any output
- [ ] Agent can fetch and reference automations/integrations for supporting context

## Success Criteria — Phase 1.5 (Document)

- [ ] Agent correctly routes "document" vs "analyze" requests
- [ ] Agent generates Full Deep-Dive documentation with all template sections
- [ ] Agent generates Executive Summary documentation when requested
- [ ] Mermaid flowchart is valid and renders in mermaid.live
- [ ] Large playbooks (30+ tasks) produce grouped/collapsed mermaid diagrams
- [ ] Documentation renders cleanly when pasted into Confluence Data Center
- [ ] Documentation is written to `investigation/docs/`
- [ ] Ambiguous prompts trigger a clarifying question
- [ ] No credentials or incident data appear in documentation output

## Success Criteria — Phase 1.6 (Document Full Workflow)

- [ ] `fetch-workflow.py` recursively walks sub-playbooks and produces a valid `manifest.json`
- [ ] Cycle detection prevents infinite loops on self-referencing or shared sub-playbooks
- [ ] All automations referenced anywhere in the tree are fetched (name-resolution failures are skipped, not fatal)
- [ ] All integrations referenced anywhere in the tree are fetched with credentials stripped
- [ ] Reference catalogs (`/incidentfields`, `/indicatortype`) fetch into `investigation/reference/` with graceful degradation on 4xx (status recorded, crawl continues)
- [ ] Manifest contains `tasks_by_id`, `invocations[]`, `command_schemas{}`, `workflow_incident_fields`, and `reference_catalogs` for every applicable record
- [ ] Agent correctly routes "workflow" / "comprehensive" / "dependency tree" prompts
- [ ] Linked doc set produced under `investigation/docs/<root>/` with README, glossary, manifest, and the three subfolders
- [ ] README includes a runbook narrative (3–5 paragraphs) covering trigger, main phases, key decisions, terminal outcomes, and operator interventions
- [ ] Per-playbook docs include task-by-task walkthrough (every task in execution order), decision map, manual-task catalog, loops/polling, error-handling surface, and outputs table
- [ ] Per-automation docs surface execution environment fields and invocation sites for every calling task
- [ ] Per-integration docs render a per-command subsection with full argument and output schemas for every command in `commands_used`
- [ ] `glossary.md` is present and every first-occurrence XSOAR term in the doc set links to it
- [ ] Every relative link in generated docs resolves to a file in the output folder (no broken links)
- [ ] Components missing from the manifest render as bold text with "external/builtin" annotation, not as links
- [ ] Unauthorized reference catalogs degrade gracefully — incident-field tables fall back to CLI names only, no broken links
- [ ] README dependency diagram renders in mermaid.live
- [ ] Doc set renders cleanly in Confluence DC when the folder is uploaded with its structure preserved

---

## Future Phase Sketches

### Phase 2 — Refactor
- Agent suggests specific changes per finding (e.g., "extract tasks 5-12 into a sub-playbook called X")
- Agent generates modified playbook JSON that can be imported back into XSOAR
- New skill: `xsoar-playbook-refactoring/SKILL.md` with transformation patterns
- New script: `push-playbook.py` to upload modified playbooks via the API (with confirmation)

### Phase 3 — Create
- Agent generates new playbooks from natural language descriptions
- Queries existing automations and integrations to wire up commands
- Applies all Phase 1 best practices by default
- New skill: `xsoar-playbook-generation/SKILL.md` with playbook templates and patterns
- Output: importable playbook JSON ready for XSOAR upload
