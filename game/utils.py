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


def get_player_inventory(session):
    """
    Returns a dict keyed by item_id: {item_id: PlayerInventory instance}.
    Used by Requirement.evaluate() and get_available_choices().
    """
    from .models import PlayerInventory
    qs = PlayerInventory.objects.filter(session=session).select_related('item')
    return {pi.item_id: pi for pi in qs}


def award_scene_items(session, scene, inventory):
    """
    Awards all SceneItems attached to `scene` to the session.
    Respects award_once: skips items the session already holds when award_once=True.
    Updates `inventory` dict in-place so callers see fresh data.
    Returns a list of (item, quantity) tuples for every item actually awarded,
    so the caller can log them.
    """
    from .models import PlayerInventory
    awarded = []
    for scene_item in scene.scene_items.select_related('item').all():
        item = scene_item.item
        if scene_item.award_once and item.id in inventory:
            continue
        pi, created = PlayerInventory.objects.get_or_create(
            session=session,
            item=item,
            defaults={'quantity': 0}
        )
        pi.quantity += scene_item.quantity
        pi.save()
        inventory[item.id] = pi          # keep caller's dict current
        awarded.append((item, scene_item.quantity))
    return awarded


def consume_item(session, item, inventory):
    """
    Removes one of `item` from the session's inventory.
    Deletes the PlayerInventory row when quantity reaches 0.
    Updates `inventory` dict in-place.
    No-ops silently if the item is not held.
    """
    pi = inventory.get(item.id)
    if not pi:
        return
    pi.quantity -= 1
    if pi.quantity <= 0:
        pi.delete()
        inventory.pop(item.id, None)
    else:
        pi.save()
        inventory[item.id] = pi
