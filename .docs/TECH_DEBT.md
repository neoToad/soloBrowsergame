# Tech Debt

Last audited: 2026-04-25

## High Priority

## Combat end-scene null handling can crash session flow

`resolve_combat_end()` assumes `next_scene` is always present, but both combat paths allow nullable destination scenes (`CombatEncounter.victory_scene` and `defeat_scene` are nullable). If content is misconfigured, `session.current_scene` can become `None` and later rendering crashes.

- Evidence: `game/models/combat.py` (`victory_scene`/`defeat_scene` nullable), `game/views.py:415-420`, `game/services/combat.py:211-215`, `game/services/combat.py:254-255`
- Impact: Hard crash / broken save-state on malformed combat content.
- Plan: Add explicit `next_scene is None` guards in combat resolution paths, return a controlled `400` with authoring guidance, and add tests for missing victory/defeat scene cases.

---

## Roll-route choices can transition to `None` scene

When a scene requires a roll, `choice_resolve()` trusts `resolve_roll()` output and does not validate that success/failure target scenes exist. Misconfigured content can route to `None`, then fail in arrival/render flow.

- Evidence: `game/views.py:113-121`, `game/services/scene.py:41-42`
- Impact: Runtime 500s and potentially invalid `current_scene` state.
- Plan: Validate `next_scene` after `resolve_roll()` in `choice_resolve()`, return `400` for malformed routing, and add coverage for missing success/failure targets.

---

## YAML import reuses requirement groups by label (cross-content coupling)

`import_quest` and `import_hubs` use `RequirementGroup.objects.get_or_create(label=...)`, then clear and rebuild requirements. Reusing labels across quests/hubs mutates shared groups unexpectedly.

- Evidence: `game/management/commands/import_quest.py:165-180`, `game/management/commands/import_hubs.py:118-133`
- Impact: Importing one content file can silently alter requirements for unrelated content.
- Plan: Stop keying requirement groups by label alone; create scoped groups per import object (or deterministic unique key), migrate existing shared-label data safely, and add regression tests for cross-quest isolation.

---

## `choice_create` in quest builder does not verify source scene belongs to quest

`choice_save`/`choice_delete` enforce quest ownership, but `choice_create` accepts `source_scene_id` without checking membership in `quest_id`.

- Evidence: `game/quest_builder_views.py:412-426`, compare with ownership checks in `game/quest_builder_views.py:460-463` and `487-490`
- Impact: Cross-quest data linkage bugs from malformed admin requests.
- Plan: Enforce quest membership check in `choice_create` before service call, return `403` on mismatch, and add endpoint tests mirroring `choice_save`/`choice_delete` protections.

---

## Medium Priority

## Event logging remains split between service-returns and direct DB writes

Most services return log messages for views to flush, but combat services still directly write logs in places (`resolve_combat_end`) and flush within service logic (`execute_enemy_attack` defeat branch).

- Evidence: `game/services/combat.py:210`, `game/services/combat.py:278-279`
- Impact: Inconsistent service contract and harder-to-test side effects.
- Plan: Standardize combat services to return log messages only, move all flushing/persistence to views (or one logging service), and update tests to assert returned logs rather than DB writes inside service code.

---

## `maybe_complete_quest` assumes ending scene belongs to a single quest

Quest completion uses `next_scene.quests.first()` despite many-to-many quest-scene relations.

- Evidence: `game/services/progression.py:102`
- Impact: Silent incorrect quest completion if ending scenes are shared across quests.
- Plan: Resolve quest context from transition source (active quest/run context) instead of `.first()`, or enforce one-quest-per-ending-scene invariant with validation; then add tests for shared-ending scenarios.

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

- `unique_together` modernization to explicit `UniqueConstraint` completed (`0044_unique_together_to_unique_constraint`).
- Root URL lambda redirect replaced with named view (`views.root_redirect`).
- Broad `except Exception` in quest builder panel path replaced with specific `CombatEncounter.DoesNotExist` handling.
- Missing `Quest.entrance_scene` guard in `start_quest` now returns controlled `400`.
- HTMX partial concatenation in `_htmx_response()` replaced with include-based template.
- Heat clamp delta reporting corrected in `process_turn_income()`.
