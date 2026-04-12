# 🏁 Milestones & GitHub Issues

Create these milestones in your repo first: **Issues → Milestones → New Milestone**
Then copy each issue below into the matching milestone.

---

## Milestone 1 — Foundation

> **Goal:** Environment set up, first agent working, understand the .agent.md schema

---

**Issue 1.1 — Environment Setup**
```
Title: [M1] Set up Copilot Pro and enable Claude agent
Labels: setup, milestone-1

## Tasks
- [ ] Subscribe to GitHub Copilot Pro ($10/mo) or higher
- [ ] Install GitHub Copilot extension in VS Code
- [ ] Enable Claude agent: GitHub Settings → Copilot → Coding agent → Partner Agents → Claude: On
- [ ] Enable `github.copilot.chat.claudeAgent.enabled` in VS Code settings
- [ ] Clone this repo and open in VS Code
- [ ] Verify Claude and Copilot both appear in the Agent Sessions view

## Definition of Done
Both agents appear and are selectable in VS Code Agent Sessions.
```

---

**Issue 1.2 — Learn the .agent.md Schema**
```
Title: [M1] Study .agent.md structure and frontmatter options
Labels: learning, milestone-1

## Tasks
- [ ] Read docs/agents/README.md in this repo
- [ ] Read the Agent Skills docs: https://code.visualstudio.com/docs/copilot/customization/agent-skills
- [ ] Open agents/triage-agent/triage-agent.agent.md and read each section
- [ ] Open templates/agents/agent-template.agent.md — understand what each field does
- [ ] Note key concepts in docs/agent-notes.md

## Definition of Done
You can explain what name, description, tools, and skills each do in frontmatter.
```

---

**Issue 1.3 — Test the Triage Agent**
```
Title: [M1] Test triage agent against sample issues
Labels: build, milestone-1

## Tasks
- [ ] Create 3–5 issues in your repo using examples/sample-issues/test-issues.md
- [ ] Trigger the agent: assign the issue to @claude or use the Agents tab
- [ ] Observe: correct label? Useful response? Right priority?
- [ ] Iterate on agent instructions until 3 issues are triaged correctly
- [ ] Log what you changed and why in docs/agent-notes.md

## Definition of Done
Agent correctly triages at least 3 sample issues with labels and structured response.
```

---

## Milestone 2 — Multi-Agent + Skills

> **Goal:** Two more agents, then extract shared logic into a reusable skill

---

**Issue 2.1 — PR Review Agent**
```
Title: [M2] Build a PR review agent
Labels: build, milestone-2

## Tasks
- [ ] Copy templates/agents/agent-template.agent.md to agents/pr-review-agent/
- [ ] Agent should flag: missing tests, hardcoded secrets, unclear variable names
- [ ] Reference skills/shared-standards/SKILL.md in frontmatter
- [ ] Open a test PR (even a trivial change), trigger the agent, review comments
- [ ] Compare Copilot vs Claude on the same PR — log differences in docs/agent-notes.md

## Definition of Done
Agent leaves at least 3 meaningful review comments on a test PR.
```

---

**Issue 2.2 — Doc Sync Agent**
```
Title: [M2] Build a doc-sync agent
Labels: build, milestone-2

## Tasks
- [ ] Copy template to agents/doc-sync-agent/
- [ ] Agent should: identify changed files in a PR, find related docs, flag stale ones
- [ ] Test by making a code change without updating docs, then triggering the agent
- [ ] Log what it catches (and misses) in docs/agent-notes.md

## Definition of Done
Agent correctly flags at least one stale doc after a simulated code change.
```

---

**Issue 2.3 — Extract Shared Skills**
```
Title: [M2] Refine shared skill and remove duplicated instructions
Labels: build, milestone-2

## Tasks
- [ ] Review triage, PR review, and doc-sync agents side by side
- [ ] Identify duplicated instructions (tone, labels, security rules)
- [ ] Update skills/shared-standards/SKILL.md with anything missing
- [ ] Remove the duplicated content from each agent file
- [ ] Re-test all three agents to confirm behavior is unchanged
- [ ] Log what you extracted in docs/agent-notes.md

## Definition of Done
Shared logic lives only in SKILL.md. At least two agents reference it.
No duplicated instructions remain across agent files.
```

---

## Milestone 3 — Commands (Slash Commands)

> **Goal:** Build slash commands in .github/prompts/ so agents are one keystroke away

---

**Issue 3.1 — Learn the .prompt.md Format**
```
Title: [M3] Study slash command format and create /triage
Labels: learning, build, milestone-3

## Tasks
- [ ] Read docs/commands/README.md
- [ ] Create .github/prompts/triage.prompt.md that invokes your triage agent
- [ ] Test: type /triage in Copilot Chat and confirm it triggers correctly
- [ ] Adjust the prompt until behavior matches direct agent invocation

## Definition of Done
/triage in Copilot Chat produces the same output as directly assigning the agent.
```

---

**Issue 3.2 — Add /review and /sync-docs Commands**
```
Title: [M3] Create /review and /sync-docs slash commands
Labels: build, milestone-3

## Tasks
- [ ] Create .github/prompts/review.prompt.md → invokes PR review agent
- [ ] Create .github/prompts/sync-docs.prompt.md → invokes doc-sync agent
- [ ] Test both commands
- [ ] Update docs/commands/README.md with actual command behaviors

## Definition of Done
All three slash commands work and are documented.
```

