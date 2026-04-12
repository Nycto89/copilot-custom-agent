# Commands (Slash Commands)

## What are slash commands?

Slash commands are prompt files stored in `.github/prompts/` that let you trigger
a specific agent behavior by typing `/command-name` in Copilot Chat.

## Format

Commands are Markdown files with a `.prompt.md` extension:

```
.github/prompts/
└── triage.prompt.md     → invoked with /triage
└── review.prompt.md     → invoked with /review
```

## Example command file

```markdown
---
name: triage
description: Triage the current issue — classify, prioritize, and respond.
---

Triage this issue using the triage agent instructions in
agents/triage-agent/triage-agent.agent.md.
Apply appropriate labels and post a structured response.
```

## Commands in this repo

*(Built during Milestone 3)*

| Command | Purpose |
|---------|---------|
| `/triage` | Run issue triage agent on the current issue |
| `/review` | Run PR review agent on the current PR |
| `/sync-docs` | Run doc-sync agent to flag stale documentation |
