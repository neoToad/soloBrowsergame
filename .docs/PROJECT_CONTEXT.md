# Solo Browser Game - Project Context

- Owner: Engineering
- Update Trigger: Major feature/module changes that alter onboarding-relevant structure.
- Last Verified Against Code: 2026-05-09

High-level onboarding snapshot for the project. This file is summary-only.

## What This Project Is
A Django + HTMX noir text RPG where players move through scenes, make choices, complete quests, and progress stats, contacts, properties, territories, and reputation in a persistent session.

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
- Arrival-effect pipeline (cash/rep/heat, items/contacts, quest completion)
- Property/territory progression and turn effects tied to quest outcomes

## Core Domain Entities
- Session/player: `GameSession`, `PlayerStats`, `CompletedQuest`
- Narrative world: `Arc`, `Quest`, `Scene`, `Choice`
- Systems: requirements, combat encounters/state, flags, inventory, properties, territories

## Architecture Snapshot
- Request flow: URLs -> views -> services -> models
- Rule: business logic belongs in services, not views
- Current known gap: `scene_detail` GET still has combat-init/log write side effects (tracked in architecture/debt docs)

## Where to Look Next
- Architecture rules/invariants: `.docs/ARCHITECTURE.md`
- Current implementation status: `.docs/CURRENT_TASK.md`
- Consolidated audit + debt register: `.docs/audit-and-tech-debt-2026-05-07.md`
- Documentation map and ownership: `.docs/README.md`
- Quest authoring docs: `.docs/QUEST_AUTHORING_COMPLETE.md`, `.docs/QUEST_AUTHORING_RULES.md`, `.docs/QUEST_AUTHORING_PATTERNS.md`, `.docs/QUEST_CONTENT_GUIDE.md`
- World lore docs: `.docs/WORLD_LORE.md`, `.docs/WORLD_LORE_CORE.md`, `.docs/WORLD_LORE_REFERENCE.md`
- Quest tracking: `.docs/quest_tracking.xlsx` and `.docs/quest_tracking.md`
