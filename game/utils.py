import random
from dataclasses import dataclass, field

def roll_d20():
    return random.randint(1, 20)

def stat_modifier(stat_value):
    return (stat_value - 10) // 2


@dataclass
class EffectiveStats:
    strength:    int
    agility:     int
    intellect:   int
    charisma:    int
    hp:          int
    max_hp:      int
    level:       int
    experience:  int
    stat_points: int
    cash:        int
    heat:        int
    rep:         int
    bonuses:     dict = field(default_factory=dict)


def get_effective_stats(stats, inventory) -> EffectiveStats:
    """
    Returns an EffectiveStats dataclass with effective stat values after applying
    all passive bonuses from carried items (passive_stat / passive_value set).

    Also exposes `bonuses` — a dict of {field_name: total_bonus} — for display use.

    IMPORTANT: The returned object is read-only for display and dice rolls.
    Always write mutations (damage, healing, stat changes) back to the original
    PlayerStats instance, then call get_effective_stats() again if needed.
    """
    bonuses: dict = {}
    for pi in inventory.values():
        item = pi.item
        if item.passive_stat and item.passive_value:
            bonuses[item.passive_stat] = (
                bonuses.get(item.passive_stat, 0) + item.passive_value
            )

    return EffectiveStats(
        strength    = stats.strength  + bonuses.get('strength',  0),
        agility     = stats.agility   + bonuses.get('agility',   0),
        intellect   = stats.intellect + bonuses.get('intellect', 0),
        charisma    = stats.charisma  + bonuses.get('charisma',  0),
        hp          = stats.hp,
        max_hp      = stats.max_hp,
        level       = stats.level,
        experience  = stats.experience,
        stat_points = stats.stat_points,
        cash        = stats.cash,
        heat        = stats.heat,
        rep         = stats.rep,
        bonuses     = bonuses,
    )
