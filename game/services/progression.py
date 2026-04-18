
from django.db import IntegrityError


def award_xp(session, stats, amount):
    """
    Adds `amount` XP to stats.experience.
    Handles multiple level-ups if a single award bridges more than one threshold.
    Awards 1 stat_point per level gained. Caps at MAX_LEVEL.
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
            stats.stat_points += 1
            levels_gained.append(next_level)
        else:
            break

    stats.save()
    return levels_gained


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

    quest = next_scene.quests.first() if next_scene.is_ending else None
    if quest:
        if not CompletedQuest.objects.filter(session=session, quest=quest).exists():
            try:
                CompletedQuest.objects.create(
                    session=session,
                    quest=quest,
                    ending_type=next_scene.ending_type
                )
            except IntegrityError:
                return log_messages
            log_messages.append(
                f"You have completed: {quest.title} ({next_scene.get_ending_type_display()})"
            )
            completed_map[quest.id] = next_scene.ending_type

            # AWARD XP
            xp_amount = XP_AWARDS.get(next_scene.ending_type, 0)
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
