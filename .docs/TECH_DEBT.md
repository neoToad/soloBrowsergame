# Tech Debt

## `start_quest` awards scene items but `choice_resolve` also awards them

Both `start_quest` and `choice_resolve` call `award_scene_items`. This is correct but easy to miss — the award-on-enter pattern is in two places. If award logic gets more complex, both need to stay in sync.

**Impact**: Low now, but a future landmine if scene item award logic changes.

---

## EventLog writes inside services

Some event writes still happen in `game/services/combat.py` and `game/services/property_service.py`, which conflicts with the preferred service/view boundary where services return messages and views log them.

**Impact**: Inconsistent EventLog patterns.

---

## `export_quest` uses Django's built-in serializer — no natural key support on all models

`export_quest` calls `serializers.serialize` with `use_natural_foreign_keys=True`. Any model that does not define `natural_key()` / `get_by_natural_key()` will fall back to PKs, making the fixture non-portable across databases.

**Impact**: Fixtures exported with `export_quest` may not load cleanly into a fresh DB if PKs collide. Add `natural_key()` to `Scene`, `Choice`, `Item`, etc. to fix.

