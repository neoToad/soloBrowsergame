from dataclasses import dataclass, field


class GameplayError(Exception):
    """Raised by gameplay use-case services for expected rule violations."""
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


@dataclass
class ChoiceResult:
    next_scene:      object
    combat_state:    object
    effective_stats: object
    roll_result:     object
    turn_summary:    object


@dataclass
class QuestStartResult:
    next_scene:      object
    combat_state:    object
    effective_stats: object


@dataclass
class UseItemResult:
    effective_stats: object
    combat_state:    object


@dataclass
class CombatRollResult:
    hit:        bool
    damage:     int
    damage_die: int   # raw die value before modifier
    roll:       int
    total:      int


@dataclass(frozen=True)
class PendingEnemyAttack:
    roll: int
    total: int
    hit: bool
    damage: int


@dataclass
class DamageResult:
    die_roll:    int
    die_label:   str
    modifier:    int
    mod_display: str
    total:       int


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
