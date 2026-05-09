from .types import CombatRollResult


def resolve_player_attack_roll(stats, enemy, *, roll: int, damage_die: int) -> CombatRollResult:
    modifier = _stat_modifier(stats.strength)
    total = roll + modifier
    hit = total >= enemy.defense
    damage = (damage_die + max(0, modifier)) if hit else 0
    applied_die = damage_die if hit else 0
    return CombatRollResult(hit=hit, damage=damage, damage_die=applied_die, roll=roll, total=total)


def resolve_enemy_attack_roll(enemy, stats, *, roll: int, damage_die: int) -> CombatRollResult:
    player_defense = 10 + _stat_modifier(stats.agility)
    total = roll + enemy.attack_modifier
    hit = total >= player_defense
    applied_die = damage_die if hit else 0
    return CombatRollResult(hit=hit, damage=applied_die, damage_die=applied_die, roll=roll, total=total)


def build_player_attack_log(*, roll: int, mod_str: str, total: int, defense: int, hit: bool, damage: int) -> str:
    if hit:
        return f"You move on him - roll {roll} ({mod_str}) = {total} vs {defense} - Hit! {damage} damage."
    return f"You move on him - roll {roll} ({mod_str}) = {total} vs {defense} - Missed."


def build_enemy_attack_log(
    *, enemy_name: str, roll: int, mod_str: str, total: int, defense: int, hit: bool, damage: int
) -> str:
    if hit:
        return f"{enemy_name} comes at you - roll {roll} ({mod_str}) = {total} vs {defense} - Hit! {damage} damage."
    return f"{enemy_name} comes at you - roll {roll} ({mod_str}) = {total} vs {defense} - Missed."


def _stat_modifier(stat: int) -> int:
    return (stat - 10) // 2


