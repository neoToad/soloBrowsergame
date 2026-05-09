# .docs Documentation Guide

## Purpose
- `.docs/` stores project documentation for engineering decisions, operational status, and content authoring references.
- Normative docs define rules and constraints implementation must follow.
- Reference/status docs describe current state, audits, and tracking artifacts and must be periodically verified.

## Document Index

| Document | Type | Purpose |
|---|---|---|
| `ARCHITECTURE.md` | Normative | Source-of-truth for architecture rules, invariants, service boundaries, stat naming policy, and endpoint response contract. |
| `PROJECT_CONTEXT.md` | Reference | High-level onboarding snapshot of project scope and current structure. |
| `CURRENT_TASK.md` | Status | Active work log and current execution priorities. |
| `audit-and-tech-debt-2026-05-07.md` | Audit + Debt Register | Consolidated findings, risks, structural debt, and priority summary. |
| `test-coverage-audit.md` | Audit | Point-in-time QA/test coverage findings and validation notes. |
| `QUEST_AUTHORING_COMPLETE.md` | Content Index | Entry point and read order for quest authoring documentation. |
| `QUEST_AUTHORING_RULES.md` | Content Reference | Structural quest authoring rules (models, mechanics, constraints). |
| `QUEST_AUTHORING_PATTERNS.md` | Content Reference | Authoring patterns, examples, and common mistakes checklist. |
| `QUEST_CONTENT_GUIDE.md` | Content Reference | Prose/tone/voice standards for quest writing. |
| `WORLD_LORE.md` | Content Index | Entry point for world/lore documentation. |
| `WORLD_LORE_CORE.md` | Content Reference | Canonical city/faction/lore context. |
| `WORLD_LORE_REFERENCE.md` | Content Reference | Hubs, characters, contacts, items, and enemy reference data. |
| `QUEST_YAML_IMPORT.md` | Ops Reference | Import/export workflow and YAML pipeline notes. |
| `quest_tracking.xlsx` | Tracking Source | Spreadsheet source for quest tracking. |
| `quest_tracking.md` | Tracking Mirror | Diff-friendly text mirror of quest tracking spreadsheet. |
| `GAME_DESIGN.md` | Design Reference | Current gameplay mechanics/design summary for implementation alignment. |

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
- `audit-and-tech-debt-2026-05-07.md`: update when findings are resolved or superseded by a newer audit.
- Audit docs: update when new findings are confirmed or resolved.

## Tracking Policy
- New findings from audits or investigations should be captured in the active consolidated findings register (`audit-and-tech-debt-2026-05-07.md`) until superseded.
- Active execution status belongs in `CURRENT_TASK.md`, not in audit docs.
- Quest tracking source of truth is `quest_tracking.xlsx`; regenerate `quest_tracking.md` after spreadsheet updates.
- Completed debt items should be removed or explicitly marked resolved with a date.
