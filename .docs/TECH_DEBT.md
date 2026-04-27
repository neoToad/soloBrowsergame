# Tech Debt

Last audited: 2026-04-27


## Medium Priority

## Event logging remains split between service-returns and direct DB writes

Most services return log messages for views to flush, but combat services still directly write logs in places (`resolve_combat_end`) and flush within service logic (`execute_enemy_attack` defeat branch).

- Evidence: `game/services/combat.py` (`execute_enemy_attack`, `resolve_combat_end`)
- Impact: Inconsistent service contract and harder-to-test side effects.
- Plan: Standardize combat services to return log messages only, move all flushing/persistence to views (or one logging service), and update tests to assert returned logs rather than DB writes inside service code.

---

## Item stat target fields are not validated

`Item.effect_stat`/`passive_stat` are free text. Runtime application uses dynamic attribute access, so typos fail silently (or mutate transient attributes not backed by DB fields).

- Evidence: `game/models/items.py:19-25`, `game/services/inventory.py:84-87`, `game/utils.py:32-35`
- Impact: Authoring mistakes produce silent gameplay inconsistencies.
- Plan: Add model-level validation (`clean()`) restricting `effect_stat`/`passive_stat` to allowed stat fields, enforce it in admin/forms/imports, and add tests for invalid stat names.

---

## Flag names are freeform and unvalidated

Choice and offer flag fields are plain strings with no schema/registry validation.

- Evidence: `game/models/world.py:205-208`, `game/models/jobs.py:180`
- Impact: Typos create silent gating/flow bugs that are difficult to diagnose.
- Plan: Introduce a shared flag registry (enum/constant source), validate `set_flag_name`/`clear_flag_name`/`required_flag` against it in model clean/admin, and provide migration-safe fallback for legacy flags.

---

## Scene key naming convention is documented but not enforced

Admin hints recommend `{quest_key}__{scene_slug}`, but no model validation enforces that convention.

- Evidence: `game/admin.py:384-385`, `game/models/world.py` (`Scene.key` has no convention-specific validator)
- Impact: Inconsistent keys and fragile content/tooling assumptions.
- Plan: Add `Scene.clean()` validation for `{quest_key}__{scene_slug}` when scene is attached to a quest, provide admin helper autofill, and include a management command to report/fix legacy violations.

---

## Fixture export uses natural-key mode without natural key implementations

`export_all_fixtures` serializes with `use_natural_foreign_keys=True` and `use_natural_primary_keys=True`, but models do not implement `natural_key()`.

- Evidence: `game/management/commands/export_all_fixtures.py:48-49`
- Impact: Portability/import assumptions are unclear and may break across environments.
- Plan: Either implement `natural_key()` and managers for exported models or disable natural-key serialization; document the chosen contract and add fixture round-trip tests.

---

## Low Priority / Maintainability

## `quest_builder.py` remains a large low-cohesion module

The quest builder service file is still very large and mixes graph assembly, validation, parsing, and mutation logic.

- Evidence: `game/services/quest_builder.py` (~900 LOC)
- Impact: Higher regression risk and slower targeted testing/refactoring.
- Plan: Split into focused modules (`canvas`, `validation`, `parsing`, `mutations`, `requirements`), preserve public API shims during transition, and add unit tests per module boundary.

---

## `build_render_context` is a broad query-assembly hotspot

A single function assembles many unrelated concerns (choices, notice board, properties, gangs, jobs context), increasing coupling and query drift risk.

- Evidence: `game/services/session.py:59-100`
- Impact: Harder performance tuning and feature isolation.
- Plan: Decompose into dedicated context builders (core scene, social/properties, jobs/hub), add query-count tests for hub vs non-hub scenes, and centralize prefetch/select strategy per builder.

---

## Recently Resolved (removed from active debt)

- Test-suite monolith cleanup completed: `game/tests/tests.py` removed and split into focused modules (`test_navigation`, `test_combat`, `test_progression`, `test_inventory`, `test_property_and_arrival`, `test_quest_builder`, `test_performance`, `test_requirements`, `test_export_game_state`).
- Quest completion ownership ambiguity resolved by scene ownership model change: `Scene` now has `quest` FK and completion resolves via `next_scene.quest` instead of M2M lookup (`game/services/progression.py`).
- Import requirement-group cross-content coupling resolved via scoped importer requirement groups (`game/services/importers/requirements.py`) plus regression tests (`game/tests/test_import_refactor.py`).
- `unique_together` modernization to explicit `UniqueConstraint` completed (`0044_unique_together_to_unique_constraint`).
- Root URL lambda redirect replaced with named view (`views.root_redirect`).
- Broad `except Exception` in quest builder panel path replaced with specific `CombatEncounter.DoesNotExist` handling.
- Missing `Quest.entrance_scene` guard in `start_quest` now returns controlled `400`.
- HTMX partial concatenation in `_htmx_response()` replaced with include-based template.
- Heat clamp delta reporting corrected in `process_turn_income()`.
- Combat end-scene null handling hardened: `resolve_combat_end()` now guards missing `victory_scene`/`defeat_scene` with controlled `400` authoring errors, and endpoint regression tests cover both misconfiguration paths (`game/tests/test_combat.py`).
- Roll-route null destination handling hardened: `resolve_choice()` now validates roll outcome routing and returns controlled `400` authoring errors for missing `success_scene`/`failure_scene`, with endpoint regression tests in `game/tests/test_navigation.py`.
- Quest-builder `choice_create` now enforces source-scene quest ownership and returns controlled `403` on mismatch, with endpoint regression tests for cross-quest rejection and same-quest success (`game/tests/test_quest_builder.py`).