---

## Milestone 4 — Guardrails

> **Goal:** Understand and practice writing security guardrail rules

---

**Issue 4.1 — Study Existing Guardrails**
```
Title: [M4] Review and understand the guardrail rule files
Labels: learning, milestone-4

## Tasks
- [ ] Read rules/common/common-guardrails.md
- [ ] Read rules/cloud/guardrails.md
- [ ] Read rules/kubernetes/k8s-guardrails.md
- [ ] Read docs/rules/README.md
- [ ] For each rule file: identify 2-3 rules that apply most to your work context
- [ ] Note in docs/agent-notes.md: which rules you'd want to enforce at work

## Definition of Done
You can explain the purpose and scope of each rule file without looking at it.
```

---

**Issue 4.2 — Wire Guardrails Into an Agent**
```
Title: [M4] Add guardrail enforcement to PR review agent
Labels: build, milestone-4

## Tasks
- [ ] Update agents/pr-review-agent/ to reference and enforce cloud guardrails
- [ ] Create a test PR that violates at least one rule (e.g. S3 bucket with public access)
- [ ] Confirm the agent flags the violation and suggests a compliant fix
- [ ] Log how well it caught violations in docs/agent-notes.md

## Definition of Done
Agent correctly identifies and comments on at least one guardrail violation in a test PR.
```

---

**Issue 4.3 — Write a New Guardrail Rule**
```
Title: [M4] Write at least one new guardrail rule from scratch
Labels: build, milestone-4

## Tasks
- [ ] Think about your work environment — what's a risk not yet covered?
- [ ] Write the rule in the appropriate rules/ file (or create a new one)
- [ ] Test it by creating a scenario that triggers it
- [ ] Document the reasoning in docs/rules/README.md

## Definition of Done
New rule is in place, tested, and documented.
```

---

## Milestone 5 — Scripts

> **Goal:** Build Python and PowerShell utility scripts that agents can invoke

---

**Issue 5.1 — Python: Label Audit Script**
```
Title: [M5] Write a Python script to audit issue labels
Labels: build, milestone-5

## Tasks
- [ ] Write scripts/python/audit-labels.py
- [ ] Script should: query GitHub API, list issues missing required labels, output a report
- [ ] Test against your repo
- [ ] Update .claude/settings.json to allow Claude Code to run it
- [ ] Document usage in a docstring

## Definition of Done
Script runs cleanly and produces a correct label audit report.
```

---

**Issue 5.2 — PowerShell: Environment Validation Script**
```
Title: [M5] Write a PowerShell script to validate local dev environment
Labels: build, milestone-5

## Tasks
- [ ] Write scripts/powershell/validate-env.ps1
- [ ] Script should: check for required tools (git, gh CLI, node, python), 
      verify env vars are set (GITHUB_TOKEN), and report pass/fail per check
- [ ] Test on your local machine
- [ ] Document expected output in script comments

## Definition of Done
Script runs on Windows and correctly reports environment readiness.
```

---

## Milestone 6 — Claude Code

> **Goal:** Use Claude Code for autonomous multi-file edits

---

**Issue 6.1 — Install and Explore Claude Code**
```
Title: [M6] Set up Claude Code CLI and explore the repo
Labels: setup, milestone-6

## Tasks
- [ ] Install: npm install -g @anthropic-ai/claude-code
- [ ] Authenticate with your Anthropic account
- [ ] Run `claude` in this repo
- [ ] Ask it to explain the repo structure — verify it reads CLAUDE.md
- [ ] Ask it to suggest one improvement — review the diff
- [ ] Log first impressions vs Copilot agent in docs/agent-notes.md

## Definition of Done
Claude Code reads the full repo structure, references CLAUDE.md, and proposes a valid change.
```

---

**Issue 6.2 — Autonomous Doc Update Workflow**
```
Title: [M6] Use Claude Code to apply doc updates from agent findings
Labels: build, milestone-6

## Tasks
- [ ] Use doc-sync agent (M2) to identify a stale doc
- [ ] Hand the finding to Claude Code: "Update docs/X based on changes in Y"
- [ ] Review the diff — approve or reject changes
- [ ] Practice the human-in-the-loop review flow
- [ ] Log: when to trust it, when to intervene

## Definition of Done
Claude Code successfully updates at least one doc based on a code change, with your review.
```

---

## Milestone 7 — Polish & Demo

> **Goal:** Clean everything up, finalize learnings, prepare work demo

---

**Issue 7.1 — Finalize Learning Log**
```
Title: [M7] Complete docs/agent-notes.md
Labels: docs, milestone-7

## Tasks
- [ ] Review all milestone entries in docs/agent-notes.md
- [ ] Add a "Key Takeaways" section at the top
- [ ] Note which patterns you're bringing to work agents
- [ ] Note any surprises or gotchas

## Definition of Done
agent-notes.md is clean, complete, and useful as a work reference.
```

---

**Issue 7.2 — Demo Prep**
```
Title: [M7] Prepare work demo
Labels: demo, milestone-7

## Tasks
- [ ] Pick your strongest agent (triage or PR review) to demo
- [ ] Write a 2-minute walkthrough script
- [ ] Update docs/workflows/README.md with your end-to-end workflow
- [ ] Record a screen capture or prepare live demo
- [ ] Share repo link with team

## Definition of Done
You can demo a working agent pipeline to a colleague in under 5 minutes.
```
