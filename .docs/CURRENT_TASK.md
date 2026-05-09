# Current Task

- Owner: Engineering
- Update Trigger: Any docs/program-level milestone or priority shift.
- Last Verified Against Code: 2026-05-09

## Focus
Keep architecture and debt tracking docs synchronized with the live codebase after the docs consolidation and architecture refresh.

## Status

### Just Completed (2026-05-09)
- Merged legacy audit/debt files into one canonical document:
  - `.docs/audit-and-tech-debt-2026-05-07.md`
- Removed superseded files:
  - `.docs/codebase-audit-2026-05-07.md`
  - `.docs/refactor-audit-2026-05-07.md`
  - `.docs/tech-debt-register.md`
- Rewrote `.docs/ARCHITECTURE.md` to match current runtime/package structure and active invariants.
- Updated debt-tracking references in architecture docs to point at current canonical sources.

### Current State
- Canonical docs by purpose:
  - Architecture/invariants: `.docs/ARCHITECTURE.md`
  - Operational status and immediate priorities: `.docs/CURRENT_TASK.md`
  - Onboarding summary: `.docs/PROJECT_CONTEXT.md`
  - Audit + debt findings register: `.docs/audit-and-tech-debt-2026-05-07.md`
- Stale references to removed docs were eliminated from architecture tracking sections.

### In Progress
- None (docs consolidation + architecture refresh complete).

### Next
- Convert top architecture gaps into implementation tasks and execute in this order:
  1. Remove write-side effects from `GET /game/scene/<scene_key>/`.
  2. Add outer `transaction.atomic()` boundaries to full transition flows (`resolve_choice`, `start_quest`, `resolve_combat_end`).
  3. Guard missing `CombatEncounter` pointers in combat scene initialization to avoid uncaught 500s.
  4. Move `level_up` mutation/log composition out of view layer into gameplay service.
  5. Remove dead helper `game/views/shared.py:_render_current_scene`.
- Keep `.docs/ARCHITECTURE.md` and this file updated whenever any of the above are completed.

## Ongoing Product Work (Non-Docs)
- Combat loop hardening and transition consistency.
- Quest-builder robustness and validation consistency.
- Session/render context maintainability improvements.
- Heat-decay gameplay rule remains deferred and tracked in the consolidated audit/debt doc.

## Working Rules
- Business logic belongs in service modules, not views.
- `ARCHITECTURE.md` is the canonical source for architecture invariants.
- `CURRENT_TASK.md` tracks active implementation/documentation status.
- `audit-and-tech-debt-2026-05-07.md` is the canonical debt and findings register until superseded by a newer audit.
