# Agents

## What is an agent?

An agent is an `.agent.md` file that defines an AI assistant's name, description, available tools, referenced skills, and behavioral instructions. Copilot reads the frontmatter to understand when and how to invoke the agent.

## Agent locations

| Location | Purpose |
|----------|---------|
| `agents/<name>/` | Primary agent definitions |
| `.github/agents/` | Always-on agents — Copilot loads these automatically |

To make an agent "always on", copy or symlink its `.agent.md` into `.github/agents/`.

## Frontmatter fields

```yaml
---
name: Agent Name               # Display name shown in Copilot
description: >                 # What the agent does and when to invoke it
  One or two sentences.
tools:                         # Tools the agent can use
  - read_file
  - list_files
  - edit_file
  - run_in_terminal
  - github
skills:                        # Relative paths to SKILL.md files
  - ../../skills/shared-standards/SKILL.md
---
```

## Creating a new agent

1. Copy `templates/agents/agent-template.agent.md` to `agents/<your-agent>/`
2. Fill in the frontmatter and instructions
3. Test against sample inputs in `investigation/`
4. If it should run automatically, copy to `.github/agents/`
