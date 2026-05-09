# Architecture

- Owner: Engineering
- Update Trigger: Any service boundary, runtime flow, package layout, or architecture invariant change.
- Last Verified Against Code: 2026-05-09

## Dev Setup

### Prerequisites
- Python 3.10+
- Django 6.0+

### Local Setup
```bash
python manage.py migrate
python manage.py loaddata game/fixtures/
python manage.py collectstatic --noinput
```

### Running Tests
```bash
python manage.py test
```

Notes:
- Most tests assume fixture data is loaded.
- HTMX endpoints should be tested with `HTTP_HX_REQUEST='true'`.
- Initialize gameplay session state by visiting `/game/` before scene/choice flows.

---

## System Layers

```text
URLs -> Views -> Services -> Models
               ^
          utils/constants
```

Rule: business logic lives in services, never views.

Views:
- Parse request input
- Perform auth/session guards
- Call service functions
- Build/render responses

Services:
- Own gameplay rules and orchestration
- Own write-side domain mutations
- Preferred EventLog direction: services return log strings and callers flush once
- Current transitional reality: several gameplay services still call `flush_event_log`/`log_event` directly

---

## Current Package Layout

```text
game/
  models/
    world.py          Arc, Quest, Scene, Choice, Gang, Contact, SceneContact, SceneGangStanding, SceneItem
    player.py         GameSession, PlayerStats, PlayerInventory, PlayerContact, PlayerGangStanding, CompletedQuest
    combat.py         Enemy, CombatEncounter, CombatState
    property.py       Property, Territory, PlayerProperty, PlayerTerritory, PlayerDiscoveredTerritory
    requirements.py   Requirement, RequirementGroup, PlayerContext
    items.py          Item
    events.py         EventLog + log helpers

  views/
    navigation.py     root redirect, hub routing, scene render, choice resolve
    combat.py         combat attack/enemy-resolve/continue endpoints
    quests.py         quest start endpoint
    player.py         level-up and item-use endpoints
    shared.py         session decorator + HTMX response helper (+ dead helper `_render_current_scene`)

  services/
    session.py        session load/create, scene advance, context assembly
    scene.py          choice availability, notice board, roll resolution
    arrival.py        transition arrival pipeline
    progression.py    XP thresholds/awards, stat spending, level-up effects
    inventory.py      inventory/contact/territory effects and item use
    property_service.py turn income and property/territory reward helpers
    combat.py         combat state init/turn/end orchestration
    combat_engine.py  pure roll/attack log helpers (no DB)
    flags.py          has/set/clear session flags
    flag_registry.py  centralized flag key validation
    types.py          gameplay/service dataclasses and errors

    gameplay/
      resolve_choice.py  choice resolution orchestration
      start_quest.py     quest start orchestration
      use_item.py        item-use orchestration
      combat.py          gameplay-facing combat endpoint orchestration

    quest_builder/
      mutations.py       admin quest-builder write flows
      validation.py      quest-builder validation services
      parsing.py         quest-builder form/row parsing helpers
      canvas.py          graph/canvas layout helpers
      requirements.py    requirement parsing/persistence helpers
      shared.py          quest-builder shared helpers

    importers/
      orchestrator.py    import pipeline routing
      world.py           world importers
      quests.py          quest importers
      hubs.py            hub importers
      items.py           item importers
      enemies_contacts.py enemies/contacts importers
      requirements.py    importer requirement mapping
      domain.py          import-domain transforms
      refs.py            FK/key reference resolution
      shared.py/types.py common importer primitives

  presentation/
    responses.py         HTMX/template response assembly helpers

  quest_builder_views/
    quest.py             canvas/list/validate endpoints
    scenes.py            scene panel/mutation endpoints
    choices.py           choice panel/mutation endpoints
    partials.py          shared quest-builder partial endpoints

  admin/
    quest_builder_urls.py admin route wiring for quest-builder

  constants.py           session/stat constants
  utils.py               dice/stat/effective stat helpers
```

Notes:
- Legacy jobs modules listed in older docs were removed (see migration `0061_remove_jobs_schema`).
- `game/services/__init__.py` is intentionally empty; callsites import concrete modules.

---

## Core Runtime Flow

1. `GET /` redirects to `game_hub`.
2. `GET /game/` loads/creates `GameSession` and redirects to `scene_detail` for `current_scene`.
3. `GET /game/scene/<scene_key>/` renders scene context.
   - Current known issue: this GET path can initialize combat state and write an EventLog entry.
4. `POST /game/choose/<choice_id>/` resolves choice routing/rolls/flags, applies arrival effects, flushes logs, and returns HTMX partials (or redirect).
5. `POST /game/quest/<quest_key>/start/` checks requirements, transitions to entrance scene, applies arrival effects.
6. `POST /game/item/use/<item_id>/` applies item effects and re-renders context.
7. `POST /game/level-up/` spends one stat point, applies HP restore, logs outcome, re-renders context.
8. Combat sub-loop:
   - `POST /game/combat/attack/`
   - `POST /game/combat/enemy-resolve/`
   - `POST /game/combat/continue/`
9. HTMX responses are composed through `game/presentation/responses.py` and returned via `views.shared._htmx_response`.

---

## Architectural Invariants

1. Business logic in services, not views.
2. Avoid write-side effects on GET endpoints (except minimal session bootstrap/routing).
3. Arrival effects execute on transitions, not read-only page loads.
4. Guard authoring-dependent pointers (`target_scene`, `entrance_scene`, combat encounter scenes) before use.
5. Wrap multi-step transitions in atomic boundaries.
6. Prefer one log flush per gameplay transition; avoid fragmented EventLog writes.

---

## Current Known Gaps (As Of 2026-05-09)

1. `scene_detail` GET still performs write-side effects via combat init + logging.
2. Outer atomic transaction boundary is missing around some full transition sequences (`resolve_choice`, `start_quest`, `resolve_combat_end`).
3. `initialize_combat_state` can raise uncaught `CombatEncounter.DoesNotExist` on mis-authored combat scenes.
4. `views.player.level_up` still contains gameplay mutation/log composition in view code.
5. `game/views/shared.py:_render_current_scene` is dead code.

---

## Source Of Truth For Debt Tracking

Tracked in:
- `.docs/audit-and-tech-debt-2026-05-07.md`
- `.docs/CURRENT_TASK.md`

---

## Conventions

- Scene keys: `{quest_key}__{scene_slug}`; hub scenes `hub__*`.
- Session anchor scene key constant: `HUB_START_SCENE_KEY = 'hub__apartment'`.
- Stats:
  - DB fields: `strength`, `agility`, `intellect`, `charisma`
  - Display names: `muscle`, `reflexes`, `cunning`, `nerve`
  - Constants: `STAT_FIELDS`, `STAT_DISPLAY_NAMES`
- Always compute roll/display values from `get_effective_stats(stats, inventory)`.
- Use `flags.py` helper functions for flag mutation checks.

---

## HTMX Rendering Contract

Core partial targets currently used in gameplay response assembly:
- `scene_panel`
- `stats_bar`
- `top_stats_bar`
- `event_log`
- `inventory`
- `mobile_stats_bar`
- `territories`

`HX-Push-Url` should mirror the active scene URL.
