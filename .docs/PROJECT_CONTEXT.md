# Solo Browser Game - Project Context

A Django text RPG set in a noir crime world. The player starts as a nobody and climbs from Errand Boy to Boss.

---

## Stack

- Python 3.10+
- Django 6.0+
- HTMX (no JS framework)
- SQLite via Django ORM

---

## Architecture

```text
URLs -> Views -> Services -> Models
               ^
          utils / constants
```

Rule: business logic belongs in services. Views handle request/response flow and delegate logic.

### Package layout

```text
game/
  models/
    player.py       - GameSession (+ flags JSONField), PlayerStats (cash, heat, rep),
                      PlayerInventory, CompletedQuest, PlayerSceneState
    world.py        - Arc, Quest (+ hub_scenes M2M), Scene, Choice, SceneItem, SceneUnlock
    items.py        - Item
    combat.py       - Enemy, CombatEncounter, CombatState
    requirements.py - Requirement, RequirementGroup, PlayerContext
    events.py       - EventLog
    property.py     - Property, PlayerProperty, RivalClaim

  services/
    session.py      - load_session_context, create_session, build_render_context
    scene.py        - resolve_roll, get_available_choices, complete_scene,
                      unlock_scene, get_available_scenes, get_notice_board
    inventory.py    - get_player_inventory, award_scene_items, consume_item
    combat.py       - attack resolution, combat lifecycle, combat-end routing
    progression.py  - award_xp, maybe_complete_quest, XP thresholds/awards
    property_service.py - turn income, rival contests, contest resolution, turn summaries
    flags.py        - has_flag, set_flag, clear_flag
    quest_builder.py - canvas data, scene/choice CRUD, position saving,
                       validate_quest, update_scene_items, update_combat_encounter,
                       build_requirement_groups_from_post

  management/commands/
    scaffold_quest.py - scaffold a quest with entrance/victory/defeat scenes
    export_quest.py   - export a quest and related objects as fixture JSON

  views.py          - HTTP handlers; Quest Builder AJAX views are in QuestAdmin.get_urls()
  utils.py          - roll_d20, stat_modifier, get_effective_stats
  constants.py      - scene keys, stat field map, item flavor text
```

---

## Data Model

```text
Arc --< Quest --< Scene --< Choice
         |          |         \-- target/success/failure -> Scene
         |          |--< SceneItem --> Item
         |          |-- CombatEncounter --> Enemy
         |          \--< SceneUnlock --> Scene
         \--< hub_scenes (M2M) --> Scene(hub)

GameSession ---- PlayerStats (1:1)
           ---- flags (JSONField)
           --< PlayerInventory --> Item
           --< CompletedQuest --> Quest
           ---- CombatState (1:1 optional)
           --< EventLog
           --< PlayerSceneState --> Scene
           --< PlayerProperty --> Property --< RivalClaim

Quest, Scene, and Choice each have M2M -> RequirementGroup -> M2M -> Requirement.
```

---

## Core Loop

1. Player hits `/game/`; a `GameSession` is created if needed.
2. Session redirects to `hub__main_square`.
3. Scene page loads with requirement-filtered choices.
4. Player takes a choice.
5. If scene requires a roll, `resolve_roll` decides success/failure routing.
6. Session advances to the resolved scene.
7. Scene unlocks (`SceneUnlock`), `PlayerSceneState` updates, flag effects, and scene item awards are applied.
8. On quest completion, property turn logic runs (income, contests, summary).
9. HTMX response re-renders core partials.

---

## Scene and Choice Rules

- Scene types: `normal`, `hub`, `combat`, `ending`.
- Roll scenes use `Scene.requires_roll`, `roll_stat`, and `roll_difficulty`.
- Choice routing fields:
  - `target_scene` for non-roll scenes
  - `success_scene` / `failure_scene` for roll scenes
- Flag effects:
  - `set_flag_name` / `clear_flag_name` are applied when a choice is taken.
- Entry choices can link to `Quest` and are hidden after completion unless `Quest.is_repeatable=True`.

---

## Combat Rules

- `CombatEncounter` ties one `Enemy` to one combat `Scene`.
- `CombatState` is one-to-one with `GameSession` (single active fight per session).
- Player attack: `d20 + strength modifier` vs `enemy.defense`.
- Enemy attack: `d20 + enemy.attack_modifier` vs `10 + agility modifier`.
- Win routes to `enemy.victory_scene`; loss routes to `enemy.defeat_scene`.

---

## Items and Stats

- Active item effects:
  - `heal_hp`
  - `add_stat`
- Passive bonuses use `passive_stat` + `passive_value` and are applied through `get_effective_stats()`.
- Always use effective stats for checks/display; write persistent changes to raw `PlayerStats`.

Stat mapping:
- DB fields: `strength`, `agility`, `intellect`, `charisma`
- UI labels: `muscle`, `reflexes`, `cunning`, `nerve`
- Mapping source: `STAT_FIELD_MAP`

---

## Property Turn System

- `PlayerProperty` entries provide per-turn:
  - cash income
  - heat reduction
  - rep bonus
- Turn processing runs on quest completion.
- Rival contest chance scales with heat (`heat / 200`).
- Contest creates `RivalClaim`, marks property contested, and unlocks a resolution scene.
- Resolution outcomes:
  - `victory`: keep property, clear contest
  - `defeat`/`neutral`: lose property

---

## Requirement System

Requirement types:
- `stat_gte`, `stat_lte`
- `has_item`, `missing_item`
- `quest_completed`, `quest_not_done`, `quest_ending`
- `level_gte`, `xp_gte`
- `has_flag`, `missing_flag`

Evaluation logic:
- All requirement groups on a gated object must pass (AND between groups).
- Each group applies internal logic `all` (AND) or `any` (OR).

---

## Flag System

- `GameSession.flags` is a JSONField storing session-level boolean flags (key → True).
- Use `flags.py` service (`has_flag`, `set_flag`, `clear_flag`) — never read/write the dict directly.
- Choices apply flag effects on take via `set_flag_name` and `clear_flag_name` fields.
- Flags are gated with `has_flag` / `missing_flag` requirement types.

---

## Notice Board / Hub Scenes

- `Quest.hub_scenes` is a M2M to hub-type `Scene` records.
- `get_notice_board(scene, ...)` filters quests by the current hub scene.
- An unlocked quest with no hub scenes assigned will not appear to the player anywhere.
- The quest builder validator warns about this (`no_hub_scenes` warning type).

---

## HTMX Rendering

POST endpoints return a combined partial response via `_htmx_response()`:
- `scene_panel`
- `stats_bar`
- `event_log`
- `inventory`
- `mobile_stats_bar`

`turn_summary` is included in context and rendered in the scene panel when present.

---

## Key Conventions

- Scene keys follow `{quest_key}__{scene_slug}`; hub scenes use `hub__*`.
- Narrative tone: noir, terse, second person, present tense.
- Services return domain results/messages; view layer owns HTTP responses and page composition.

---

## Known Tech Debt

- Some event writes still happen in services (`game/services/combat.py`), which conflicts with the service/view logging boundary.
- Scene key prefix convention is documented but not model-validated.
- `export_quest` portability depends on natural keys that are not implemented across all related models.
- Scene item awarding is triggered in multiple flows (`start_quest`, `choice_resolve`, combat end), increasing maintenance risk.

See `.docs/TECH_DEBT.md` for details.