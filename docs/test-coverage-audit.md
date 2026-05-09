Reviewed and updated. Supersedes previous version.

# Test Coverage Audit

## Scope and method
Reviewed `game/tests/*` and cross-checked against service/view/model code plus `coverage.json` (overall ~48% statement coverage). Focused on behavioral risk in gameplay transitions, requirements, combat, arrival effects, and flag mutations.

## 1) Tests to improve

### A. Requirement evaluation breadth is incomplete
- **Tests:** [test_requirements.py](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_requirements.py)
- **Current behaviour:** Covers `stat_gte`, `level_gte`, `has_item`, `missing_item`, `quest_completed`, `quest_not_done`, `quest_ending`, and group `all/any`.
- **Gap:** Does not cover `stat_lte`, `xp_gte`, `has_flag`, `missing_flag`, `has_contact`, `missing_contact`, or unknown `condition_type` fallback. `has_flag`/`missing_flag` appear only in integration navigation tests; `has_contact`/`missing_contact` have no test coverage at any layer.
- **Recommended fix:** Add table-driven cases for every registered evaluator. `has_contact`/`missing_contact` require a real `Contact` + `PlayerContact` row. Add one invalid evaluator case asserting `False`.

### B. Some progression tests assert implementation details, not behavior
- **Tests:** [test_progression.py](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_progression.py)
- **Current behaviour:** `test_apply_stat_rewards_no_change_returns_empty_and_does_not_save` patches `stats.save` and asserts the mock was not called.
- **Gap:** Verifies internal call pattern, not external state contract; brittle to harmless refactors such as switching to `update_fields`.
- **Recommended fix:** Replace with state-based assertions: confirm no stat deltas via `refresh_from_db`, no event logs created. Add a query-count guard if save-suppression is the behavioral invariant.

### C. Combat guard tests missing endpoint-level verification for two guard paths
- **Tests:** [test_combat_continue_and_guards.py](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_combat_continue_and_guards.py)
- **Current behaviour:** `run_combat_continue_raises_when_no_combat_state` and `run_enemy_attack_raises_when_no_pending_enemy_attack` are tested at service level only, with `flush_event_log` patched. Endpoint tests for missing-scene guard paths already exist (`test_combat_continue_returns_400_when_victory_scene_missing`, `test_combat_enemy_resolve_returns_400_when_defeat_scene_missing`).
- **Gap:** No endpoint-level test confirms that POSTing to `combat_continue` with no `CombatState` row, or to `combat_resolve_enemy` with active combat but no pending attack, returns 400 and leaves DB state unchanged.
- **Recommended fix:** Add two integration tests hitting the endpoints directly without patching service internals: one with no `CombatState`, one with active combat but `enemy_attack_pending = False`. Assert 400 status, unchanged combat/session rows, and no partial log writes.

### D. Import orchestrator test is too dispatch-internal
- **Tests:** [test_import_orchestrator.py](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_import_orchestrator.py)
- **Current behaviour:** `test_import_single_source_uses_registry_handler` uses `patch.dict` on `IMPORT_HANDLERS` and asserts the mock was called.
- **Gap:** Tests registry wiring only; real import paths are tested in `test_import_quest.py` and `test_import_refactor.py` but not via the orchestrator dispatcher.
- **Recommended fix:** Add one integration test that passes a real minimal YAML through `import_single_source` per import type and asserts created/updated/warnings behavior without mocking the handler.

### E. Route resolution test is low-value and framework-coupled
- **Tests:** [test_routes.py](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_routes.py)
- **Current behaviour:** Asserts Django `resolve(reverse(...))` maps to callables.
- **Gap:** Duplicates what higher-level endpoint tests already validate; primarily tests Django resolver mechanics.
- **Recommended fix:** Remove or collapse into one smoke assertion if a URLconf sanity check is desired.

## 2) Tests to remove

| Test | Why it adds little/no value |
|---|---|
| [test_routes.py](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_routes.py) `test_named_routes_resolve_to_public_view_callables` | Duplicates coverage already provided by many request-level tests hitting those routes; primarily tests Django resolver mechanics. |
| [test_session_territory_context.py](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_session_territory_context.py) `test_render_context_uses_player_territory_for_owned_territory_ids` | Substantially overlaps [test_session_context_builders.py](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_session_context_builders.py) `test_build_social_context_exposes_representative_social_and_property_values`; both assert `visible_territories`, `owned_territory_ids`, and `player_properties` on the same underlying data. Keep the context-builder test; remove the render-context duplicate. |
| [test_territory_models.py](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_territory_models.py) `test_create_territory_with_income_fields` | Pure ORM field persistence smoke test; income field behavior is meaningfully exercised in `test_property_and_arrival.py`. Constraint/uniqueness tests in the same file are the higher-value part. |

