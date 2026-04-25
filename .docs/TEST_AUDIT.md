# Test Audit Report

## 1. Coverage Summary

| File | Stmts | Miss | Cover |
|---|---|---|---|
| `services/export_game_state.py` | 93 | 93 | **0%** |
| `quest_builder_views.py` | 229 | 171 | **25%** |
| `services/quest_builder.py` | 487 | 266 | **45%** |
| `services/inventory.py` | 64 | 28 | **56%** |
| `services/property_service.py` | 71 | 27 | **62%** |
| `services/arrival.py` | 36 | 13 | **64%** |
| `services/combat.py` | 155 | 52 | **66%** |
| `services/progression.py` | 75 | 25 | **67%** |
| `templatetags/game_filters.py` | 48 | 15 | **69%** |
| `services/scene.py` | 54 | 14 | **74%** |
| `views.py` | 312 | 77 | **75%** |
| **TOTAL** | 2855 | 899 | **68.5%** |

Below the 80% threshold. The riskiest gaps are in the combat loop (`execute_enemy_attack` untested), arrival pipeline (`process_arrival` happy path untested), inventory effects (`add_stat` branch), and property rewards — all active game logic with real branching.

---

## 2. Missing Tests (High Priority)

### `services/combat.py` — `execute_enemy_attack` (entire function untested, ~40 lines)

The enemy attack resolution — including the player-defeat branch — has no tests. This is the most critical gap: it's stateful, mutates HP, and calls `resolve_combat_end`.

```
test_enemy_attack_hit_reduces_player_hp
test_enemy_attack_miss_leaves_hp_unchanged
test_enemy_attack_reduces_player_to_zero_transitions_to_defeat_scene
```

### `services/combat.py` — `initialize_combat_state` non-combat path

The branch that deactivates a lingering `CombatState` when entering a non-combat scene is untested.

```
test_initialize_combat_state_deactivates_when_entering_non_combat_scene
test_initialize_combat_state_recreates_deleted_inactive_state
```

### `services/inventory.py` — `apply_item_effect` branches

Only `heal_hp` is tested via `UseItemTest`. The `add_stat` branch and the non-consumable path are both uncovered.

```
test_use_item_add_stat_effect_increases_stat_and_consumes_item
test_consume_item_decrements_quantity_without_deleting_when_qty_gt_1
test_award_scene_items_respects_award_once_flag
test_award_scene_contacts_gain_and_lose
```

### `services/arrival.py` — `process_arrival` quest-completion branch

The outer `if quest_logs:` block (lines 46–61) is never exercised. This path runs `resolve_contest`, `process_turn_income`, `trigger_rival_contest`, and `get_turn_summary` — all untested in integration.

```
test_process_arrival_on_quest_ending_triggers_income_and_turn_summary
test_process_arrival_resolves_active_rival_claim_on_victory_scene
```

### `services/property_service.py` — `apply_property_rewards`

`receive_property` and `lose_property` paths are fully uncovered.

```
test_apply_property_rewards_grants_property_on_arrival
test_apply_property_rewards_skips_already_owned_property
test_apply_property_rewards_removes_property_on_lose
test_process_turn_income_with_active_properties_applies_cash_rep_heat
```

### `services/progression.py` — `maybe_complete_quest` edge cases

The function is tested indirectly through views but not directly. Uncovered: the `created=False` branch (quest already completed), and the non-ending scene early return.

```
test_maybe_complete_quest_non_ending_scene_returns_empty
test_maybe_complete_quest_already_completed_does_not_duplicate
```

### `views.py` — `combat_enemy_attack` and `combat_flee` views

Both views exist in `urls.py` and are used in combat flow, but no view-level tests exercise them.

```
test_combat_enemy_attack_view_applies_queued_attack
test_combat_flee_redirects_to_current_scene
```

### `services/export_game_state.py` — 0% coverage

The entire module is untested. If it's production-usable code (not just a dev tool), at least a smoke test is warranted.

---

## 3. Unnecessary / Low-Value Tests

