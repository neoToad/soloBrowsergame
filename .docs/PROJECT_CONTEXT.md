# Solo Browser Game — Project Context

A Django text RPG set in a noir crime world. The player is a nobody climbing the ranks of a criminal organization, from Errand Boy to Boss.

---

## Stack

- Python 3.10+ / Django 6.0+
- HTMX for partial-page updates (no full-page reloads after the initial load)
- SQLite via Django ORM

---

## Architecture

```
URLs → Views → Services → Models
                ↑
           utils / constants
```

**Rule**: All business logic lives in services. Views only read the request, call services, build context, and return a response. Services never create `EventLog` entries directly — they return log strings; the view creates the DB objects.

### Package layout

```
game/
  models/
    player.py       — GameSession, PlayerStats, PlayerInventory, CompletedQuest
    world.py        — Arc, Quest, Scene, Choice, SceneItem
    items.py        — Item
    combat.py       — Enemy, CombatEncounter, CombatState
    requirements.py — Requirement, RequirementGroup, PlayerContext (dataclass)
    events.py       — EventLog

  services/
    session.py      — load_session_context, create_session, build_render_context
    scene.py        — get_available_choices, get_notice_board
    inventory.py    — get_player_inventory, award_scene_items, consume_item
    combat.py       — get_or_create_combat_state, resolve_player_attack, resolve_enemy_attack, resolve_combat_end
    progression.py  — award_xp, maybe_complete_quest; XP_THRESHOLDS, XP_AWARDS, RANK_TITLES

  management/commands/
    scaffold_quest.py — creates a stub quest with entrance + victory/defeat ending scenes
    export_quest.py   — dumps a quest and all related objects to a loadable fixture JSON

  views.py          — HTTP handlers only
  utils.py          — roll_d20, stat_modifier, get_effective_stats
  constants.py      — HUB_START_SCENE_KEY, NOTICE_BOARD_SCENE_KEY, STAT_FIELD_MAP, USE_ITEM_FLAVOR
```

---

## Data Model

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

Quest, Scene, Choice each hold M2M → RequirementGroup → M2M → Requirement
```

---

## The Game Loop

1. Player visits `/game/` → session created → redirected to `hub__main_square`
2. `scene_detail` loads the scene, filters choices via `RequirementGroup` evaluation
3. Player POSTs to `choice_resolve` with a choice ID
4. If `scene.requires_roll=True`, a d20 is rolled vs `roll_difficulty`
5. Session's `current_scene` advances to the resolved target
6. Quest completion checked; XP and level-ups awarded
7. Scene items awarded; `EventLog` entries created
8. HTMX re-renders five partials: `scene_panel`, `stats_bar`, `event_log`, `inventory`, `mobile_stats_bar`

---

## Player Stats

All stats default to 5. Modifier: `(stat - 10) // 2` (D&D-style; 5 → −3).

| DB field    | UI label  | Used for                                        |
|-------------|-----------|-------------------------------------------------|
| `strength`  | Muscle    | Melee attack rolls, physical skill checks       |
| `agility`   | Reflexes  | Player defense (`10 + agility modifier`)        |
| `intellect` | Cunning   | Wit/planning checks                             |
| `charisma`  | Nerve     | Persuasion, intimidation, social checks         |
| `hp`        | HP        | Current health                                  |
| `max_hp`    | Max HP    | Healing cap; starts at 20                       |

Always use `get_effective_stats(stats, inventory)` for rolls and display. Write mutations to the raw `PlayerStats` instance.

---


## Scene Types

| Type     | Behaviour                                                          |
|----------|--------------------------------------------------------------------|
| `normal` | Standard narrative scene with choices                             |
| `hub`    | Persistent home area; choices always available                    |
| `combat` | Triggers a `CombatEncounter`; standard choices hidden during combat |
| `ending` | Quest terminus; triggers `maybe_complete_quest()` on arrival      |

Ending scenes have an `ending_type`: `victory`, `defeat`, or `neutral`.

---

## Roll System

- `requires_roll=True` on a Scene triggers a d20 roll when any choice is taken.
- Roll: `d20 + stat_modifier(roll_stat)` vs `roll_difficulty` (DC).
- Routes to `success_scene` or `failure_scene` on the Choice.
- Non-roll choices use `target_scene`.

