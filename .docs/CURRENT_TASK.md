# Current Task

- Owner: Engineering
- Update Trigger: Any docs/program-level milestone or priority shift.
- Last Verified Against Code: 2026-05-02

## Focus
Finalize documentation consolidation in `.docs/` with clear source-of-truth boundaries, no stale references, and split content docs that preserve full canonical content.

## Status

### Just Completed (2026-04-29)
- Created `.docs/README.md` as the docs map with ownership/update guidance and backlog flow policy.
- Updated `.docs/ARCHITECTURE.md` to current module layout and active tracking references.
- Normalized `.docs/PROJECT_CONTEXT.md` to summary-only onboarding context.
- Enforced scope boundaries:
  - `refactor-inventory.md` = structural refactor backlog only
  - `tech-debt-register.md` = debt/risk/workaround/deferred behavior only
- Added diff-friendly text mirror for quest tracking:
  - source: `.docs/quest_tracking.xlsx`
  - mirror: `.docs/quest_tracking.md`
- Split oversized content docs while preserving full content in split files:
  - Quest authoring split: `QUEST_AUTHORING_RULES.md`, `QUEST_AUTHORING_PATTERNS.md`
  - World lore split: `WORLD_LORE_CORE.md`, `WORLD_LORE_REFERENCE.md`
- Converted original large files into index entry points:
  - `QUEST_AUTHORING_COMPLETE.md`
  - `WORLD_LORE.md`

### Current State
- Core docs now have explicit separation by purpose:
  - Architecture/invariants: `ARCHITECTURE.md`
  - Operational status: `CURRENT_TASK.md`
  - Onboarding summary: `PROJECT_CONTEXT.md`
  - Structural backlog: `refactor-inventory.md`
  - Debt/risk register: `tech-debt-register.md`
- Content docs are now navigable via index files and split canonical references.

### In Progress
- Apply drift-audit follow-up updates from `.docs/drift-audit-2026-05-02.md`.

### Next
- Keep docs aligned with runtime behavior as code changes land (especially gameplay logging boundaries and response semantics).
- Update audit docs when findings become stale or are resolved.

## Ongoing Product Work (Non-Docs)
- Jobs subsystem, combat flow, quest builder, and property systems remain active product areas.
- Heat-decay gameplay rule remains deferred and tracked as debt.

## Working Rules
- Business logic belongs in service modules, not views.
- `ARCHITECTURE.md` is the canonical source for architecture invariants.
- `CURRENT_TASK.md` tracks active implementation status.
