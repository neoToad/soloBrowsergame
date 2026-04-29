# .docs Documentation Guide

## Purpose
- `.docs/` stores project documentation for engineering decisions, operational status, and content authoring references.
- Normative docs define rules and constraints implementation must follow.
- Reference/status docs describe current state, audits, and backlog and may drift unless periodically verified.

## Document Index

| Document | Type | Purpose |
|---|---|---|
| `ARCHITECTURE.md` | Normative | Source-of-truth for architecture rules, invariants, and service boundaries. |
| `STAT_NAMING_POLICY.md` | Normative | Canonical naming and terminology policy for stats and system labels. |
| `ENDPOINT_RESPONSE_CONTRACT.md` | Normative | Response/event contract for endpoints and UI integration expectations. |
| `PROJECT_CONTEXT.md` | Reference | High-level onboarding snapshot of project scope and current structure. |
| `CURRENT_TASK.md` | Status | Active work log and current execution status. |
| `test-audit.md` | Audit | Point-in-time QA/test coverage findings and validation notes. |
| `refactor-inventory.md` | Backlog (Refactor) | Structural/code-organization improvements. |
| `tech-debt-register.md` | Backlog (Debt/Risk) | Workarounds, shortcuts, missing safeguards, and risk debt. |
| `QUEST_AUTHORING_COMPLETE.md` | Content Index | Entry point and read order for quest authoring documentation. |
| `QUEST_AUTHORING_RULES.md` | Content Reference | Structural quest authoring rules (models, mechanics, constraints). |
| `QUEST_AUTHORING_PATTERNS.md` | Content Reference | Authoring patterns, examples, and common mistakes checklist. |
| `QUEST_CONTENT_GUIDE.md` | Content Reference | Prose/tone/voice standards for quest writing. |
| `WORLD_LORE.md` | Content Index | Entry point for world/lore documentation. |
| `WORLD_LORE_CORE.md` | Content Reference | Canonical city/faction/lore context. |
| `WORLD_LORE_REFERENCE.md` | Content Reference | Hubs, characters, contacts, items, and enemy reference data. |
| `quest_tracking.xlsx` | Tracking Source | Spreadsheet source for quest tracking. |
| `quest_tracking.md` | Tracking Mirror | Diff-friendly text mirror of quest tracking spreadsheet. |

## Ownership and Update Cadence
Each core doc should include this metadata block near the top:

```md
- Owner: <role or team>
- Update Trigger: <when this must be updated>
- Last Verified Against Code: YYYY-MM-DD
```

Recommended defaults:
- `ARCHITECTURE.md`: update on architecture/service-boundary changes.
- `PROJECT_CONTEXT.md`: update after major feature/module changes.
- `CURRENT_TASK.md`: update at every meaningful task checkpoint.
- `ENDPOINT_RESPONSE_CONTRACT.md`: update when response schema or event semantics change.
- `STAT_NAMING_POLICY.md`: update when naming conventions evolve.
- Audit/backlog docs: update when new findings are confirmed or resolved.

## Backlog Policy
- New findings from audits (`test-audit.md`, ad hoc investigations) must be converted into actionable entries in either:
  - `refactor-inventory.md` for structure/organization changes.
  - `tech-debt-register.md` for risk/debt/workaround/missing safeguards.
- Active implementation status belongs in `CURRENT_TASK.md`, not in audit docs.
- Completed backlog items should be removed or explicitly marked resolved with a date.
