# Tech Debt



## `get_effective_stats` returns a SimpleNamespace

`utils.get_effective_stats()` returns a `SimpleNamespace` rather than a proper dataclass. This means no type hints, no IDE autocomplete on the return value, and it's easy to silently typo a field name.

**Impact**: Low now, but grows as more code accesses effective stats fields.

---

## Quest has two independent gating mechanisms

`Quest.is_unlocked` (a boolean you flip manually) coexists with the `requirements` M2M (the proper evaluated gate). Both are checked separately in `get_notice_board`. A quest could be `is_unlocked=True` with all requirements passing, or either could block independently.

**Impact**: Confusing when authoring content. The intention of `is_unlocked` is unclear — "not yet authored" vs "actively blocked"? Needs a documented convention or consolidation into requirements.

---

## EventLog creation is split between views and services

Services return lists of log message strings. Views loop over them and call `EventLog.objects.create()`. This is a deliberate design (services stay DB-lite where possible), but it means the pattern is inconsistently applied — some log entries are created directly in views, others come back from service return values.

**Impact**: Cognitive overhead when tracing what gets logged. Consider a thin `log_event(session, text)` helper to at least make the call sites consistent.

---

## `get_notice_board` re-fetches inventory independently

`services/scene.py: get_notice_board()` calls `get_player_inventory(session)` internally. When called from `scene_detail` or `choice_resolve`, the inventory has already been loaded by `load_session_context`. This results in a redundant DB query on every notice board render.

**Impact**: Minor extra query per notice board load. Could be fixed by accepting inventory as a parameter.

---

## `start_quest` awards scene items but `choice_resolve` also awards them

Both `start_quest` and `choice_resolve` call `award_scene_items`. This is correct but easy to miss — the award-on-enter pattern is in two places. If award logic gets more complex, both need to stay in sync.

**Impact**: Low now, but a future landmine if scene item award logic changes.

---

## CombatState is a 1:1 on session — only one active fight at a time

`CombatState` is a `OneToOneField` to `GameSession`. This means there is no way to have concurrent encounters or re-enter a partially-completed fight after navigating away. The current game design doesn't require it, but the constraint is not documented.

**Impact**: Not a problem today. Document and revisit if multi-room dungeons with sequential fights are added.

---

## Item equip system is stubbed

`Item.equip_slot` (`weapon`, `armor`, `accessory`) exists in the DB but no equip logic is implemented. There's no way to "equip" an item as opposed to just carrying it. Passive bonuses work via the inventory presence mechanic (`passive_stat` / `passive_value`), not via a slot system.

**Impact**: Dead schema weight. Either implement it or remove it when the inventory UX is revisited.
