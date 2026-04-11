from ..constants import NOTICE_BOARD_SCENE_KEY

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
    from .inventory import get_player_inventory
    from ..models import Quest, CompletedQuest, PlayerContext
    from collections import defaultdict

    completed_qs = CompletedQuest.objects.filter(
        session=session
    ).select_related('quest')
    completed_map = {cq.quest_id: cq.ending_type for cq in completed_qs}

    # Group endings by quest in memory to avoid N+1 query
    endings_by_quest = defaultdict(list)
    for cq in sorted(completed_qs, key=lambda x: x.completed_at, reverse=True):
        endings_by_quest[cq.quest_id].append(cq)

    inventory = get_player_inventory(session)

    quests = Quest.objects.filter(is_unlocked=True).select_related(
        'entrance_scene'
    ).prefetch_related('requirements__requirements')

    board = []
    ctx = PlayerContext(stats=stats, inventory=inventory, completed_map=completed_map)
    for quest in quests:
        lock_reason = ''

        # RequirementGroup gate — all groups must pass
        if quest.requirements.exists():
            for rg in quest.requirements.all():
                if not rg.evaluate(ctx):
                    lock_reason = f'Requirements not met: {rg.label}'
                    break

        # Determine status
        if quest.id in completed_map:
            status = 'completed'
        elif lock_reason:
            status = 'locked'
        else:
            status = 'available'

        # Gather all completions for this quest
        endings = endings_by_quest[quest.id]

        board.append({
            'quest': quest,
            'status': status,
            'endings': endings,
            'lock_reason': lock_reason,
        })

    return board


def get_available_choices(scene, effective_stats, inventory, completed_map):
    from ..models import PlayerContext
    ctx = PlayerContext(
        stats=effective_stats,
        inventory=inventory,
        completed_map=completed_map
    )
    choices = []
    for choice in scene.choices.all():
        if choice.requirements.exists():
            passed = all(
                rg.evaluate(ctx)
                for rg in choice.requirements.all()
            )
            if not passed:
                continue
        choices.append(choice)
    return choices


def get_notice_board_for_scene(session, stats, scene):
    if scene.key == NOTICE_BOARD_SCENE_KEY:
        return get_notice_board(session, stats)
    return None
