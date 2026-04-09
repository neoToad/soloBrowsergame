import random

def roll_d20():
    return random.randint(1, 20)

def stat_modifier(stat_value):
    return (stat_value - 10) // 2

def get_notice_board(session, stats):
    """
    Returns a list of dicts describing each quest's availability
    for the given session and stats.

    Each dict has:
      quest         — the Quest instance
      status        — one of: 'available', 'locked', 'completed'
      endings       — list of CompletedQuest instances for this quest
                      (empty if not completed)
      lock_reason   — human readable string if status is 'locked',
                      else empty string
    """
    from .models import Quest, CompletedQuest

    completed_qs = CompletedQuest.objects.filter(
        session=session
    ).select_related('quest')
    completed_map = {cq.quest_id: cq for cq in completed_qs}

    quests = Quest.objects.filter(is_unlocked=True).select_related(
        'required_quest', 'entrance_scene'
    )

    board = []
    for quest in quests:
        lock_reason = ''

        # Check quest prerequisite
        if quest.required_quest:
            if quest.required_quest_id not in completed_map:
                lock_reason = (
                    f'Requires completion of: {quest.required_quest.title}'
                )

        # Check stat gate (only if not already locked)
        if not lock_reason and quest.required_stat:
            player_value = getattr(stats, quest.required_stat, 0)
            if player_value < quest.required_minimum:
                stat_label = quest.required_stat.capitalize()
                lock_reason = (
                    f'Requires {stat_label} {quest.required_minimum} '
                    f'(yours: {player_value})'
                )

        # Determine status
        if quest.id in completed_map:
            status = 'completed'
        elif lock_reason:
            status = 'locked'
        else:
            status = 'available'

        # Gather all completions for this quest (can be done multiple times)
        endings = CompletedQuest.objects.filter(
            session=session, quest=quest
        ).order_by('-completed_at')

        board.append({
            'quest': quest,
            'status': status,
            'endings': endings,
            'lock_reason': lock_reason,
        })

    return board
