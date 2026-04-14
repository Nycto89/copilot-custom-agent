# CLAUDE.md

This file is read by Claude Code automatically when you run `claude` in this repo.
It gives Claude context about the project, the person working in it, conventions,
and what it is/isn't allowed to do.

---

## Who Is Working on This

This repo is being built by a developer who will be building Copilot-native custom
agents professionally in the near future. This project is a deliberate at-home
practice environment designed to mirror the structure and patterns used at work
before building the real thing.

**What this means for how you should help:**

- Explain your reasoning, not just your output — this is a learning context
- When you suggest something, say *why* it's the right pattern, not just *what* it is
- Flag when something I've done could cause a problem at work (security, naming,
  structure, or pattern mismatches with enterprise Copilot conventions)
- If I'm about to learn a bad habit, say so directly before proceeding
- Prefer teaching correct patterns over quick fixes

---

## Work Context

This repo mirrors a real enterprise Copilot-native agent project with the following structure:

```
.github/agents/       # Always-on agents
.github/prompts/      # Slash commands
.vscode/mcp.json      # MCP config (not yet in use at work)
agents/               # Agent definitions (agents/<name>/<name>.agent.md)
commands/             # Command definitions
docs/                 # Per-domain documentation
investigation/        # Gitignored scratch space for testing and agent output
rules/                # Guardrail rules (common, cloud, kubernetes)
scripts/              # Python and PowerShell utility scripts
skills/               # Reusable SKILL.md files
templates/            # Agent and skill starter templates
```

**Constraints that apply from the work environment:**

- MCP servers are not available at work yet — do not build workflows that depend on them
- Scripts must be Python or PowerShell only — no Bash, Go, or JavaScript
- All agents must reference `skills/shared-standards/SKILL.md` for tone and label conventions
- Guardrail rules in `rules/` are not optional — agents that touch cloud or k8s configs
  must enforce them, everything else uses common rules
- Never suggest patterns that would require admin-level GitHub permissions for basic
  agent operation

---

## Project Overview

A Copilot-native agent toolkit that automates dev workflow tasks. Current components:

| Component | Location | Status |
|-----------|----------|--------|
| Agent template | `templates/agents/` | ✅ Built |
| Shared standards skill | `skills/shared-standards/` | ✅ Built |
| XSOAR playbook analyst | `agents/xsoar-analyst/` | ✅ Built |
| XSOAR analysis skill | `skills/xsoar-playbook-analysis/` | ✅ Built |
| XSOAR fetch scripts | `scripts/python/` | ✅ Built |
| XSOAR analyst PRD | `docs/xsoar-analyst-prd.md` | ✅ Built |
| Issue triage agent | `agents/triage-agent/` | 🔲 Milestone 1 |
| PR review agent | `agents/pr-review-agent/` | 🔲 Milestone 2 |
| Doc sync agent | `agents/doc-sync-agent/` | 🔲 Milestone 2 |
| Slash commands | `.github/prompts/` | 🔲 Milestone 3 |
| Cloud guardrails | `rules/cloud/` | 🔲 Milestone 4 |
| K8s guardrails | `rules/kubernetes/` | 🔲 Milestone 4 |
| Common guardrails | `rules/common/` | 🔲 Milestone 4 |
| PowerShell scripts | `scripts/powershell/` | 🔲 Milestone 5 |

See `MILESTONES.md` for the full task breakdown and GitHub issues to copy in.

---

## Conventions

- All agents live in `agents/<agent-name>/<agent-name>.agent.md`
- Always-on agents are copied into `.github/agents/`
- Skills live in `skills/<skill-name>/SKILL.md`
- Rules are Markdown files in `rules/<environment>/`
- Scripts follow the pattern: `scripts/<language>/<purpose>.<ext>`
- Shared Python modules (e.g., API clients) live alongside scripts in `scripts/python/`
- New agents must be built from `templates/agents/agent-template.agent.md`
- All agents must reference `skills/shared-standards/SKILL.md` in their frontmatter
- Never commit secrets — use environment variables for all tokens
- `investigation/` is gitignored scratch space — agents write output here (reports, downloads, etc.)
- Agent-specific PRDs and documentation go in `docs/`

---

## What Claude Code Can Do Here

- Read and edit any file in this repo
- Create new agents, skills, rules, and scripts
- Run Python scripts in `scripts/python/`
- Run PowerShell scripts in `scripts/powershell/`
- Suggest improvements to guardrail rules
- Create new files following the conventions above

## What Claude Code Should NOT Do

- Commit or push to git without explicit approval
- Modify `.gitignore` without asking
- Write hardcoded credentials or tokens into any file
- Delete files without confirmation
- Suggest MCP-dependent workflows (not available at work yet)
- Use Bash, Go, or JavaScript for scripts

---

## Testing Agents

Sample issues for testing the triage agent are in `examples/sample-issues/test-issues.md`.
Use `investigation/` as scratch space for any ad-hoc testing — it's gitignored.
Subdirectories under `investigation/` are created per-agent as needed (e.g., `playbooks/`, `reports/`).

---

## Start Here (New Session Prompt)

When starting a new Claude Code session in this repo, run this to orient yourself:

```
Read CLAUDE.md, MILESTONES.md, and the README. Then tell me:
1. Which milestone I should be working on next based on what's already built
2. What the next uncompleted task is
3. Any issues you spot in files that already exist
```

This gives every session a consistent starting point without re-explaining the project.