## 3) Tests to create

## Service layer (high risk)

- **`game/services/gameplay/start_quest.py` — no-entrance-scene branch is untested.**  
  Scenario: quest exists, requirements pass, but `quest.entrance_scene` is `None`.  
  Assert: 400 response, session scene unchanged, no arrival or log side effects.  
  Note: requirement failure (403) and success paths are already covered in `test_navigation_notice_board.py`.

- **`game/services/gameplay/use_item.py` — item with no `effect_type`.**  
  Scenario: item is in inventory but `item.effect_type` is blank/None.  
  Assert: `GameplayError` with status 400, inventory unchanged, no event log entries.  
  Note: the inventory-missing and heal-success paths already exist in `test_inventory.py`; only the `no effect_type` branch is missing.

- **`game/services/progression.py` — XP award at `MAX_LEVEL`.**  
  Scenario: `stats.level == MAX_LEVEL` (7), award additional XP.  
  Assert: level does not increment past 7, XP accumulates, stat_points still awarded from XP milestones up to the `stat_points_awarded` high-water mark, no exception raised.

## Requirement evaluation paths (high risk)

- **Full evaluator coverage in `Requirement.evaluate`.**  
  Scenario: every `CONDITION_TYPES` branch not yet in `test_requirements.py`: `stat_lte`, `xp_gte`, `has_flag`, `missing_flag`, `has_contact` (requires real `Contact` + `PlayerContact` row), `missing_contact`, and one unknown `condition_type` asserting `False`.  
  Assert: exact boolean outcomes for each case.

- **`get_available_choices` with multi-group mixed logic.**  
  Scenario: choice with two requirement groups (`any` + `all`) where one group fails; a second choice where both groups pass.  
  Assert: first choice is gated out; second choice is visible. Tests the outer `all(rg.evaluate(ctx) for rg in requirement_groups)` loop that unit tests do not reach.

## Combat state transitions (high risk)

- **No-pending-victory and no-active-combat through endpoints (without mocks).**  
  Scenario: POST to `combat_continue` with no `CombatState` row; separately POST to `combat_resolve_enemy` with active combat but `enemy_attack_pending = False`.  
  Assert: 400 response, unchanged session/combat rows, no partial log writes.

- **Pending enemy attack lifecycle consistency.**  
  Scenario: queue an attack, resolve once via `combat_resolve_enemy`, then POST `combat_resolve_enemy` again.  
  Assert: second resolve returns 400 ("No pending enemy attack"), pending fields cleared atomically after first resolve, damage not applied twice.

- **Combat end with chained arrival + quest completion + level-up.**  
  Scenario: victory scene is also a quest ending scene with stat rewards; XP award crosses a level threshold.  
  Assert: correct log ordering (combat reward → arrival → quest completion → XP → level-up flavor), exact stat deltas, no duplicate `CompletedQuest` rows.

## Arrival effects (high risk)

- **Atomic rollback of `process_arrival`.**  
  Scenario: force failure mid-arrival by patching one downstream reward function to raise after earlier mutations have applied.  
  Assert: no partial cash/rep/heat/item/contact/territory mutations persisted; `refresh_from_db` confirms original state.

- **Arrival effects must not run on read-only views.**  
  Scenario: repeated GET `scene_detail` on a scene configured with cash/item/contact arrival rewards.  
  Assert: no stat mutations, no inventory changes, no quest completions, no turn-income processing across repeated GETs.

- **Income trigger condition — already-completed quest does not re-trigger income.**  
  Scenario: player arrives at a quest ending scene for a quest already in `completed_map`.  
  Assert: `maybe_complete_quest` returns `[]`, `process_arrival` produces no `quest_logs`, turn income does not run, `turn_summary` is `None`.

## Roll mechanics and flag mutations (medium risk)

- **Roll exact DC boundary.**  
  Scenario: mock `roll_d20` so that `roll + modifier == scene.roll_difficulty` exactly (not exceeds it).  
  Assert: `RollResult.success` is `True` (success condition is `>=`), destination is `success_scene`, roll log reflects the tie.

- **Flag mutation order when set and clear target the same flag name.**  
  Scenario: choice with identical `set_flag_name` and `clear_flag_name`.  
  Assert: flag is cleared after resolution (`resolve_choice` executes `set_flag` before `clear_flag`), no ambiguous intermediate state persisted to the session.

## Architecture invariant coverage status

- **Arrival effects must not fire on read-only views (Invariant #3 from ARCHITECTURE.md):**  
  No explicit test currently proves this invariant.

- **Atomic boundaries around multi-step transitions (Invariant #5 from ARCHITECTURE.md):**  
  No rollback/failure-in-transaction test currently verifies atomicity of arrival or combat multi-step transitions.