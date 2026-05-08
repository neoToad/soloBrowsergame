# Refactor Audit Report (`soloBrowserGame`)

Scope note: I audited runtime code in `game/`, `core/`, and `.docs/` (views/services/models/admin quest-builder). I did not treat migrations/fixtures as refactor targets. `.docs/refactor-inventory.md` is missing in this workspace, so "known debt" cross-check is against `ARCHITECTURE.md` and `tech-debt-register.md`.

## 1) Architectural invariants
**Verdict: Multiple violations found (correctness-impacting), plus some areas already clean.**

### A. Business logic leaking into views
1. `game/views/navigation.py` `scene_detail` calls combat initialization and writes logs.
- Breaks: "views should not execute gameplay mutations."
- Correct version: controller calls a gameplay service/use-case that returns render DTO + logs; view only renders.

2. `game/views/player.py` `level_up` performs domain mutation flow directly (`spend_stat_point`, HP restore, log write, recomputation).
- Breaks: business logic in view.
- Correct version: move whole level-up use-case into `game/services/gameplay/*`, return updated context/logs.

Clean examples:
1. `game/views/combat.py` endpoints are thin wrappers over gameplay services.
2. `game/views/quests.py` `start_quest` is mostly orchestration-only.

### B. Write-side effects on GET paths
1. `game/views/navigation.py` `GET /game/scene/<key>/` can create/update/delete `CombatState` via `initialize_combat_state`.
2. Same path writes `EventLog` on GET (`log_event`).

Clean/acceptable:
1. `game/views/navigation.py` `game_hub` may create session on GET; this matches "minimal session routing" exception.

### C. EventLog written directly from services instead of returned strings
1. `game/services/gameplay/resolve_choice.py` writes logs directly (`flush_event_log`, `log_event`).
2. `game/services/gameplay/start_quest.py` writes directly.
3. `game/services/gameplay/use_item.py` writes directly.
4. `game/services/gameplay/combat.py` writes directly.

Note: this is explicitly documented transitional debt in architecture, so it is a known violation, not a surprise.

### D. Missing atomic boundaries around multi-step transitions
1. `game/services/gameplay/resolve_choice.py` spans flag mutation, scene advance, arrival processing, event flush, combat init without one outer transaction.
2. `game/services/gameplay/start_quest.py` has same issue.
3. `game/services/combat.py` `resolve_combat_end` performs multi-write state transition without outer atomic boundary.

Correct version: wrap each full use-case transition in one `transaction.atomic()` at gameplay-service boundary.

### E. Unguarded FK pointers (target/entrance/combat scenes)
1. Unguarded combat encounter in scene GET path: `game/services/combat.py` uses `.get(scene=scene)`; caller `game/views/navigation.py` does not catch `DoesNotExist`, so mis-authored content can 500.
2. Quest-builder combat save does not validate scene ownership or cross-quest routing for victory/defeat scene IDs before persist: `game/services/quest_builder/mutations.py`.

Clean guards present:
1. Entrance scene guarded: `game/services/gameplay/start_quest.py`.
2. Choice destination guarded at runtime and via model validation: `game/services/gameplay/resolve_choice.py`, `game/models/world.py`.

## 2) Service layer structure
**Verdict: Core gameplay services are mostly well-bounded, with one module too large and a few boundary leaks.**

Issues:
1. `game/services/combat.py` is oversized and multi-responsibility (init, turn engine, encounter resolution, arrival integration, rendering context shaping). Should split into `combat_state`, `combat_turns`, `combat_resolution`.
2. `session` context assembly remains dense/cross-domain: `game/services/session.py`. This is known debt and still present.
3. Event logging contract inconsistency across services (some return logs, gameplay services flush directly) creates boundary ambiguity.

Clean/scoped:
1. `game/services/arrival.py` is a clear orchestrator for arrival effects.
2. `game/services/inventory.py` is cohesive around inventory/contact/territory award mechanics.
3. Quest-builder service split (`parsing`, `mutations`, `validation`, `requirements`) is generally good.

## 3) Model layer
**Verdict: Mostly clean domain validation; a few constraints/validation gaps remain.**

Issues:
1. Missing uniqueness constraints can allow duplicate ownership rows under race conditions:
- `game/models/property.py` `PlayerProperty` lacks unique `(session, property)`.
- `game/models/property.py` `PlayerTerritory` lacks unique `(session, territory)`.
2. `CombatEncounter` has no model-level `clean()` enforcing combat-scene semantics or same-quest route constraints for victory/defeat pointers, relying on external discipline.

Clean:
1. Strong routing/authoring validation in `game/models/world.py` (`Choice.clean`, `validate_choice_routing`).
2. Good use of uniqueness constraints in player/session relation tables (inventory/contacts/gang standing/completed quests).
3. `RequirementGroup` scoped identity constraint is solid.

## 4) View layer
**Verdict: Gameplay views are mixed; combat/quest endpoints are clean, while scene and level-up still violate the thin-view rule.**

Violations:
1. `game/views/navigation.py` `scene_detail` mutates combat/log state.
2. `game/views/player.py` `level_up` performs gameplay mutation and logging.

Clean:
1. `game/views/combat.py` thin and consistent.
2. `game/views/quests.py` thin.
3. Most quest-builder mutation views validate request method, check quest ownership, delegate to services.

## 5) Code quality and patterns
**Verdict: Readable overall; several consistency and maintainability debts remain.**

Findings:
1. Inconsistent parsing pattern in quest-builder:
- `game/quest_builder_views/scenes.py` has hand-rolled row parsing for gang standings while items/contacts use parser services.
2. Dead/unreferenced helper:
- `game/views/shared.py` `_render_current_scene` is not referenced.
3. Encoding/mojibake artifacts still present in strings/comments:
- `game/services/combat.py`,
- `game/models/player.py`.
4. Duplicated “write log now” behavior spread across gameplay modules instead of one event-emission contract.

Good shape:
1. Requirement evaluation and routing validation patterns are consistent and understandable.
2. Presentation response helpers are centralized and readable.

## 6) Known debt vs undocumented debt
**Verdict: Most major findings are already known; several important items are undocumented.**

Tracked and still present (verified):
1. Legacy flag validation allowance path still present: `game/models/world.py`.
2. Dual legacy + normalized trigger contract still present: `game/presentation/responses.py`.
3. Import orchestrator key-based dispatch still present: `game/services/importers/orchestrator.py`.
4. Dense context assembly in `session.py` still present.
5. Manual gang-standings POST parsing still present.
6. Scene GET write-side effects still present (also called out in architecture priorities).
7. Missing combat encounter guard causing potential 500 still present in scene GET path.

Not tracked (or not found in available debt docs):
1. Missing DB uniqueness constraints for `PlayerProperty` and `PlayerTerritory`.
2. Missing outer atomic boundaries for full gameplay transitions (`resolve_choice`, `start_quest`, `resolve_combat_end`).
3. `choice_panel` GET ownership guard gap in `game/quest_builder_views/choices.py` (loads choice by id without verifying it belongs to `quest_id`).
4. `.docs/refactor-inventory.md` missing even though architecture references it as active tracking source.

## Priority summary
**Correctness first:**
1. Remove write side-effects from `scene_detail` GET and guard missing combat encounter pointers.
2. Add atomic boundaries around full gameplay transitions.
3. Add missing uniqueness constraints for `PlayerProperty`/`PlayerTerritory`.

**Structural next:**
1. Move `level_up` flow into gameplay service.
2. Split oversized `services/combat.py`.

**Quality then:**
1. Normalize quest-builder parsing pattern.
2. Remove dead helper and clean encoding artifacts.
