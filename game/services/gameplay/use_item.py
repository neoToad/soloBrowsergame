from ..combat import get_active_combat_state
from ..inventory import apply_item_effect
from ...models.events import flush_event_log
from ...utils import get_effective_stats
from ..types import UseItemResult, GameplayError


def use_item(session_context, item) -> UseItemResult:
    session, stats, inventory, effective_stats, completed_map = session_context

    if item.id not in inventory:
        raise GameplayError("Item not in stash.", status=400)
    if not item.effect_type:
        raise GameplayError("Item has no usable effect.", status=400)

    logs = apply_item_effect(session, stats, inventory, item)
    flush_event_log(session, logs)

    effective_stats = get_effective_stats(stats, inventory)
    combat_state = get_active_combat_state(session)

    return UseItemResult(
        effective_stats=effective_stats,
        combat_state=combat_state,
    )