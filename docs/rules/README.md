# Rules & Guardrails

## What are guardrails?

Guardrails are Markdown rule files that define behavioral constraints for AI agents.
They prevent agents from suggesting insecure configurations, over-privileged access,
or actions that violate enterprise security policy.

## Rule files in this repo

| File | Scope |
|------|-------|
| `rules/common/common-guardrails.md` | All enterprise environments |
| `rules/cloud/guardrails.md` | AWS, Azure, GCP |
| `rules/kubernetes/k8s-guardrails.md` | Kubernetes and OpenShift |

## How agents use rules

Reference a rule file in an agent's instructions:

```markdown
Before suggesting any cloud configuration changes, review and apply
the constraints in rules/cloud/guardrails.md.
```

Or reference it as a skill if the same rules apply to multiple agents.

## Updating guardrails

When you add a new rule:
1. Add it to the appropriate file under `rules/`
2. Update any agent instructions that reference that rule file
3. Test with a sample PR or issue that would trigger the new rule
