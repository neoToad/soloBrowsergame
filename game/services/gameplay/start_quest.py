from ..arrival import process_arrival
from ..session import advance_to_scene, build_player_context
from ..combat import initialize_combat_state
from ...models.events import flush_event_log, log_event
from ...utils import get_effective_stats
from ..types import QuestStartResult, GameplayError


def start_quest(session_context, quest) -> QuestStartResult:
    session, stats, inventory, effective_stats, completed_map = session_context

    ctx = build_player_context(effective_stats, inventory, completed_map, flags=session.flags)
    if quest.requirements.exists():
        if not all(rg.evaluate(ctx) for rg in quest.requirements.all()):
            raise GameplayError("Quest requirements not met.", status=403)

    next_scene = quest.entrance_scene
    if next_scene is None:
        raise GameplayError("Quest has no entrance scene configured.", status=400)

    advance_to_scene(session, next_scene)

    arrival_logs, _ = process_arrival(session, stats, inventory, completed_map, next_scene)
    flush_event_log(session, [f"You took the job: {quest.title}.", *arrival_logs])

    combat_state, combat_init_log = initialize_combat_state(session, next_scene)
    if combat_init_log:
        log_event(session, combat_init_log)

    effective_stats = get_effective_stats(stats, inventory)

    return QuestStartResult(
        next_scene=next_scene,
        combat_state=combat_state,
        effective_stats=effective_stats,
    )