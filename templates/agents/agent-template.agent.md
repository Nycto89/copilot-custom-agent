---
# Required: A short, human-readable name for this agent.
# This appears in Copilot Chat when the agent is invoked.
name: Agent Name Here

# Required: A one-line description of what this agent does.
# Copilot uses this to decide when to suggest this agent.
description: >
  Describe the agent's purpose in one sentence.

# Required: The tools this agent is allowed to use.
# Common options:
#   - run_in_terminal    (execute shell commands / scripts)
#   - read_file          (read file contents)
#   - edit_file          (create or modify files)
#   - list_files         (list directory contents)
tools:
  - run_in_terminal
  - read_file

# Required: Skills this agent references for shared instructions.
# Every agent must include shared-standards at minimum.
skills:
  - ../../skills/shared-standards/SKILL.md
---

## Role

<!-- What is this agent? Who does it serve? What domain does it operate in? -->

You are a [role] that helps [target users] with [domain/task].

## Instructions

<!-- Step-by-step behavioral instructions. Be specific about the workflow. -->

When the user asks you to [primary task]:

1. [First step]
2. [Second step]
3. [Third step]
4. Present your findings clearly

## Constraints

<!-- Hard boundaries the agent must never cross. -->

- Never [unsafe action]
- Always [required behavior]
- Do not [out-of-scope action]

## Output Format

<!-- How the agent should structure its responses. -->

Respond with:
- A brief summary of your findings
- Detailed analysis organized by category
- Actionable recommendations prioritized by impact
