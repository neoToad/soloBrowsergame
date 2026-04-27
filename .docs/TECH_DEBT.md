# Tech Debt

Last audited: 2026-04-26

## High Priority

## Combat end-scene null handling can crash session flow

`resolve_combat_end()` assumes `next_scene` is always present, but both combat paths allow nullable destination scenes (`CombatEncounter.victory_scene` and `defeat_scene` are nullable). If content is misconfigured, `session.current_scene` can become `None` and later rendering crashes.

- Evidence: `game/models/combat.py` (`victory_scene`/`defeat_scene` nullable), `game/services/combat.py` (`resolve_combat_end` assigns `session.current_scene = next_scene` without a null guard)
- Impact: Hard crash / broken save-state on malformed combat content.
- Plan: Add explicit `next_scene is None` guards in combat resolution paths, return a controlled `400` with authoring guidance, and add tests for missing victory/defeat scene cases.

---

## Roll-route choices can transition to `None` scene

When a scene requires a roll, gameplay choice resolution trusts `resolve_roll()` output and does not validate that success/failure target scenes exist. Misconfigured content can route to `None`, then fail in arrival/render flow.

- Evidence: `game/services/gameplay/resolve_choice.py:20-42`, `game/services/scene.py:41-42`, `game/services/session.py:19-22`
- Impact: Runtime 500s and potentially invalid `current_scene` state.
- Plan: Validate `next_scene` after `resolve_roll()` in gameplay choice resolution, return `400` for malformed routing, and add coverage for missing success/failure targets.

---

## `choice_create` in quest builder does not verify source scene belongs to quest

`choice_save`/`choice_delete` enforce quest ownership, but `choice_create` accepts `source_scene_id` without checking membership in `quest_id`.

- Evidence: `game/quest_builder_views.py` (`choice_create` accepts `source_scene_id` and calls `create_choice_service` without verifying `choice.scene.quest_id == quest_id`); `choice_save`/`choice_delete` perform ownership checks.
- Impact: Cross-quest data linkage bugs from malformed admin requests.
- Plan: Enforce quest membership check in `choice_create` before service call, return `403` on mismatch, and add endpoint tests mirroring `choice_save`/`choice_delete` protections.

---

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