| Test | Why | Action |
|---|---|---|
| `test_levelup_flavor_filter_uses_level_keyed_lookup` | Tests a static dict lookup; the dict can't have bugs | Remove or fold into `test_scene_renders_level_up_panel_after_level_gain` |
| `test_compute_max_hp_formula` | Tests arithmetic over hardcoded constants; formula can't be wrong unless the constants change | Merge with `test_create_session_sets_hp_and_max_hp_from_formula` |
| `test_increment_turn_advances_session_counter` | Tests that adding 1 to a counter adds 1 | Remove; this level of triviality adds no confidence |
| `test_get_recon_tier_thresholds` | Verifies a dict-range lookup with three boundary values; no branching logic | Keep as parametrized, or remove — the job view tests exercise the same boundary implicitly |

---

## 4. Redundancy Issues

### `test_full_replay_loop_allows_replay_after_cooldown` / `test_contact_offer_unlock_and_offer_cooldown_are_enforced_independently`

Both tests execute the full beat-1 → beat-2 → resolve sequence. The second test adds unique value (min_run_count gating, contact-offer cooldown), but beats 1 and 2 are copy-pasted. **Refactor suggestion:** extract a `_run_full_job(client, run, approach)` helper that encapsulates the beat 1 + beat 2 + resolve calls, then call it from both tests.

### `test_stat_gte` / `test_level_gte`

Both test a `>= threshold` numeric comparison on a different field. These could be a single parametrized test:

```python
@pytest.mark.parametrize("condition_type,stat_name,stat_value,player_value,expected", [
    ('stat_gte', 'strength', 10, 10, True),
    ('stat_gte', 'strength', 11, 10, False),
    ('level_gte', None, 5, 5, True),
    ('level_gte', None, 6, 5, False),
])
```

---

## 5. Test Quality Issues

### Naming problems

| Current name | Better name |
|---|---|
| `test_combat_attack_continues` | `test_player_attack_non_killing_blow_returns_combat_panel` |
| `test_htmx_choice_resolve` | `test_choice_resolve_advances_scene_and_returns_htmx_fragment` |
| `Phase4PerformanceTest` | Most of this class tests correctness, not performance — rename to `PropertyServiceTest`, move the two query-budget tests to a `QueryBudgetTest` class |

### Missing assertions

- `test_combat_attack_continues` — asserts on HTML content but never verifies that `enemy_hp` decreased or `turn_number` advanced in the DB.
- `test_scene_navigation` — only checks status code and text; doesn't confirm the session's `current_scene` is unchanged as a result.
- `test_use_item_success` — `effect_value=10`, `max_hp - 5 = N-5`, so the exact healed HP is deterministic. The test uses `assertGreater(hp, N-5)` but could use `assertEqual(hp, N)`.

### Structural issues

- **Fixture-heavy tests are brittle.** `GameNavigationTest`, `NoticeBoardTest`, and `CombatTest` all load 7+ JSON fixtures. Any game-data change (key rename, new required field) silently breaks unrelated tests. The factory helpers already in place are the right path — consider migrating `GameNavigationTest` to use them.
- **`test_duplicate_key_detected` mocks the entire Django ORM.** Three levels of `MagicMock` patching to bypass a DB uniqueness constraint is too much indirection. The comment in the test even acknowledges this case "can't exist in reality." Either remove this test or test the pure logic by extracting the duplicate-detection code into a function that takes a list.

---

## 6. Recommended Improvements (Top 5)

### 1. Add `execute_enemy_attack` tests — highest risk gap

The player-defeat path is untested in any form. One test for the hit/survive case and one for the defeat case would cover ~40 lines and validate the most consequential state transition in the game.

### 2. Add `process_arrival` integration test covering the quest-completion branch

Create a test session that navigates to an ending scene via `choice_resolve`. This would exercise `maybe_complete_quest`, `process_turn_income`, `trigger_rival_contest`, and `get_turn_summary` together — the largest single untested execution path.

### 3. Add `apply_item_effect` `add_stat` and `consume_item` quantity-decrement tests

Two small unit tests. These are pure service functions with no fixture dependencies. Currently the only item effect tested is `heal_hp`.

### 4. Add `apply_property_rewards` tests (receive + lose)

These are pure service functions that operate on well-factored models. A `PropertyServiceTest` class with four tests (receive-new, receive-already-owned, lose-owned, lose-not-owned) would add meaningful coverage to a 62% file.

### 5. Rename `Phase4PerformanceTest` and split it

The current class name actively misleads. The contest resolution tests (`test_resolve_contest_victory_*`, `test_resolve_contest_non_victory_*`) have nothing to do with query performance. Move them to a `PropertyServiceTest` class; keep only the two `CaptureQueriesContext` tests under a `QueryBudgetTest` name.