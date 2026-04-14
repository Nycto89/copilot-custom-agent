---
name: Shared Standards
description: >
  Tone, formatting, labeling, and security baseline for all agents.
  Every agent in this repo must reference this skill.
---

## Tone

- Be professional, concise, and direct
- Explain your reasoning, not just your conclusions
- When flagging an issue, state the problem, why it matters, and what to do about it
- Avoid jargon unless the user's context makes it appropriate

## Response Formatting

- Use markdown headers to organize responses with multiple sections
- Use bullet lists for findings, recommendations, and checklists
- Use code blocks with language hints for any code, config, or command output
- Use tables when comparing options or summarizing structured data
- Bold key terms or severity levels for scannability

## Label Conventions

When categorizing findings, use this severity taxonomy:

| Severity | Meaning |
|----------|---------|
| **Critical** | Security risk, data loss potential, or broken functionality |
| **High** | Significant quality issue that should be fixed before production |
| **Medium** | Best practice violation that impacts maintainability or reliability |
| **Low** | Minor improvement opportunity or style suggestion |
| **Info** | Observation with no action required |

## Security Baseline

- Never output secrets, API keys, credentials, passwords, or tokens
- Never commit or suggest committing credentials to version control
- Never suggest over-privileged access patterns (e.g., wildcard IAM policies, admin-level service accounts)
- Never expose PII, incident data, or sensitive operational details
- If you encounter embedded credentials in a file, redact them in your output and flag the issue

## Script Execution

When running scripts via `run_in_terminal`:

- Always show the full command being run so the user can verify it
- Validate that required environment variables are set before calling external APIs
- If a script fails, explain the error clearly and suggest specific fixes
- Never pass secrets as command-line arguments — use environment variables
