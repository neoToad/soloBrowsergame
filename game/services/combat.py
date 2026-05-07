import random
from ..utils import roll_d20, stat_modifier
from .combat_engine import (
    build_enemy_attack_log,
    build_player_attack_log,
    resolve_enemy_attack_roll,
    resolve_player_attack_roll,
)
from .types import CombatRollResult, PendingEnemyAttack
from .types import GameplayError


def resolve_player_attack(stats, enemy) -> CombatRollResult:
    """Resolve one player attack roll against an enemy and return hit/damage details."""
    roll = roll_d20()
    damage_die = random.randint(1, 6)
    return resolve_player_attack_roll(stats, enemy, roll=roll, damage_die=damage_die)


def resolve_enemy_attack(enemy, stats) -> CombatRollResult:
    """Resolve one enemy attack roll against player stats and return hit/damage details."""
    roll = roll_d20()
    damage_die = random.randint(enemy.damage_min, enemy.damage_max)
    return resolve_enemy_attack_roll(enemy, stats, roll=roll, damage_die=damage_die)


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


def execute_player_attack(session, stats, inventory, completed_map, combat_state, effective_stats):
    """
    Resolve a full player attack turn: roll, update HP, queue enemy turn or flag victory.
    Returns (logs, context). Caller flushes logs and sets context['choices'] = [].
    """
    from ..utils import get_effective_stats, stat_modifier, RollResult, DamageResult
    from .session import build_render_context

    enemy = combat_state.enemy
    p = resolve_player_attack(effective_stats, enemy)
    str_mod = stat_modifier(effective_stats.strength)
    mod_str = f"+{str_mod}" if str_mod >= 0 else str(str_mod)

    if p.hit:
        combat_state.enemy_hp = max(0, combat_state.enemy_hp - p.damage)
        combat_state.save()

    logs = []
    player_attack_log = build_player_attack_log(
        roll=p.roll,
        mod_str=mod_str,
        total=p.total,
        defense=enemy.defense,
        hit=p.hit,
        damage=p.damage,
    )

    if combat_state.enemy_hp <= 0:
        if p.hit:
            logs.append(player_attack_log)
        logs.append(f"{enemy.name} goes down.")
        combat_state.pending_victory = True
        combat_state.save()
        roll_result = RollResult(
            roll=p.roll, modifier=str_mod, mod_display=mod_str,
            total=p.total, dc=enemy.defense, stat='strength', success=p.hit,
        )
        dmg_mod = max(0, str_mod)
        damage_result = DamageResult(
            die_roll=p.damage_die, die_label='d6',
            modifier=dmg_mod,
            mod_display=f"+{dmg_mod}" if dmg_mod >= 0 else str(dmg_mod),
            total=p.damage,
        )
        context = build_render_context(
            session, session.current_scene, stats, effective_stats, inventory, completed_map,
            combat_state=combat_state,
            roll_result=roll_result,
            damage_result=damage_result,
        )
        return logs, context

    e = resolve_enemy_attack(enemy, effective_stats)
    logs.append(player_attack_log)

    queue_enemy_attack(combat_state, e)

    effective_stats = get_effective_stats(stats, inventory)
    roll_result = RollResult(
        roll=p.roll, modifier=str_mod, mod_display=mod_str,
        total=p.total, dc=enemy.defense, stat='strength', success=p.hit,
    )
    damage_result = None
    if p.hit:
        dmg_mod = max(0, str_mod)
        dmg_mod_str = f"+{dmg_mod}" if dmg_mod >= 0 else str(dmg_mod)
        damage_result = DamageResult(
            die_roll=p.damage_die, die_label='d6',
            modifier=dmg_mod, mod_display=dmg_mod_str,
            total=p.damage,
        )
    context = build_render_context(
        session, session.current_scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state,
        roll_result=roll_result,
        damage_result=damage_result,
    )
    return logs, context


def execute_enemy_attack(session, stats, inventory, completed_map, combat_state, effective_stats):
    """
    Apply the queued enemy attack and advance combat. Mutates stats and combat_state.
    Returns (logs, context). On defeat, returns pre-defeat logs followed by combat-end logs
    so callers can persist in order.
    Raises CombatEncounter.DoesNotExist if the encounter row is missing.
    """
    from ..models import CombatEncounter
    from ..utils import get_effective_stats, stat_modifier, RollResult, DamageResult
    from .session import build_render_context

    encounter = CombatEncounter.objects.get(scene=session.current_scene)

    enemy = combat_state.enemy
    player_defense = 10 + stat_modifier(effective_stats.agility)
    e_mod_str = f"+{enemy.attack_modifier}" if enemy.attack_modifier >= 0 else str(enemy.attack_modifier)

    enemy_attack = consume_enemy_attack(combat_state)
    e_roll = enemy_attack.roll
    e_total = enemy_attack.total
    e_hit = enemy_attack.hit
    e_dmg = enemy_attack.damage

    logs = []
    if e_hit:
        stats.hp = max(0, stats.hp - e_dmg)
    logs.append(
        build_enemy_attack_log(
            enemy_name=enemy.name,
            roll=e_roll,
            mod_str=e_mod_str,
            total=e_total,
            defense=player_defense,
            hit=e_hit,
            damage=e_dmg,
        )
    )

    combat_state.turn_number += 1
    combat_state.save(update_fields=["turn_number"])
    stats.save()

    if stats.hp <= 0:
        logs.append("You're down. You lose consciousness.")
        end_logs, context = resolve_combat_end(
            session, stats, inventory, completed_map,
            encounter.defeat_scene, combat_state,
            ending_type='defeat',
        )
        return [*logs, *end_logs], context

    effective_stats = get_effective_stats(stats, inventory)
    roll_result = RollResult(
        roll=e_roll, modifier=enemy.attack_modifier, mod_display=e_mod_str,
        total=e_total, dc=player_defense, stat=enemy.name, success=e_hit,
    )
    damage_result = None
    if e_hit:
        dmg_label = f'd({enemy.damage_min}–{enemy.damage_max})'
        damage_result = DamageResult(
            die_roll=e_dmg, die_label=dmg_label, modifier=0, mod_display='+0', total=e_dmg,
        )
    context = build_render_context(
        session, session.current_scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state,
        roll_result=roll_result,
        damage_result=damage_result,
    )
    return logs, context


