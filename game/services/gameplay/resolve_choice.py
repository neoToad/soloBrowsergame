from ..flags import set_flag, clear_flag
from ..scene import resolve_roll
from ..arrival import process_arrival
from ..session import advance_to_scene
from ..combat import initialize_combat_state
from ...models.events import flush_event_log, log_event
from ...utils import get_effective_stats
from ..types import ChoiceResult, GameplayError


def resolve_choice(session_context, choice) -> ChoiceResult:
    session, stats, inventory, effective_stats, completed_map = session_context

    if choice.scene_id != session.current_scene_id:
        raise GameplayError("Choice is not available from your current scene.", status=403)

    scene = choice.scene
    log_queue = []

    if scene.requires_roll:
        next_scene, roll_log, roll_result = resolve_roll(scene, choice, effective_stats)
        log_queue.append(roll_log)
        if next_scene is None:
            if roll_result.success:
                missing_target = "success_scene"
            else:
                missing_target = "failure_scene"
            raise GameplayError(
                f"Roll-routed choice is missing {missing_target}. "
                f"Set Choice.{missing_target} in quest content.",
                status=400,
            )
    else:
        next_scene = choice.target_scene
        if next_scene is None:
            raise GameplayError("This choice has no destination configured.", status=500)
        roll_result = None

    if roll_result and not roll_result.success and choice.failure_arrival_flavor:
        log_queue.append(choice.failure_arrival_flavor)
    elif choice.arrival_flavor:
        log_queue.append(choice.arrival_flavor)

    if choice.set_flag_name:
        set_flag(session, choice.set_flag_name)
    if choice.clear_flag_name:
        clear_flag(session, choice.clear_flag_name)

    advance_to_scene(session, next_scene)

    arrival_logs, turn_summary = process_arrival(session, stats, inventory, completed_map, next_scene)
    log_queue.extend(arrival_logs)
    flush_event_log(session, log_queue)

    combat_state, combat_init_log = initialize_combat_state(session, next_scene)
    if combat_init_log:
        log_event(session, combat_init_log)

    effective_stats = get_effective_stats(stats, inventory)

    return ChoiceResult(
        next_scene=next_scene,
        combat_state=combat_state,
        effective_stats=effective_stats,
        roll_result=roll_result,
        turn_summary=turn_summary,
    )
