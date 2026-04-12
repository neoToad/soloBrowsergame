# Tech Debt

## `start_quest` awards scene items but `choice_resolve` also awards them

Both `start_quest` and `choice_resolve` call `award_scene_items`. This is correct but easy to miss — the award-on-enter pattern is in two places. If award logic gets more complex, both need to stay in sync.

**Impact**: Low now, but a future landmine if scene item award logic changes.

---

## CombatState is a 1:1 on session — only one active fight at a time

`CombatState` is a `OneToOneField` to `GameSession`. This means there is no way to have concurrent encounters or re-enter a partially-completed fight after navigating away. The current game design doesn't require it, but the constraint is documented on the model field.

**Impact**: Not a problem today. Revisit if multi-room dungeons with sequential fights are added.