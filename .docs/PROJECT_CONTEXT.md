# Solo Browser Game - Project Context

A Django + HTMX noir text RPG. The player progresses through scenes, completes jobs/quests,
and develops stats, contacts, territory, and reputation over a persistent session.

---

## Stack

- Python 3.10+
- Django 6.0+
- HTMX (no JS framework)
- SQLite in dev (via Django ORM)

---

## Runtime Summary

- Entry: `GET /game/`
- Session pointer: `request.session[SESSION_KEY] -> GameSession.pk`
- Start scene constant: `HUB_START_SCENE_KEY = 'hub__apartment'`
- Main render endpoint: `GET /game/scene/<scene_key>/`
- Main action endpoint: `POST /game/choose/<choice_id>/`

Player-facing systems currently active:
- Scene/choice routing with optional roll gating
- Requirement groups (items, stats, quests, flags, contacts)
- Inventory items (active + passive effects)
- Combat encounters (two-phase rounds)
- Jobs pipeline (recon, approaches, beats, rewards/cooldowns)
- Property income/contest loop tied to quest completion events

---

## Domain Concepts

### Session and Stats
- `GameSession` tracks current scene, turn counter, and flags JSON.
- `PlayerStats` tracks combat stats, XP/level, and economy (`cash`, `heat`, `rep`).
- `CompletedQuest` records first-time quest completion per session/quest.

### Scenes and Choices
- Scene types: `normal`, `hub`, `combat`, `ending`.
- Choice routing:
  - direct route: `target_scene`
  - roll route: `success_scene` / `failure_scene`
- Roll checks use effective stats and `roll_difficulty`.

### Requirements
- Objects can have many `RequirementGroup`s.
- Between groups: AND logic (all groups must pass).
- Within group: `all` (AND) or `any` (OR).

### Combat
- `CombatEncounter` binds combat scene -> enemy + victory/defeat routes.
- `CombatState` is 1:1 with `GameSession`.
- Enemy attack is pre-rolled and stored for two-step UX.

### Jobs
- District jobs and contact offers are hub-driven.
- Runs advance through beats 1/2/3 with tiered recon and rewards.
- Cooldowns and run-count milestones are stored in player job state models.

### Property Turn Loop
- Triggered after quest completion arrivals.
- Applies passive property income/effects.
- Rolls rival contest chance from heat (`heat / 200`).
- Creates/clears `RivalClaim` through contest resolution scenes.

---

## Important Rules

1. Business logic belongs in `game/services/*`, not views.
2. Services should return log strings; callers flush via event log helpers.
3. Use effective stats for checks; mutate persistent values on `PlayerStats`.
4. Use `flags.py` helpers (`has_flag`, `set_flag`, `clear_flag`) for flag mutation.
5. Keep GET endpoints read-only for domain state when possible.

---

## Current Risks / Active Refactor Tracks

Canonical backlog files:
- `.docs/codebase_audit.txt`
- `.docs/codebase_audit_addendum.txt`

Key active concerns:
- Remaining gameplay logic still embedded in some views (combat/use-item paths).
- GET scene rendering currently contains at least one write-side side effect path.
- Some authoring integrity guards are missing (null/missing route targets/encounters).
- Quest-builder endpoints need stronger ownership validation for `quest_id` + `choice_id`.

---

## Test Notes

- Use `python manage.py test`.
- HTMX responses require `HTTP_HX_REQUEST='true'` in tests.
- Many tests assume initial session creation via `GET /game/` before actions.
- Existing tests cover jobs, combat, and scene routing; add coverage with each refactor migration from view -> service.
