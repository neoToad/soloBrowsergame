# Tech Debt

## `start_quest` awards scene items but `choice_resolve` also awards them

Both `start_quest` and `choice_resolve` call `award_scene_items`. This is correct but easy to miss — the award-on-enter pattern is in two places. If award logic gets more complex, both need to stay in sync.

**Impact**: Low now, but a future landmine if scene item award logic changes.

---

## EventLog writes inside services

Some event writes still happen in `game/services/combat.py` and `game/services/property_service.py`, which conflicts with the preferred service/view boundary where services return messages and views log them.

**Impact**: Inconsistent EventLog patterns.

---

## Scene key prefix convention is not model-validated

The `{quest_key}__{scene_slug}` convention is documented and the admin shows a hint, but nothing enforces it at the model level. A scene saved with an arbitrary key will pass validation.

**Impact**: Silent breakage risk if a scene key is authored incorrectly.

---

## `export_quest` portability depends on unimplemented natural keys

`export_quest` relies on Django's natural key serialization, but not all related models implement `natural_key()`. Fixtures exported from one database may fail to load into another.

**Impact**: Content workflow is partially broken for cross-database portability.

---

## `CombatEncounter.objects.get()` unhandled in views

`views.py:196` and `views.py:278` call `.objects.get(scene=session.current_scene)` with no exception handler. `services/combat.py:86` wraps its equivalent call, but the view-level calls don't. Corrupted data or a missing encounter record raises an unhandled 500.

**Impact**: Hard crash if a combat scene has no associated encounter.

---

## `BASE_DEFENSE` magic number duplicated

The formula `10 + stat_modifier(agility)` appears in both `services/combat.py:15` and `views.py:279`. The `10` baseline is a game rule with no named constant.

**Impact**: A balance change to base defense requires two edits; easy to miss one.

---

## Player damage is hardcoded `d6`, enemy damage is configurable

`services/combat.py:10` rolls `random.randint(1, 6)` for player damage. Enemy damage uses `damage_min`/`damage_max` fields on `CombatEncounter`. There's no equivalent for the player.

**Impact**: Balancing player damage requires a code change; inconsistent with how enemy damage is handled.

---

## Silent `except Exception` in `quest_builder_views.py`

A bare `except Exception: combat_encounter = None` swallows all errors when fetching a combat encounter for the builder. Specific exceptions like `CombatEncounter.DoesNotExist` are fine to catch, but the broad catch hides real bugs silently.

**Impact**: Database errors or programming mistakes during quest editing produce no traceback.

---

## Flag names are unvalidated freeform strings

`set_flag_name` and `clear_flag_name` on `Choice` (models/world.py:203–206) are plain `CharField`s. A typo in a flag name is a silent no-op — the flag is set or cleared with a wrong name, breaking game logic without any error.

**Impact**: Authoring errors in flag names are invisible at save time and unpredictable at runtime.

---

## `effect_stat` on `Item` not validated against real stat fields

`views.py:~387–398` applies item stat bonuses via `setattr(stats, item.effect_stat, ...)`. There is no validation (in `Item.clean()` or at runtime) that `effect_stat` is actually a field on `PlayerStats`. A typo saves fine and silently does nothing.

**Impact**: Misconfigured items fail without error.

---

## Heat delta reported incorrectly when clamped

`services/property_service.py:23–24` subtracts `prop.heat_per_turn` from `stats.heat` then clamps to 0, but the `totals['heat']` accumulator records the unclamped subtraction. If heat is 5 and `heat_per_turn` is 10, the player's heat drops by 5 but the income summary reports −10.

**Impact**: Property income log shows incorrect heat reduction; harder to reason about balance.

---

## `completed_map` rebuilt from all rows on every request

`session.py:get_completed_map()` materialises every `CompletedQuest` row for the session into a dict on each view call. For a player with many completed quests this issues a full table scan per request.

**Impact**: Performance degrades linearly with quest completion count; no caching layer.

---

## `Quest.entrance_scene` can be null; `start_quest` does not guard it

`entrance_scene` is `null=True, blank=True` on `Quest`. `views.py:start_quest` sets `session.current_scene = quest.entrance_scene` without checking for null. A published quest with no entrance scene will set `current_scene` to `None` and crash the next view.

**Impact**: Misconfigured but visible quests cause an immediate hard crash when a player accepts them.