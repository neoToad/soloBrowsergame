# Game Design Reference

## Setting

Noir crime world. The player is a nobody climbing through Creston's criminal economy.
Tone is gritty, dry, and terse. See `QUEST_CONTENT_GUIDE.md` for writing guidance.

---

## Player Stats

All stats default to 5. Modifier formula: `(stat - 10) // 2`.

| DB field    | UI label   | Used for |
|-------------|------------|----------|
| `strength`  | Muscle     | Player attack rolls, physical checks, max HP scaling |
| `agility`   | Reflexes   | Player defense (`10 + agility modifier`), dodge checks |
| `intellect` | Cunning    | Planning/analysis checks |
| `charisma`  | Nerve      | Social pressure, persuasion, intimidation |
| `hp`        | HP         | Current health |
| `max_hp`    | Max HP     | Healing cap |

Passive item bonuses are applied via `get_effective_stats()`. Effective stats drive checks/rendering; persistent mutations write to `PlayerStats`.

---

## Scene Types

| Type | Behavior |
|---|---|
| `normal` | Standard narrative scene with choices |
| `hub` | Persistent location with notice board quest surfacing |
| `combat` | Uses `CombatEncounter`; regular choices hidden while active combat is in progress |
| `ending` | Quest terminus; completion and XP handled on arrival |

Ending scenes set `ending_type`: `victory`, `defeat`, or `neutral`.

---

## Combat System

- `CombatEncounter` links one enemy and routes to `victory_scene` / `defeat_scene`.
- Entering a combat scene initializes (or reuses) one active `CombatState` for the session.
- Combat is two-phase:
  1. Player attack resolves and logs; enemy counterattack is pre-rolled and stored.
  2. Player resolves enemy attack; HP/turn update; victory/defeat transitions execute.
- Stored enemy attack fields: `pending_enemy_roll`, `pending_enemy_total`, `pending_enemy_hit`, `pending_enemy_damage`.
- Player attack: `d20 + strength_modifier` vs `enemy.defense`; damage `d6 + max(0, strength_modifier)`.
- Enemy attack: `d20 + enemy.attack_modifier` vs `10 + agility_modifier`; damage `d(enemy.damage_min..enemy.damage_max)`.
- Combat victory grants XP via `XP_AWARDS['combat_victory']` and then routes through combat-end arrival processing.

---

## Item System

### Effect Types

| `effect_type` | Behavior |
|---|---|
| `heal_hp` | Restore `effect_value` HP (capped at `max_hp`) |
| `add_stat` | Permanently add `effect_value` to `effect_stat` |

### Passive Bonuses

Items can provide `passive_stat` + `passive_value` while carried; these are computed, not persisted.

### Consumables

- `is_consumable=True`: removed when used through item-use flow.
- Scene arrival can also consume one item via `Scene.consume_item`.

---

## Requirement / Gating System

- Quests and choices gate through `RequirementGroup` M2M.
- All groups attached to an object must pass (AND between groups).
- Within a group, `logic='all'` (AND) or `logic='any'` (OR).

### Condition Types

- `stat_gte`, `stat_lte`
- `has_item`, `missing_item`
- `quest_completed`, `quest_not_done`, `quest_ending`
- `level_gte`, `xp_gte`
- `has_flag`, `missing_flag`
- `has_contact`, `missing_contact`

---

## Flag System

Session-level boolean flags are stored in `GameSession.flags` (JSONField).

- Set/clear through choice fields: `set_flag_name`, `clear_flag_name`.
- Read in requirements via `has_flag` / `missing_flag`.
- Use `game/services/flags.py` helpers for mutation and checks.

---

## Notice Board

Hub scenes surface quests assigned through `Quest.hub_scenes`.

- Available: requirements pass and quest is surfaced/unlocked.
- Locked: surfaced but requirements fail.
- Completed: quest has `CompletedQuest` for the session unless repeatable behavior re-surfaces it.

---

## Arcs

`Arc` groups quests for sequencing/organization. `arc.order` and `quest.arc_order` define presentation order; hard gating should be modeled through requirements.
