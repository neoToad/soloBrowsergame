from ..models import RivalClaim
from .progression import apply_stat_rewards, maybe_complete_quest
from .property_service import (
    apply_property_rewards,
    process_turn_income,
    check_rival_contests,
    get_turn_summary,
    resolve_contest,
)
from .inventory import award_scene_items
from .scene import consume_arrival_item


def process_arrival(session, stats, inventory, completed_map, next_scene):
    """
    Applies all arrival effects when the player transitions to next_scene.
    Returns (logs: list[str], turn_summary: dict | None).
    Callers are responsible for writing EventLog entries from the returned logs.
    """
    logs = []

    logs += apply_stat_rewards(session, stats, next_scene)
    logs += apply_property_rewards(session, next_scene)
    logs += consume_arrival_item(session, inventory, next_scene)

    quest_logs = maybe_complete_quest(session, stats, next_scene, completed_map)
    logs += quest_logs

    for item, qty in award_scene_items(session, next_scene, inventory):
        logs.append(f"You picked up: {item.name} x{qty}.")

    turn_summary = None
    if quest_logs:
        active_claim = RivalClaim.objects.filter(
            player_property__session=session,
            resolution_scene=next_scene,
        ).first()
        if active_claim:
            logs.append(resolve_contest(session, active_claim, next_scene.ending_type))

        income_logs, income_totals = process_turn_income(session)
        logs += income_logs

        contest_warning, unlocked_scene = check_rival_contests(session)
        if contest_warning:
            logs.append(contest_warning)
        newly_unlocked = [unlocked_scene] if unlocked_scene else []

        turn_summary = get_turn_summary(session, income_totals, newly_unlocked)

    return logs, turn_summary