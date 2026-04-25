# Architecture

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
- Build/render response

Services:
- Own gameplay rules and orchestration
- Own write-side domain mutations
- Return log strings; caller flushes logs

---

## Current Package Layout

```text
game/
  models/
    world.py          Arc, Quest, Scene, Choice, SceneItem, Contact/Gang/SceneContact
    player.py         GameSession, PlayerStats, PlayerInventory, PlayerContact,
                      PlayerGangStanding, CompletedQuest
    jobs.py           Job, JobApproach, JobBeatVariant, ContactJobOffer,
                      PlayerJobState, PlayerContactOfferState, JobRun
    combat.py         Enemy, CombatEncounter, CombatState
    property.py       Property, PlayerProperty, RivalClaim
    requirements.py   Requirement, RequirementGroup, PlayerContext
    events.py         EventLog + log helpers

  services/
    session.py        load_session_context, create_session, build_render_context
    scene.py          resolve_roll, get_available_choices, get_notice_board
    arrival.py        process_arrival
    progression.py    XP awards/thresholds, quest completion, stat spending
    inventory.py      inventory/contact awards + consumption
    property_service.py turn-income, rival contests, contest resolution
    combat.py         combat resolution helpers + combat state init/end
    jobs.py           recon/contact job lifecycle and rewards
    flags.py          has_flag, set_flag, clear_flag
    quest_builder.py  admin quest-builder domain logic

  views.py            gameplay HTTP endpoints
  quest_builder_views.py admin HTMX endpoints for quest builder
  constants.py        session/stat mapping/display constants
  utils.py            dice/stat math + effective stats
```

---

## Core Flow

1. `GET /game/` loads or creates `GameSession`, then redirects to current scene.
2. `GET /game/scene/<scene_key>/` renders scene + derived UI state.
3. `POST /game/choose/<choice_id>/` resolves routing/rolls/flags.
4. Arrival processing (`process_arrival`) applies scene effects, quest completion, item/contact effects.
5. On quest completion, turn systems run (property income, rival contest checks, turn summary).
6. HTMX requests return concatenated partial updates via `_htmx_response`.

Combat sub-loop:
- `POST /game/combat/attack/`
- `POST /game/combat/enemy-resolve/`
- `POST /game/combat/continue/`

Jobs sub-loop:
- Recon start/commit/walk-away
- Contact offer start
- Beat 1/2/3 resolve and abort

---

## Architectural Invariants

1. Services should not write `EventLog` directly; they return log text and caller flushes.
2. Views should not execute gameplay mutations beyond minimal session routing.
3. Arrival effects happen on transitions, not on read-only page views.
4. Guard all authoring-dependent pointers (`target_scene`, `entrance_scene`, combat encounter scenes) before use.
5. Keep atomic boundaries around multi-step state transitions.

---

## Known Refactor Priorities

Tracked in:
- `.docs/codebase_audit.txt`
- `.docs/codebase_audit_addendum.txt`

Highest-priority active items:
- Move remaining combat and item business logic from views into services.
- Remove write-side effects from `scene_detail` GET path.
- Validate quest-builder choice ownership by `quest_id`.
- Guard missing combat encounter/scene routing data to avoid 500s.

---

## Conventions

- Scene keys: `{quest_key}__{scene_slug}`; hub scenes `hub__*`.
- Session anchor scene key constant: `HUB_START_SCENE_KEY = 'hub__apartment'`.
- Stats:
  - DB fields: `strength`, `agility`, `intellect`, `charisma`
  - Display names: `muscle`, `reflexes`, `cunning`, `nerve`
  - Mapping: `STAT_FIELD_MAP`
- Always compute roll/display values from `get_effective_stats(stats, inventory)`.
- Use `flags.py` helper functions for flag mutation checks.

---

## HTMX Rendering Contract

`_htmx_response` currently concatenates these partials:
- `scene_panel`
- `stats_bar`
- `top_stats_bar`
- `event_log`
- `inventory`
- `mobile_stats_bar`
- `territories`

`HX-Push-Url` should mirror the active scene URL.