def resolve_combat_end(session, stats, inventory, completed_map, next_scene, combat_state, *, xp_award=0, ending_type='neutral'):
    """Finalize combat, transition to next scene, and return (logs, render context)."""
    from ..models import CombatEncounter
    from .progression import award_xp, LEVEL_UP_FLAVOR
    from .arrival import process_arrival
    from ..utils import get_effective_stats
    from .session import build_render_context

    try:
        encounter = CombatEncounter.objects.get(scene=session.current_scene)
    except CombatEncounter.DoesNotExist:
        encounter = None

    if next_scene is None:
        scene_key = session.current_scene.key if session.current_scene else "unknown"
        if ending_type == 'victory':
            missing_field = "victory_scene"
        elif ending_type == 'defeat':
            missing_field = "defeat_scene"
        else:
            missing_field = "destination scene"
        raise GameplayError(
            f"Combat encounter on scene '{scene_key}' is missing {missing_field}. "
            f"Set CombatEncounter.{missing_field} in quest content.",
            status=400,
        )

    combat_state.is_active = False
    combat_state.save()

    session.current_scene = next_scene
    session.save()

    log_queue = []
    victory_flavor = ""

    if encounter:
        if ending_type == 'victory' and encounter.victory_arrival_flavor:
            victory_flavor = encounter.victory_arrival_flavor.strip()
            log_queue.append(victory_flavor)
        elif ending_type == 'defeat' and encounter.defeat_arrival_flavor:
            log_queue.append(encounter.defeat_arrival_flavor)

    cash_before = stats.cash
    heat_before = stats.heat
    rep_before = stats.rep
    arrival_logs, _ = process_arrival(session, stats, inventory, completed_map, next_scene)
    cash_delta = stats.cash - cash_before
    heat_delta = stats.heat - heat_before
    rep_delta = stats.rep - rep_before
    if ending_type == 'victory':
        arrival_logs = [
            line for line in arrival_logs
            if not (
                line.startswith("Cash: ")
                or line.startswith("Heat: ")
                or line.startswith("Reputation: ")
            )
        ]
    log_queue.extend(arrival_logs)

    if xp_award:
        combat_levels = award_xp(session, stats, xp_award)
        if ending_type == 'victory':
            reward_bits = [f"{xp_award} XP"]
            if cash_delta:
                cash_sign = "+" if cash_delta > 0 else "-"
                reward_bits.append(f"{cash_sign}${abs(cash_delta)} cash")
            if heat_delta:
                heat_sign = "+" if heat_delta > 0 else "-"
                reward_bits.append(f"{heat_sign}{abs(heat_delta)} heat")
            if rep_delta:
                rep_sign = "+" if rep_delta > 0 else "-"
                reward_bits.append(f"{rep_sign}{abs(rep_delta)} rep")
            combined = f"You gained {', '.join(reward_bits)}."
            if victory_flavor:
                combined = f"{victory_flavor} {combined}"
                if victory_flavor in log_queue:
                    log_queue.remove(victory_flavor)
            log_queue.append(combined)
        else:
            log_queue.append(f"+{xp_award} XP.")
        for new_level in combat_levels:
            log_queue.append(LEVEL_UP_FLAVOR.get(new_level, "You feel stronger."))

    next_combat_state, combat_init_log = initialize_combat_state(session, next_scene)
    if combat_init_log:
        log_queue.append(combat_init_log)

    effective_stats = get_effective_stats(stats, inventory)
    context = build_render_context(
        session, next_scene, stats, effective_stats, inventory, completed_map,
        combat_state=next_combat_state,
    )
    return log_queue, context


def queue_enemy_attack(combat_state, attack: CombatRollResult) -> None:
    combat_state.pending_enemy_roll = attack.roll
    combat_state.pending_enemy_total = attack.total
    combat_state.pending_enemy_hit = attack.hit
    combat_state.pending_enemy_damage = attack.damage
    combat_state.save(
        update_fields=[
            "pending_enemy_roll",
            "pending_enemy_total",
            "pending_enemy_hit",
            "pending_enemy_damage",
        ]
    )


def consume_enemy_attack(combat_state) -> PendingEnemyAttack:
    if (
        combat_state.pending_enemy_roll is None
        or combat_state.pending_enemy_total is None
        or combat_state.pending_enemy_hit is None
        or combat_state.pending_enemy_damage is None
    ):
        raise ValueError("No pending enemy attack to consume.")
    attack = PendingEnemyAttack(
        roll=combat_state.pending_enemy_roll,
        total=combat_state.pending_enemy_total,
        hit=bool(combat_state.pending_enemy_hit),
        damage=combat_state.pending_enemy_damage,
    )
    clear_enemy_attack(combat_state)
    return attack


def clear_enemy_attack(combat_state) -> None:
    combat_state.pending_enemy_roll = None
    combat_state.pending_enemy_total = None
    combat_state.pending_enemy_hit = None
    combat_state.pending_enemy_damage = None
    combat_state.save(
        update_fields=[
            "pending_enemy_roll",
            "pending_enemy_total",
            "pending_enemy_hit",
            "pending_enemy_damage",
        ]
    )
