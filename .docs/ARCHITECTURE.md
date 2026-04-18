# Architecture

## Dev Setup

### Prerequisites
- Python 3.10+, Django 6.0+

### Local Setup
```bash
python manage.py migrate
python manage.py loaddata game/fixtures/hub.json game/fixtures/quest_warehouse_job.json
python manage.py collectstatic --noinput
```

### Running Tests
```bash
python manage.py test
```

Most tests require both fixtures. HTMX views need `HTTP_HX_REQUEST='true'`.
Always initialize a session by visiting `/game/` before testing gameplay.

---

## System Layers

```
URLs → Views → Services → Models
                ↑
           utils / constants
```

**Rule: business logic lives in services, never views.**
Views are responsible for: reading the request, calling services, building context,
returning a response. Services are responsible for: all game logic, all DB writes
beyond simple session saves.

---

## Package Structure

```
game/
  models/
    player.py       — GameSession (+ flags JSONField), PlayerStats (cash, heat, rep),
                      PlayerInventory, CompletedQuest, PlayerSceneState
    world.py        — Arc, Quest (+ hub_scenes M2M), Scene, Choice, SceneItem, SceneUnlock
    items.py        — Item
    combat.py       — Enemy, CombatEncounter, CombatState
    requirements.py — Requirement, RequirementGroup, PlayerContext (dataclass)
    events.py       — EventLog
    property.py     — Property, PlayerProperty, RivalClaim
    __init__.py     — re-exports all public models

  services/
    session.py      — load_session_context, create_session, build_render_context
    scene.py        — resolve_roll, get_available_choices, complete_scene,
                      unlock_scene, get_available_scenes, get_notice_board
    inventory.py    — get_player_inventory, award_scene_items, consume_item
    combat.py       — get_or_create_combat_state, resolve_player_attack,
                      resolve_enemy_attack, resolve_combat_end
    progression.py  — award_xp, maybe_complete_quest; XP_THRESHOLDS, XP_AWARDS, RANK_TITLES
    property_service.py — turn income, rival contests, contest resolution, turn summaries
    flags.py        — has_flag, set_flag, clear_flag
    quest_builder.py — canvas data, scene/choice CRUD, position saving,
                       validate_quest, update_scene_items, update_combat_encounter,
                       build_requirement_groups_from_post

  management/commands/
    scaffold_quest.py — creates a stub quest with entrance + victory/defeat ending scenes
    export_quest.py   — dumps a quest and all related objects to a loadable fixture JSON

  views.py          — HTTP handlers; delegates to services; Quest Builder AJAX views
                      are registered via QuestAdmin.get_urls()
  utils.py          — roll_d20, stat_modifier, get_effective_stats
  constants.py      — HUB_START_SCENE_KEY, NOTICE_BOARD_SCENE_KEY, STAT_FIELD_MAP,
                      USE_ITEM_FLAVOR
```

---

## Data Model Relationships

```
Arc ──< Quest ──< Scene ──< Choice
         │          │          └── target_scene / success_scene / failure_scene → Scene
         │          └──< SceneItem ──> Item
         │          └── CombatEncounter ──> Enemy
         │          └──< SceneUnlock ──> Scene
         └──< hub_scenes (M2M) ──> Scene(hub)

GameSession ──── PlayerStats (1:1)
            ──── flags (JSONField)
            ──< PlayerInventory ──> Item
            ──< CompletedQuest ──> Quest
            ──── CombatState (1:1, optional)
            ──< EventLog
            ──< PlayerSceneState ──> Scene
            ──< PlayerProperty ──> Property ──< RivalClaim

Quest, Scene, Choice each hold a M2M to RequirementGroup.
RequirementGroup holds a M2M to Requirement.
All groups on an object must pass (AND between groups, AND/OR within each group).
```

---

## The Game Loop

1. Player visits `/game/` → session is created → redirected to `hub__main_square`
2. `scene_detail` loads the scene, filters available choices via `RequirementGroup` evaluation
3. Player POSTs to `choice_resolve` with a choice ID
4. If the scene has `requires_roll=True`, a d20 is rolled and compared to `roll_difficulty`
5. The session's `current_scene` advances to the resolved target
6. Quest completion is checked; XP and level-ups are awarded if applicable
7. Scene unlocks (`SceneUnlock`) and `PlayerSceneState` are updated
8. Flag effects (`set_flag_name` / `clear_flag_name`) on the taken choice are applied
9. Scene items are awarded; `EventLog` entries are created
10. On quest completion, property turn logic runs (income, contests, summary)
11. HTMX response re-renders the five partials in place

---

## Quest Builder (Admin Tool)

Mounted under `QuestAdmin.get_urls()`. Primary authoring tool for quest narrative flows.

- **Canvas view**: draggable scene cards with SVG arrows for choices and combat routing
- **Scene panel**: title, key, type, roll settings, body, items, combat encounter, requirement groups
- **Choice panel**: label, routing type (direct / roll), targets, flag effects
- **Validation**: `validate_quest()` returns warnings for orphan scenes, missing routing, hub
  assignment, combat misconfigs, etc.
- **Hub assignment**: `Quest.hub_scenes` M2M determines which notice boards list the quest

---

## Key Conventions

- **Scene keys**: `{quest_slug}__{scene_slug}`, e.g. `haunted_mine__entrance`. Hub scenes use `hub__*`.
- **Stat fields**: DB names are `strength`, `agility`, `intellect`, `charisma`. Display names are
  `muscle`, `reflexes`, `cunning`, `nerve` — mapped via `STAT_FIELD_MAP`.
- **effective_stats**: always use `get_effective_stats(stats, inventory)` for rolls and display.
  Write mutations to raw `PlayerStats`, then recompute.
- **EventLog**: services return log message strings; the view creates the DB objects. Services
  must not create `EventLog` entries directly.
- **HTMX**: all POST views return `_htmx_response()` when `HX-Request: true`. Five partials
  rendered and concatenated: `scene_panel`, `stats_bar`, `event_log`, `inventory`,
  `mobile_stats_bar`. `turn_summary` is included in context and rendered inside `scene_panel`.
- **Flags**: use `flags.py` service only — never read/write `GameSession.flags` directly in
  views or other services.