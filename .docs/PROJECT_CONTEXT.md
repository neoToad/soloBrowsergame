# Solo Browser Game - Project Context

- Owner: Engineering
- Update Trigger: Major feature/module changes that alter onboarding-relevant structure.
- Last Verified Against Code: 2026-05-02

High-level onboarding snapshot for the project. This file is summary-only.

## What This Project Is
A Django + HTMX noir text RPG where players move through scenes, make choices, complete jobs/quests, and progress stats, contacts, territory, and reputation in a persistent session.

## Stack
- Python 3.10+
- Django 6.0+
- HTMX (no frontend framework)
- SQLite in development

## Runtime at a Glance
- Entry route: `GET /game/`
- Core scene route: `GET /game/scene/<scene_key>/`
- Core choice route: `POST /game/choose/<choice_id>/`
- Session anchor: `request.session[SESSION_KEY] -> GameSession.pk`
- Hub start scene key: `hub__apartment`

## Main Gameplay Systems
- Scene/choice routing with optional stat-roll checks
- Requirement evaluation (items, stats, quests, flags, contacts)
- Inventory with active/passive item effects
- Two-phase combat encounters
- Multi-stage jobs flow (recon, approach, beats, rewards/cooldowns)
- Property/territory turn effects tied to quest progression

## Core Domain Entities
- Session/player: `GameSession`, `PlayerStats`, `CompletedQuest`
- Narrative world: `Arc`, `Quest`, `Scene`, `Choice`
- Systems: requirements, combat encounters/state, jobs state, property/rival claims

## Where to Look Next
- Architecture rules/invariants: `.docs/ARCHITECTURE.md`
- Current implementation status: `.docs/CURRENT_TASK.md`
- Endpoint/HTMX response contract: `.docs/ENDPOINT_RESPONSE_CONTRACT.md`
- Structural refactor backlog: `.docs/refactor-inventory.md`
- Debt/risk register: `.docs/tech-debt-register.md`
- Documentation map and ownership: `.docs/README.md`
- Quest authoring index: `.docs/QUEST_AUTHORING_COMPLETE.md`
- World lore index: `.docs/WORLD_LORE.md`
