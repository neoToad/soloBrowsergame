def award_xp(session, stats, amount):
    """
    Adds `amount` XP to stats.experience.
    Handles multiple level-ups if a single award bridges more than one threshold.
    Awards unspent stat points from lifetime XP milestones (1 per 100 XP).
    Uses stat_points_awarded as the high-water mark to avoid over/under granting.
    Saves stats before returning.
    Returns a list of new level numbers reached (empty list if no level-up).
    Callers are responsible for creating EventLog entries from the return value.
    """
    levels_gained = []
    stats.experience += amount

    while stats.level < MAX_LEVEL:
        next_level = stats.level + 1
        if stats.experience >= XP_THRESHOLDS[next_level]:
            stats.level = next_level
            levels_gained.append(next_level)
        else:
            break

    eligible_points = stats.experience // 100
    new_points = max(0, eligible_points - stats.stat_points_awarded)
    if new_points:
        stats.stat_points += new_points
    stats.stat_points_awarded = eligible_points

    stats.save()
    return levels_gained


def spend_stat_point(stats, stat_name, stat_field_map):
    """
    Spends one unspent stat point on one of the four spendable player stats.
    Returns a tuple: (public_stat_name, db_field_name, new_value).
    Raises ValueError on invalid stat name or when no points are available.
    """
    if stats.stat_points <= 0:
        raise ValueError("No stat points available.")

    public_name = (stat_name or "").lower()
    field = stat_field_map.get(public_name)
    if not field:
        raise ValueError("Invalid stat.")

    current_val = getattr(stats, field)
    setattr(stats, field, current_val + 1)
    stats.stat_points -= 1
    if field == 'strength':
        from ..utils import compute_max_hp
        stats.max_hp = compute_max_hp(stats.strength)
        stats.hp = min(stats.hp, stats.max_hp)
    stats.save()
    return public_name, field, current_val + 1


def apply_stat_rewards(session, stats, obj):
    """
    Applies cash_change, rep_change, heat_change from `obj` (Scene or Choice) to stats.
    Returns a list of log strings. Callers are responsible for logging.
    Saves stats if any change occurred.
    """
    logs = []
    changed = False

    if hasattr(obj, 'cash_change') and obj.cash_change != 0:
        stats.cash += obj.cash_change
        prefix = "+" if obj.cash_change > 0 else ""
        logs.append(f"Cash: {prefix}${obj.cash_change}")
        changed = True

    if hasattr(obj, 'rep_change') and obj.rep_change != 0:
        stats.rep += obj.rep_change
        prefix = "+" if obj.rep_change > 0 else ""
        logs.append(f"Reputation: {prefix}{obj.rep_change}")
        changed = True

    if hasattr(obj, 'heat_change') and obj.heat_change != 0:
        stats.heat = max(0, stats.heat + obj.heat_change)
        prefix = "+" if obj.heat_change > 0 else ""
        logs.append(f"Heat: {prefix}{obj.heat_change}")
        changed = True

    if changed:
        stats.save()

    return logs


def maybe_complete_quest(session, stats, next_scene, completed_map):
    """
    If next_scene is a quest ending that hasn't been recorded yet,
    creates CompletedQuest, awards XP, and handles level-ups.
    Updates completed_map in place.
    Returns a list of log message strings (completion, XP, level-up
    flavor) so the caller can create EventLog entries — this function
    must not create EventLog entries itself.
    """
    from ..models import CompletedQuest
    log_messages = []

    quest = next_scene.quest if next_scene.is_ending else None
    if quest:
        completed_quest, created = CompletedQuest.objects.get_or_create(
            session=session,
            quest=quest,
            defaults={'ending_type': next_scene.ending_type},
        )
        if created:
            log_messages.append(
                f"You have completed: {quest.title} ({next_scene.get_ending_type_display()})"
            )
            completed_map[quest.id] = completed_quest.ending_type

            # AWARD XP
            xp_amount = XP_AWARDS.get(completed_quest.ending_type, 0)
            if xp_amount:
                levels = award_xp(session, stats, xp_amount)
                log_messages.append(f"+{xp_amount} XP.")
                for new_level in levels:
                    flavor = LEVEL_UP_FLAVOR.get(new_level, "You feel stronger.")
                    log_messages.append(flavor)

    return log_messages

XP_THRESHOLDS = {
    1: 0,
    2: 200,
    3: 600,
    4: 1300,
    5: 2400,
    6: 4000,
    7: 6200,
}

MAX_LEVEL = 7

RANK_TITLES = {
    1: 'Errand Boy',
    2: 'Corner Operator',
    3: 'Crew Member',
    4: 'Made Man',
    5: 'Lieutenant',
    6: 'Underboss',
    7: 'Boss',
}

LEVEL_UP_FLAVOR = {
    2: "Word travels fast. You're moving up.",
    3: "The crew is taking notice.",
    4: "You've earned your stripes.",
    5: "They're calling your name across the city.",
    6: "Nobody moves without your say-so.",
    7: "You run this town. Act like it.",
}

XP_AWARDS = {
    'victory':        150,
    'neutral':         75,
    'defeat':          25,
    'combat_victory':  50,
}
