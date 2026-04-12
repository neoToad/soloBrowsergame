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
Views are responsible for: reading the request, calling services, building context, returning a response.
Services are responsible for: all game logic, all DB writes beyond simple session saves.

---

## The Game Loop (plain English)

1. Player visits `/game/` → session is created → redirected to `hub__main_square`
2. `scene_detail` loads the scene, filters available choices via `RequirementGroup` evaluation
3. Player POSTs to `choice_resolve` with a choice ID
4. If the scene has `requires_roll=True`, a d20 is rolled and compared to `roll_difficulty`
5. The session's `current_scene` advances to the resolved target
6. Quest completion is checked; XP and level-ups are awarded if applicable
7. Scene items are awarded; EventLog entries are created
8. HTMX response re-renders the five partials in place

---

## Package Structure

```
game/
  models/
    player.py       — GameSession, PlayerStats, PlayerInventory, CompletedQuest
    world.py        — Arc, Quest, Scene, Choice, SceneItem
    items.py        — Item
    combat.py       — Enemy, CombatEncounter, CombatState
    requirements.py — Requirement, RequirementGroup, PlayerContext (dataclass)
    events.py       — EventLog
    __init__.py     — re-exports all public models

  services/
    session.py      — load_session_context, create_session, build_render_context
    scene.py        — get_available_choices, get_notice_board, get_notice_board_for_scene
    inventory.py    — get_player_inventory, award_scene_items, consume_item
    combat.py       — get_or_create_combat_state, resolve_player_attack, resolve_enemy_attack, resolve_combat_end
    progression.py  — award_xp, maybe_complete_quest; also defines XP_THRESHOLDS, XP_AWARDS, RANK_TITLES

  views.py          — HTTP handlers only; delegates to services
  utils.py          — roll_d20, stat_modifier, get_effective_stats
  constants.py      — HUB_START_SCENE_KEY, NOTICE_BOARD_SCENE_KEY, STAT_FIELD_MAP, USE_ITEM_FLAVOR
```

---

## Data Model Relationships

```
Arc ──< Quest ──< Scene ──< Choice
                   │          └── target_scene / success_scene / failure_scene → Scene
                   └──< SceneItem ──> Item
                   └── CombatEncounter ──> Enemy

GameSession ──── PlayerStats (1:1)
            ──< PlayerInventory ──> Item
            ──< CompletedQuest ──> Quest
            ──── CombatState (1:1, optional)
            ──< EventLog

Quest, Scene, Choice each hold a M2M to RequirementGroup.
RequirementGroup holds a M2M to Requirement.
All groups on an object must pass (AND between groups, AND/OR within each group).
```

---

## Key Conventions

- **Scene keys**: `{quest_slug}__{scene_slug}`, e.g. `haunted_mine__entrance`. Hub scenes use `hub__*`.
- **Stat fields**: internal DB names are `strength`, `agility`, `intellect`, `charisma`. Display names (from the UI/POST data) are `muscle`, `reflexes`, `cunning`, `nerve` — mapped via `STAT_FIELD_MAP`.
- **effective_stats**: always use `get_effective_stats(stats, inventory)` for rolls and display. Write mutations to the raw `PlayerStats` instance, then recompute.
- **EventLog**: services return log message strings; the view creates the DB objects. Services must not create EventLog entries directly.
- **HTMX**: all POST views return `_htmx_response()` when `HX-Request: true`. Five partials are rendered and concatenated: `scene_panel`, `stats_bar`, `event_log`, `inventory`, `mobile_stats_bar`.
