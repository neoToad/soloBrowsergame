# Tech Debt

## `start_quest` awards scene items but `choice_resolve` also awards them

Both `start_quest` and `choice_resolve` call `award_scene_items`. This is correct but easy to miss — the award-on-enter pattern is in two places. If award logic gets more complex, both need to stay in sync.

**Impact**: Low now, but a future landmine if scene item award logic changes.

---

## EventLog writes inside services

Some event writes still happen in `game/services/combat.py` and `game/services/property_service.py`, which conflicts with the preferred service/view boundary where services return messages and views log them.

**Impact**: Inconsistent EventLog patterns.

