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