# Skills

## What is a skill?

A skill is a `SKILL.md` file containing reusable instructions that multiple agents
can reference. Instead of duplicating logic across agent files, you extract it into
a skill and reference it in each agent's frontmatter.

## When to create a skill

Create a skill when:
- Two or more agents share the same instructions
- A set of rules is complex enough to deserve its own file
- You want to update shared behavior in one place

## Referencing a skill

In your agent's frontmatter:

```yaml
skills:
  - ../../skills/shared-standards/SKILL.md
  - ../../skills/security-checklist/SKILL.md
```

## Skills in this repo

| Skill | Purpose |
|-------|---------|
| `skills/shared-standards/` | Tone, label conventions, security baseline |

## Skill file format

```markdown
---
name: Skill Name
description: >
  What this skill provides and which agents should use it.
---

# Skill Name

[Instructions, checklists, standards, or reference material]
```
