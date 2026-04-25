import random
from ..utils import roll_d20, stat_modifier
from .types import CombatRollResult

def resolve_player_attack(stats, enemy) -> CombatRollResult:
    """Resolve one player attack roll against an enemy and return hit/damage details."""
    modifier = stat_modifier(stats.strength)
    roll  = roll_d20()
    total = roll + modifier
    hit   = total >= enemy.defense
    damage_die = random.randint(1, 6) if hit else 0
    damage     = damage_die + max(0, modifier) if hit else 0
    return CombatRollResult(hit=hit, damage=damage, damage_die=damage_die, roll=roll, total=total)


def resolve_enemy_attack(enemy, stats) -> CombatRollResult:
    """Resolve one enemy attack roll against player stats and return hit/damage details."""
    player_defense = 10 + stat_modifier(stats.agility)
    roll  = roll_d20()
    total = roll + enemy.attack_modifier
    hit   = total >= player_defense
    damage_die = random.randint(enemy.damage_min, enemy.damage_max) if hit else 0
    return CombatRollResult(hit=hit, damage=damage_die, damage_die=damage_die, roll=roll, total=total)


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
    For a combat scene: returns (CombatState, init_log | None), creating the state if needed.
    If an inactive state exists for a combat scene, deletes and recreates it.
    For a non-combat scene: deactivates any lingering active CombatState and returns (None, None).
    Callers are responsible for writing the init_log to EventLog.
    """
    from ..models import CombatEncounter, CombatState
    if not scene.is_combat:
        try:
            cs = session.combat_state
            if cs.is_active:
                cs.is_active = False
                cs.save()
        except CombatState.DoesNotExist:
            pass
        return None, None

    try:
        cs = session.combat_state
        if cs.is_active:
            return cs, None
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
    return cs, f"You square up against {encounter.enemy.name}."


def resolve_combat_end(session, stats, inventory, completed_map, next_scene, combat_state, *, xp_award=0, ending_type='neutral'):
    """Finalize combat, transition to next scene, apply arrival/XP effects, and return render context."""
    from ..models import EventLog, CombatEncounter
    from .progression import award_xp, LEVEL_UP_FLAVOR
    from .arrival import process_arrival
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

    log_queue = []

    if encounter:
        if ending_type == 'victory' and encounter.victory_arrival_flavor:
            log_queue.append(encounter.victory_arrival_flavor)
        elif ending_type == 'defeat' and encounter.defeat_arrival_flavor:
            log_queue.append(encounter.defeat_arrival_flavor)

    arrival_logs, _ = process_arrival(session, stats, inventory, completed_map, next_scene)
    log_queue.extend(arrival_logs)

    if xp_award:
        combat_levels = award_xp(session, stats, xp_award)
        log_queue.append(f"+{xp_award} XP.")
        for new_level in combat_levels:
            log_queue.append(LEVEL_UP_FLAVOR.get(new_level, "You feel stronger."))

    next_combat_state, combat_init_log = initialize_combat_state(session, next_scene)
    if combat_init_log:
        log_queue.append(combat_init_log)

    for text in log_queue:
        EventLog.objects.create(session=session, text=text)

    effective_stats = get_effective_stats(stats, inventory)
    return build_render_context(
        session, next_scene, stats, effective_stats, inventory, completed_map,
        combat_state=next_combat_state,
    )
