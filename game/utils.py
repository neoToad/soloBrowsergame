import random
from types import SimpleNamespace
from collections import defaultdict

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
    from .models import Quest, CompletedQuest, PlayerContext

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


def get_effective_stats(stats, inventory):
    """
    Returns a SimpleNamespace with effective stat values after applying all
    passive bonuses from carried items (items with passive_stat and passive_value set).

    The returned object supports getattr() on the same field names as PlayerStats:
    strength, agility, intellect, charisma, hp, max_hp, level, experience, stat_points.

    Also exposes `bonuses` — a dict of {field_name: total_bonus} — for display use.

    IMPORTANT: The returned object is read-only for display and dice rolls.
    Always write mutations (damage, healing, stat changes) back to the original
    PlayerStats instance, then call get_effective_stats() again if needed.
    """
    bonuses = {}
    for pi in inventory.values():
        item = pi.item
        if item.passive_stat and item.passive_value:
            bonuses[item.passive_stat] = (
                bonuses.get(item.passive_stat, 0) + item.passive_value
            )

    return SimpleNamespace(
        strength   = stats.strength  + bonuses.get('strength',  0),
        agility    = stats.agility   + bonuses.get('agility',   0),
        intellect  = stats.intellect + bonuses.get('intellect', 0),
        charisma   = stats.charisma  + bonuses.get('charisma',  0),
        hp         = stats.hp,
        max_hp     = stats.max_hp,
        level      = stats.level,
        experience = stats.experience,
        stat_points = stats.stat_points,
        bonuses    = bonuses,
    )


def resolve_player_attack(stats, enemy):
    """
    Resolves one player attack against enemy.
    Player rolls: d20 + stat_modifier(strength) vs enemy.defense.
    Damage on hit: d6 + max(0, stat_modifier(strength)).
    Returns (hit: bool, damage: int, roll: int, total: int).
    """
    modifier = stat_modifier(stats.strength)
    roll  = roll_d20()
    total = roll + modifier
    hit   = total >= enemy.defense
    damage = 0
    if hit:
        damage = random.randint(1, 6) + max(0, modifier)
    return hit, damage, roll, total


def resolve_enemy_attack(enemy, stats):
    """
    Resolves one enemy attack against the player.
    Enemy rolls: d20 + enemy.attack_modifier vs (10 + stat_modifier(agility)).
    Damage on hit: random(enemy.damage_min, enemy.damage_max).
    Returns (hit: bool, damage: int, roll: int, total: int).
    """
    player_defense = 10 + stat_modifier(stats.agility)
    roll  = roll_d20()
    total = roll + enemy.attack_modifier
    hit   = total >= player_defense
    damage = 0
    if hit:
        damage = random.randint(enemy.damage_min, enemy.damage_max)
    return hit, damage, roll, total


# ── XP / LEVELING CONSTANTS ──────────────────────────────────────────────────

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

LEVEL_UP_FLAVOR = [
    "Word travels fast. You're moving up.",        # → level 2
    "The crew is taking notice.",                  # → level 3
    "You've earned your stripes.",                 # → level 4
    "They're calling your name across the city.",  # → level 5
    "Nobody moves without your say-so.",           # → level 6
    "You run this town. Act like it.",             # → level 7
]

XP_AWARDS = {
    'victory':        150,
    'neutral':         75,
    'defeat':          25,
    'combat_victory':  50,
}


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
    from .models import CompletedQuest
    log_messages = []

    if next_scene.is_ending and next_scene.quest:
        if not CompletedQuest.objects.filter(session=session, quest=next_scene.quest).exists():
            CompletedQuest.objects.create(
                session=session,
                quest=next_scene.quest,
                ending_type=next_scene.ending_type
            )
            log_messages.append(
                f"You have completed: {next_scene.quest.title} ({next_scene.get_ending_type_display()})"
            )
            completed_map[next_scene.quest_id] = next_scene.ending_type

            # AWARD XP
            xp_amount = XP_AWARDS.get(next_scene.ending_type, 0)
            if xp_amount:
                levels = award_xp(session, stats, xp_amount)
                log_messages.append(f"+{xp_amount} XP.")
                for new_level in levels:
                    flavor = LEVEL_UP_FLAVOR[new_level - 2]
                    log_messages.append(flavor)

    return log_messages
