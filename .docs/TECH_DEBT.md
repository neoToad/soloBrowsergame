# Tech Debt

Last audited: 2026-04-27


## Medium Priority



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
- Item stat target validation completed: `Item.clean()` now restricts `effect_stat`/`passive_stat` to canonical stat fields; importer item writes run `full_clean()` and fail fast on invalid stat targets; runtime item application/effective-stat paths ignore invalid legacy stat names; invalid rows can be reported via `report_invalid_item_stats`; regression coverage added in `game/tests/test_inventory.py`.
- Combat event logging contract standardized: low-level combat services now return logs only (no direct `EventLog` writes / internal flushes), and persistence is centralized at gameplay orchestration boundary (`game/services/gameplay/combat.py`), with combat tests updated to assert returned logs and boundary flushing behavior.
- Fixture export natural-key mismatch resolved: `export_all_fixtures` now uses PK-based serialization (natural-key flags removed) and regression coverage verifies FK shape plus `loaddata` round-trip (`game/management/commands/export_all_fixtures.py`, `game/tests/test_fixture_export.py`).
