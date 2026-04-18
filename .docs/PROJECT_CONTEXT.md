# Solo Browser Game - Project Context

A Django text RPG set in a noir crime world. The player starts as a nobody and
climbs from Errand Boy to Boss.

---

## Stack

- Python 3.10+
- Django 6.0+
- HTMX (no JS framework)
- SQLite via Django ORM

---

## Core Loop

1. Player hits `/game/`; a `GameSession` is created if needed.
2. Session redirects to `hub__main_square`.
3. Scene page loads with requirement-filtered choices.
4. Player takes a choice.
5. If the scene requires a roll, `resolve_roll` decides success/failure routing.
6. Session advances to the resolved scene.
7. Updates, flag effects, and scene item awards are applied.
8. On quest completion, property turn logic runs (income, contests, summary).
9. HTMX response re-renders core partials.

---

## Scene and Choice Rules

- Scene types: `normal`, `hub`, `combat`, `ending`.
- Roll scenes use `Scene.requires_roll`, `roll_stat`, and `roll_difficulty`.
- Choice routing fields:
  - `target_scene` for non-roll scenes
  - `success_scene` / `failure_scene` for roll scenes
- Flag effects: `set_flag_name` / `clear_flag_name` are applied when a choice is taken.
- Entry choices can link to a `Quest` and are hidden after completion unless
  `Quest.is_repeatable=True`.

---

## Combat Rules

- `CombatEncounter` ties one `Enemy` to one combat `Scene`.
- `CombatState` is one-to-one with `GameSession` (single active fight per session).
- Rounds are two-phase:
  1. `POST /game/combat/attack/` — resolves player attack; pre-rolls and stores enemy counter on `CombatState` (`pending_e_roll/total/hit/dmg`). Returns "Brace yourself" state.
  2. `POST /game/combat/enemy-resolve/` — applies stored enemy attack, clears pending fields, advances `turn_number`.
- Player attack: `d20 + strength modifier` vs `enemy.defense`.
- Enemy attack: `d20 + enemy.attack_modifier` vs `10 + agility modifier`.
- Enemy death is checked after phase 1 (no retaliation if already dead).
- Win routes to `victory_scene`; loss routes to `defeat_scene`.

---

## XP and Leveling

- Core progression lives in `game/services/progression.py`.
- XP is cumulative (`stats.experience` is never spent).
- XP sources:
  - Quest ending completion (first completion per quest/session only):
    - `victory`: `+150 XP`
    - `neutral`: `+75 XP`
    - `defeat`: `+25 XP`
  - Combat victory: `+50 XP` (`combat_victory` award).
- Level thresholds:
  - Level 1: `0`
  - Level 2: `200`
  - Level 3: `600`
  - Level 4: `1300`
  - Level 5: `2400`
  - Level 6: `4000`
  - Level 7: `6200` (max level)
- Level-up behavior (`award_xp`):
  - Adds XP, then iterates thresholds to allow multi-level gains from one award.
  - Grants `+1 stat_point` per level gained.
  - At `MAX_LEVEL=7`, XP can still increase but no further levels/stat points are awarded.
- UI behavior:
  - Stats bar shows raw total XP (`{{ stats.experience }} XP`).
  - XP bar shows progress within the current level band.
  - At max level, XP bar is forced to `100%`.
- Requirements can gate on total XP via `xp_gte` (`stats.experience >= stat_value`).

---

## Items and Stats

- Active item effects: `heal_hp`, `add_stat`.
- Passive bonuses use `passive_stat` + `passive_value`, applied via `get_effective_stats()`.
- Always use effective stats for checks/display; write persistent changes to raw `PlayerStats`.

Stat mapping:
- DB fields: `strength`, `agility`, `intellect`, `charisma`
- UI labels: `muscle`, `reflexes`, `cunning`, `nerve`
- Mapping source: `STAT_FIELD_MAP`

---

## Property Turn System

- `PlayerProperty` entries provide per-turn cash income, heat reduction, and rep bonus.
- Turn processing runs on quest completion.
- Rival contest chance scales with heat (`heat / 200`).
- Contest creates a `RivalClaim`, marks the property contested, and unlocks a resolution scene.
- Resolution outcomes: `victory` (keep property, clear contest), `defeat`/`neutral` (lose property).

---

## Requirement System

Requirement types: `stat_gte`, `stat_lte`, `has_item`, `missing_item`, `quest_completed`,
`quest_not_done`, `quest_ending`, `level_gte`, `xp_gte`, `has_flag`, `missing_flag`.

Evaluation logic:
- All requirement groups on a gated object must pass (AND between groups).
- Each group applies internal logic `all` (AND) or `any` (OR).

---

## Flag System

- `GameSession.flags` is a JSONField storing session-level boolean flags (key → True).
- Use the `flags.py` service (`has_flag`, `set_flag`, `clear_flag`) — never read/write the
  dict directly.
- Flags are gated with `has_flag` / `missing_flag` requirement types.

---

## Notice Board / Hub Scenes

- `Quest.hub_scenes` is a M2M to hub-type `Scene` records.
- `get_notice_board(scene, ...)` filters quests by the current hub scene.
- An unlocked quest with no hub scenes assigned will not appear to the player anywhere.
- The quest builder validator warns about this (`no_hub_scenes` warning type).

---

## Narrative Conventions

- Tone: noir, terse, second person, present tense.
- Scene keys follow `{quest_key}__{scene_slug}`; hub scenes use `hub__*`.

