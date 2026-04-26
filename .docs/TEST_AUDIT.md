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