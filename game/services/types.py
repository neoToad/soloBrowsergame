from dataclasses import dataclass, field


@dataclass
class RollResult:
    roll:        int
    modifier:    int
    mod_display: str
    total:       int
    dc:          int
    stat:        str
    success:     bool


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