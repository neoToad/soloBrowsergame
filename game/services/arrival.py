from django.db import transaction

from .progression import apply_stat_rewards, maybe_complete_quest
from .property_service import (
    apply_property_rewards,
    process_turn_income,
    get_turn_summary,
)
from .inventory import (
    award_scene_items,
    award_scene_contacts,
    award_scene_discovered_territories,
    apply_scene_gang_standing_changes,
    get_player_contacts,
    get_discovered_territories,
)
from .scene import consume_arrival_item


def process_arrival(session, stats, inventory, completed_map, next_scene, contacts=None):
    """
    Applies all arrival effects when the player transitions to next_scene.
    Returns (logs: list[str], turn_summary: dict | None).
    Callers are responsible for writing EventLog entries from the returned logs.
    """
    with transaction.atomic():
        if contacts is None:
            contacts = get_player_contacts(session)
        discovered_territories = get_discovered_territories(session)

        logs = []

        logs += apply_stat_rewards(session, stats, next_scene)
        logs += apply_property_rewards(session, next_scene)
        logs += consume_arrival_item(session, inventory, next_scene)

        quest_logs = maybe_complete_quest(session, stats, next_scene, completed_map)
        logs += quest_logs

        for item, qty in award_scene_items(session, next_scene, inventory):
            logs.append(f"You picked up: {item.name} x{qty}.")

        gained, lost = award_scene_contacts(session, next_scene, contacts)
        for contact in gained:
            logs.append(f"You gained a contact: {contact.name}.")
        for contact in lost:
            logs.append(f"You lost contact with {contact.name}.")
        for territory in award_scene_discovered_territories(session, next_scene, discovered_territories):
            logs.append(f"You discovered a territory: {territory.name}.")
        for gang, delta, new_total in apply_scene_gang_standing_changes(session, next_scene):
            sign = "+" if delta >= 0 else ""
            logs.append(f"Gang standing changed: {gang.name} {sign}{delta} (now {new_total}).")

        turn_summary = None
        if quest_logs:
            income_logs, income_totals = process_turn_income(session)
            logs += income_logs

            turn_summary = get_turn_summary(session, income_totals, [])

        return logs, turn_summary
