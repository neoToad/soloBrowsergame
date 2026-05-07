# Refactor Implementation Prompt Pack

Use these prompts one at a time in a coding agent. Each prompt assumes this repo�s architecture rule: business logic must live in services, not views.

## 12) Extract inline quest-builder JS into static module(s)

```text
Move inline JavaScript out of quest-builder partial templates into static JS files.

Scope:
- `templates/admin/quest_builder/partials/items_section.html`
- `templates/admin/quest_builder/partials/contacts_section.html`
- `templates/admin/quest_builder/partials/requirements_section.html`
- `templates/admin/quest_builder/partials/scene_panel.html`
- `templates/admin/quest_builder/partials/choice_panel.html`

Requirements:
1. Create static modules under `static/js/admin/quest_builder/`.
2. Use data attributes to parameterize selectors and row templates.
3. Preserve HTMX swap compatibility (re-bind behavior after fragment swaps).
4. Remove inline `onclick` handlers and inline `<script>` blocks from these partials.
5. Keep existing UI behavior exactly (add/remove row, reindexing, dynamic param visibility).

Deliverables:
- Reusable JS modules with no inline scripts in listed templates.
- Frontend regression checks for row editing workflows.
```

## 13) Remove tracked `__pycache__` artifacts from git index

```text
Clean repository noise by untracking committed bytecode caches.

Requirements:
1. Remove tracked `__pycache__` directories under `core/` and `game/` from git index only (not local deletion intent):
   - use `git rm --cached -r` on tracked cache paths.
2. Ensure `.gitignore` already covers `__pycache__/` (it does; verify no gaps).
3. Do not modify runtime code.

Deliverables:
- Clean git index without cache artifacts.
```

## 14) Split large integration-heavy tests into behavior-focused modules

```text
Refactor oversized tests for maintainability:
- `game/tests/test_combat.py`
- `game/tests/test_navigation.py`

Requirements:
1. Split by behavior area/endpoints, e.g.:
   - combat attack flow
   - enemy resolve flow
   - combat continue/victory/defeat
   - scene routing/choice resolution
2. Extract shared setup/assertion helpers into `game/tests/helpers/` or fixtures.
3. Keep test intent and coverage equivalent or better.
4. Ensure test names remain descriptive and deterministic.

Deliverables:
- Smaller test modules, shared fixtures/helpers, unchanged behavior confidence.
```

## 15) Add route-shape validation boundary for scene/choice routing semantics

```text
Introduce a single validation boundary for scene/choice route semantics currently spread across models/services/views.

Requirements:
1. Add validator(s) in model/service layer (not views), likely under:
   - `game/models/world.py` for model invariants
   - `game/services/quest_builder/validation.py` for workflow-level checks
2. Cover target/success/failure routing compatibility with scene types and quest ownership constraints.
3. Ensure errors are actionable and consistent for admin quest builder.
4. Add tests for invalid/valid routing combinations.

Deliverables:
- Centralized routing validation with reduced duplicated assumptions.
```

## 16) Optional sequencing meta-prompt (run this before prompt 1)

```text
Create an execution plan for the refactor prompts in `.docs/refactor-implementation-prompts.md` with dependency ordering, expected risk, and test strategy per step.

Output format:
- Ordered checklist with: `step`, `depends_on`, `risk`, `tests_to_run`, `rollback_plan`.
- Keep each step small enough for a single PR.
```
