import random
from ..utils import roll_d20, stat_modifier
from .types import CombatRollResult

def resolve_player_attack(stats, enemy) -> CombatRollResult:
    modifier = stat_modifier(stats.strength)
    roll  = roll_d20()
    total = roll + modifier
    hit   = total >= enemy.defense
    damage = random.randint(1, 6) + max(0, modifier) if hit else 0
    return CombatRollResult(hit=hit, damage=damage, roll=roll, total=total)


def resolve_enemy_attack(enemy, stats) -> CombatRollResult:
    player_defense = 10 + stat_modifier(stats.agility)
    roll  = roll_d20()
    total = roll + enemy.attack_modifier
    hit   = total >= player_defense
    damage = random.randint(enemy.damage_min, enemy.damage_max) if hit else 0
    return CombatRollResult(hit=hit, damage=damage, roll=roll, total=total)


def get_active_combat_state(session):
    """
    Returns the session's active CombatState if one exists, else None.
    Read-only, does not modify database.
    """
    from ..models import CombatState
    try:
        cs = session.combat_state
        if cs.is_active:
            return cs
    except CombatState.DoesNotExist:
        pass
    return None


def initialize_combat_state(session, scene):
    """
    For a combat scene: returns an active CombatState, creating one if needed.
    If an inactive state exists for a combat scene, deletes and recreates it.
    For a non-combat scene: deactivates any lingering active CombatState and returns None.
    """
    from ..models import CombatEncounter, CombatState, EventLog
    if not scene.is_combat:
        try:
            cs = session.combat_state
            if cs.is_active:
                cs.is_active = False
                cs.save()
        except CombatState.DoesNotExist:
            pass
        return None

    try:
        cs = session.combat_state
        if cs.is_active:
            return cs
        cs.delete()
    except CombatState.DoesNotExist:
        pass

    encounter = CombatEncounter.objects.select_related('enemy').get(scene=scene)
    cs = CombatState.objects.create(
        session=session,
        enemy=encounter.enemy,
        enemy_hp=encounter.enemy.max_hp,
        turn_number=1,
        is_active=True,
    )
    EventLog.objects.create(
        session=session,
        text=f"You square up against {encounter.enemy.name}."
    )
    return cs


def resolve_combat_end(session, stats, inventory, completed_map, next_scene, combat_state, *, xp_award=0, ending_type='neutral'):
    from ..models import EventLog, CombatEncounter
    from .progression import maybe_complete_quest, award_xp, LEVEL_UP_FLAVOR
    from .inventory import award_scene_items
    from ..utils import get_effective_stats
    from .session import build_render_context

    try:
        encounter = CombatEncounter.objects.get(scene=session.current_scene)
    except CombatEncounter.DoesNotExist:
        encounter = None

    combat_state.is_active = False
    combat_state.save()

    session.current_scene = next_scene
    session.save()

    if encounter:
        if ending_type == 'victory' and encounter.victory_arrival_flavor:
            EventLog.objects.create(session=session, text=encounter.victory_arrival_flavor)
        elif ending_type == 'defeat' and encounter.defeat_arrival_flavor:
            EventLog.objects.create(session=session, text=encounter.defeat_arrival_flavor)

    quest_logs = maybe_complete_quest(session, stats, next_scene, completed_map)
    for log_text in quest_logs:
        EventLog.objects.create(session=session, text=log_text)

    awarded = award_scene_items(session, next_scene, inventory)
    for item, qty in awarded:
        EventLog.objects.create(session=session, text=f"You picked up: {item.name} x{qty}.")

    if xp_award:
        combat_levels = award_xp(session, stats, xp_award)
        EventLog.objects.create(session=session, text=f"+{xp_award} XP.")
        for new_level in combat_levels:
            EventLog.objects.create(session=session, text=LEVEL_UP_FLAVOR.get(new_level, "You feel stronger."))

    effective_stats = get_effective_stats(stats, inventory)
    next_combat_state = initialize_combat_state(session, next_scene)
    return build_render_context(
        session, next_scene, stats, effective_stats, inventory, completed_map,
        combat_state=next_combat_state,
    )
