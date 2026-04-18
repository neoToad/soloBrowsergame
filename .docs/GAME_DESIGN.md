# Game Design Reference

## Setting

Noir crime world. The player is a nobody climbing the ranks of a criminal organization.
Tone is gritty, dry, and terse. See `CONTENT_GUIDE.md` for writing guidance.

---

## Player Stats

All stats default to 5. Modifier formula: `(stat - 10) // 2` (D&D-style, so 5 → -3).

| DB field    | UI label   | Used for                                  |
|-------------|------------|-------------------------------------------|
| `strength`  | Muscle     | Melee attack rolls, physical skill checks |
| `agility`   | Reflexes   | Player defense (`10 + agility modifier`), dodge checks |
| `intellect` | Cunning    | Skill checks requiring wit or planning    |
| `charisma`  | Nerve      | Persuasion, intimidation, social checks   |
| `hp`        | HP         | Current health; combat damage reduces this |
| `max_hp`    | Max HP     | Cap for healing; starts at 20             |

Passive item bonuses are applied on top via `get_effective_stats()` — effective values are used for all rolls and display, but mutations always go to the raw `PlayerStats`.

---

## Scene Types

| Type     | Behaviour                                                                  |
|----------|----------------------------------------------------------------------------|
| `normal` | Standard narrative scene with choices                                      |
| `hub`    | Persistent home area; choices are always available; hosts a notice board   |
| `combat` | Triggers a `CombatEncounter`; standard choices are hidden during combat    |
| `ending` | Quest terminus; triggers `maybe_complete_quest()` on arrival               |

Ending scenes additionally have an `ending_type`: `victory`, `defeat`, or `neutral`.

---

## Combat System

- A `CombatEncounter` attaches one `Enemy` to a `Scene`.
- On entering a combat scene, a `CombatState` is created (or retrieved) for the session.
- Each round: player attacks, then enemy attacks back (if still alive).
- **Player attack**: `d20 + strength_modifier` vs `enemy.defense`. Hit deals `d(damage_min–damage_max) + strength_modifier`.
- **Enemy attack**: `d20 + enemy.attack_modifier` vs `10 + player_agility_modifier`. Hit deals `d(damage_min–damage_max)`.
- Enemy down → routes to `enemy.victory_scene`; awards `combat_victory` XP.
- Player down → routes to `enemy.defeat_scene`.
- Only one active `CombatState` per session at a time.

---

## Item System

### Effect Types

| `effect_type` | Behaviour                                                  |
|---------------|------------------------------------------------------------|
| `heal_hp`     | Restores `effect_value` HP (capped at `max_hp`) on use     |
| `add_stat`    | Permanently adds `effect_value` to `effect_stat` on use   |

### Passive Bonuses
Items can have `passive_stat` + `passive_value`. These are applied automatically via `get_effective_stats()` while the item is in inventory. The bonus does **not** persist to the DB — it is computed on every request.

### Consumables
If `is_consumable=True`, the item is removed from inventory after use (or when a Choice with `consume_item` set is taken).

### Equipment Slots
`equip_slot` field exists (`weapon`, `armor`, `accessory`) but equip logic is not yet implemented. Reserved for future use.

---

## Requirement / Gating System

Gates control whether a Quest, Scene, or Choice is accessible.

- Each object holds a M2M to `RequirementGroup`.
- All groups on an object must pass (**AND** between groups).
- Within a group, conditions are evaluated with **AND** (`logic='all'`) or **OR** (`logic='any'`).

### Condition Types

| Type               | Checks                                           |
|--------------------|--------------------------------------------------|
| `stat_gte`         | `stats.{stat_name} >= stat_value`                |
| `stat_lte`         | `stats.{stat_name} <= stat_value`                |
| `has_item`         | item is in inventory                             |
| `missing_item`     | item is not in inventory                         |
| `quest_completed`  | quest has any completion                         |
| `quest_not_done`   | quest has no completion                          |
| `quest_ending`     | quest completed with specific `ending_type`      |
| `level_gte`        | `stats.level >= stat_value`                      |
| `xp_gte`           | `stats.experience >= stat_value`                 |
| `has_flag`         | `flag_name` is set on the session                |
| `missing_flag`     | `flag_name` is not set on the session            |

---

## Flag System

Session-level boolean flags stored in `GameSession.flags` (JSONField).

- Flags are set or cleared automatically when a Choice is taken (`set_flag_name` / `clear_flag_name` fields).
- Gated via `has_flag` / `missing_flag` requirement types on Quests, Scenes, and Choices.
- Use `flags.py` service to read/write flags — never touch the dict directly.

---

## Scene Unlock System

`SceneUnlock` records define conditional scene discovery:

- `from_scene` → `unlocks_scene`: when `from_scene` is completed, `unlocks_scene` becomes available.
- Optional guards: `requires_choice` (only if a specific choice was taken) and `requires_item` (only if an item is in inventory).
- When conditions are met, an event log entry "New area unlocked: X" is generated for the player.

---

## Notice Board

Each hub scene has a notice board showing quests assigned to it via `Quest.hub_scenes` (M2M).

- **Available**: quest not completed and all requirement groups pass.
- **Locked**: quest not completed but at least one requirement group fails (shown with reason).
- **Completed**: quest has a `CompletedQuest` record for this session.

A quest must be assigned to at least one hub scene (`is_unlocked=True`) to appear in the game. The quest builder validator flags quests that are unlocked but have no hub scenes.

---

## Arcs

Quests can be grouped into `Arc` objects. Arcs have an `order` field; quests within an arc have `arc_order`. Currently informational — no gameplay gating is based on arc membership.