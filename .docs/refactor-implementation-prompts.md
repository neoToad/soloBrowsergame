# Refactor Implementation Prompt Pack

Use these prompts one at a time in a coding agent. Each prompt assumes this repo�s architecture rule: business logic must live in services, not views.

## 4) Add a trigger helper for snake_case + dot.case event names

```text
Remove manual duplication of HTMX trigger naming conventions in quest-builder responses.

Requirements:
1. Add a helper in `game/presentation/responses.py` (or `game/quest_builder_views/partials.py`) that takes canonical event info and emits both variants, e.g.:
   - `sceneUpdated` and `scene.updated`
2. Replace hand-written dual trigger dicts in scene/choice endpoints.
3. Preserve exact trigger payload shapes consumed by frontend.

Deliverables:
- One trigger builder used everywhere in quest-builder endpoints.
- Tests covering trigger header values.
```

## 5) Retire legacy pending-enemy-attack fallback in combat service

```text
Simplify `game/services/combat.py` by removing legacy compatibility around `pending_enemy_attack` JSON fallback.

Context:
- Current code still has `_has_legacy_pending_enemy_attack_field` and `_read_pending_enemy_attack` fallback logic.
- Migrations include `0053_remove_combatstate_pending_enemy_attack_json.py`.

Requirements:
1. Remove field-existence checks and JSON fallback paths.
2. Keep only typed scalar pending fields (`pending_enemy_roll/total/hit/damage`).
3. Ensure clear errors when pending attack is absent.
4. Update tests in `game/tests/test_combat.py` for new simplified behavior.
5. Verify no model field references remain to removed legacy field.

Deliverables:
- Leaner queue/consume/clear attack functions.
- Passing combat tests.
```

## 6) Separate combat math engine from persistence/orchestration

```text
Refactor `game/services/combat.py` to make roll math pure and orchestration side-effectful but isolated.

Requirements:
1. Create `game/services/combat_engine.py` for pure functions only:
   - player attack roll resolution
   - enemy attack roll resolution
   - message-fragment builders that do not touch DB
2. Keep DB/session mutations in `game/services/combat.py` or move orchestration to `game/services/gameplay/combat.py`.
3. Avoid changing gameplay behavior or text outputs.
4. Add unit tests for pure engine functions without DB fixtures.

Deliverables:
- Clear module boundary between pure rules and persistence.
- Reduced cognitive load in `combat.py`.
```

## 7) Split importer domain module into per-domain modules

```text
Refactor `game/services/importers/domain.py` into smaller modules:
- `game/services/importers/items.py`
- `game/services/importers/enemies_contacts.py`
- `game/services/importers/world.py`
- `game/services/importers/hubs.py`
- `game/services/importers/quests.py`
- shared helpers in `game/services/importers/shared.py`

Requirements:
1. Preserve current import behavior and `ImportResult` bookkeeping.
2. Keep helper reuse for scene choice/items/contacts/combat import paths.
3. Update imports in orchestrator and management commands.
4. Keep function-level test coverage green (`game/tests/test_import_refactor.py`, `test_import_quest.py`).

Deliverables:
- Smaller importer modules with clear responsibilities.
```

## 8) Replace stringly-typed import dispatch with enum/registry

```text
Refactor `game/services/importers/orchestrator.py` to remove string `if/elif` dispatch.

Requirements:
1. Introduce an enum (e.g., `ImportType`) in `game/services/importers/types.py`.
2. Convert `detect_import_type()` to return enum values, not raw strings.
3. Replace `_import_typed_data()` conditionals with a registry map `{ImportType: handler}`.
4. Keep import order deterministic and equivalent to current `TYPE_ORDER`.
5. Maintain current error handling (`CommandError`) and CLI behavior.

Deliverables:
- Enum + registry dispatch.
- Updated tests validating detection and dispatch.
```

## 9) Split overloaded Django admin module

```text
Break `game/admin.py` into an admin package by domain while preserving admin registrations and URLs.

Target structure:
- `game/admin/__init__.py`
- `game/admin/quests.py`
- `game/admin/world.py`
- `game/admin/player.py`
- `game/admin/combat.py`
- `game/admin/inlines.py`
- `game/admin/actions.py`
- `game/admin/quest_builder_urls.py`

Requirements:
1. Preserve all `@admin.register` behavior.
2. Keep `QuestAdmin.get_urls()` behavior, but extract quest-builder URL declarations into a dedicated helper module.
3. Maintain current admin templates and custom links.
4. Confirm Django discovers registrations correctly.

Deliverables:
- Modular admin package with same runtime behavior.
```

## 10) Split runtime `views.py` by domain

```text
Refactor `game/views.py` into a views package:
- `game/views/__init__.py`
- `game/views/navigation.py` (root, hub, scene detail)
- `game/views/combat.py`
- `game/views/quests.py`
- `game/views/player.py` (level_up, use_item)
- `game/views/shared.py` (decorators/helpers like `require_game_session`, `_htmx_response`)

Requirements:
1. Keep public callables imported by `game/urls.py` unchanged via re-exports.
2. No business logic in views; preserve use of services/gameplay layer.
3. Keep HTMX behavior, redirects, and error handling identical.
4. Add/update route tests for regression confidence.

Deliverables:
- Domain-oriented views package with unchanged URL behavior.
```

## 11) Decompose dense session context builder

```text
Refactor `game/services/session.py` `build_render_context()` composition into explicit context providers.

Requirements:
1. Introduce provider functions or dataclass-based providers with clear contracts, e.g.:
   - `build_core_context(...)`
   - `build_hub_context(...)`
   - `build_social_context(...)`
2. Keep output keys and template compatibility unchanged.
3. Ensure no new DB query explosions (use existing select_related/prefetch patterns where needed).
4. Add tests for context key presence and representative values.

Deliverables:
- Better-separated context assembly without behavior changes.
```

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