---

## Combat System

- `CombatEncounter` attaches one `Enemy` to a `Scene`.
- On entering a combat scene, a `CombatState` is created (or retrieved) for the session.
- **Player attack**: `d20 + strength_modifier` vs `enemy.defense`. Hit: `d(damage_min–damage_max) + strength_modifier`.
- **Enemy attack**: `d20 + enemy.attack_modifier` vs `10 + player_agility_modifier`. Hit: `d(damage_min–damage_max)`.
- Enemy down → `enemy.victory_scene`; awards `combat_victory` XP.
- Player down → `enemy.defeat_scene`.
- Only one active `CombatState` per session at a time.

---

## Item System

| `effect_type` | Behaviour                                                       |
|---------------|-----------------------------------------------------------------|
| `heal_hp`     | Restores `effect_value` HP (capped at `max_hp`) on use         |
| `add_stat`    | Permanently adds `effect_value` to `effect_stat` on use        |

Passive bonuses: `passive_stat` + `passive_value` applied via `get_effective_stats()` while the item is in inventory. Not persisted to DB — recomputed every request.

If `is_consumable=True`, item is removed after use.

`equip_slot` (`weapon`, `armor`, `accessory`) exists in the schema but equip logic is not implemented.

---

## Requirement / Gating System

| Type              | Checks                                         |
|-------------------|------------------------------------------------|
| `stat_gte`        | `stats.{stat_name} >= stat_value`              |
| `stat_lte`        | `stats.{stat_name} <= stat_value`              |
| `has_item`        | item is in inventory                           |
| `missing_item`    | item is not in inventory                       |
| `quest_completed` | quest has any completion                       |
| `quest_not_done`  | quest has no completion                        |
| `quest_ending`    | quest completed with specific `ending_type`    |
| `level_gte`       | `stats.level >= stat_value`                    |
| `xp_gte`          | `stats.experience >= stat_value`               |

All `RequirementGroup`s on an object must pass (AND between groups). Within a group: `logic='all'` (AND) or `logic='any'` (OR).

---

## Key Conventions

- **Scene keys**: `{quest_slug}__{scene_slug}` (e.g. `haunted_mine__entrance`). Hub scenes use `hub__*`.
- **Stat field names**: DB uses `strength / agility / intellect / charisma`. UI/POST uses `muscle / reflexes / cunning / nerve` — mapped via `STAT_FIELD_MAP`.
- **HTMX**: all POST views return `_htmx_response()` when `HX-Request: true`.
- **EventLog**: services return strings; views call `EventLog.objects.create()`. Services must not create log entries directly.

---

## Writing Tone

Noir. Terse. Dry. Second person, present tense. Matter-of-fact about violence. No melodrama, no exclamation points.

- **Scene title**: Short. Location or situation. ("Back Alley", "The Drop")
- **Scene body**: 2–4 sentences. Atmosphere, stakes, tension. Don't narrate choices.
- **Choice labels**: Actions, not thoughts. 3–8 words. ("Bribe the guard." not "Decide to try bribing the guard.")
- **`arrival_flavor`**: One line, past tense, logged on arrival. Omit if the next scene's body covers the transition.
- **Items**: Concrete noun name, one-sentence description of what it *is* (not what it does mechanically).
- **Event log**: One sentence. Immediate. No over-explanation.

---

## Known Tech Debt

- Roll logic (`d20 + modifier + DC compare`) lives inline in `views.py` instead of a service.
- `get_effective_stats()` returns a `SimpleNamespace` instead of a typed dataclass.
- `Quest.is_unlocked` (manual boolean) coexists with the `requirements` M2M — purpose is ambiguous.
- `get_notice_board()` re-fetches inventory even when it's already been loaded by `load_session_context`.
- `CombatState` is a `OneToOneField` on session — only one active fight possible at a time.
- `Item.equip_slot` is dead schema weight — no equip logic is implemented.
- Scene key prefix (`{quest_key}__`) is convention-only — not validated; a wrong key silently breaks navigation.
- `export_quest` falls back to PKs for models without `natural_key()` — fixtures may not load cleanly into a fresh DB.
- `start_quest` and `choice_resolve` both call `award_scene_items` — award-on-enter logic is in two places.

See `.junie/TECH_DEBT.md` for full details.
