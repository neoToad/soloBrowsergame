# Consolidated Audit and Tech Debt Report

*Compiled: 2026-05-09*

This document combines:
- `codebase-audit-2026-05-07.md`
- `refactor-audit-2026-05-07.md`
- `tech-debt-register.md`

---

## Source: codebase-audit-2026-05-07.md

# Codebase Audit Report - soloBrowserGame

*Audit date: 2026-05-07. Code verified against current HEAD.*

---

## 1. Violations of Architectural Invariants

### Invariant: Services should not write EventLog directly
**Clean - no violations.**

`EventLog.objects.create()` exists in exactly one place: `models/events.py:9`, inside the `log_event()` helper. All gameplay code reaches EventLog through `flush_event_log()` or `log_event()`. The direction of travel - services return strings, callers flush - is being followed, with `log_event` called from views only for single post-transition log entries (combat init). The ARCHITECTURE.md correctly notes this is a transition-period pattern, not a permanent exception. Nothing to fix here beyond the existing direction.

---

### Invariant: Write-side effects on GET paths
**One violation, pre-existing and tracked.**

`navigation.py:37-39` - `scene_detail` is a GET handler that calls `initialize_combat_state(game_session, scene)`, which can CREATE a `CombatState` row and produce an init log, followed by `log_event(game_session, combat_init_log)`. A read-only page view is writing to two tables.

`shared.py:38-57` - `_render_current_scene` has the identical problem (calls `initialize_combat_state` + `log_event` on a GET). However, this function is **never called anywhere** - it is dead code (see Â§5).

The violation in `scene_detail` is already listed in ARCHITECTURE.md's Known Refactor Priorities: "Remove write-side effects from `scene_detail` GET path." The correct fix is to handle combat initialization only on POST transitions (e.g., move it to `resolve_choice`) and drop the write from the GET view.

---

### Invariant: Missing atomic boundaries around multi-step state transitions
**One gap, newly identified - not in any tracked document.**

`process_arrival` is now correctly wrapped in `transaction.atomic()` - the April 2026 audit item is resolved. But the *calling sequences* are not wrapped in an outer transaction:

- `resolve_choice.py:49-51`: `advance_to_scene(session, next_scene)` (writes `session.current_scene`) runs before `process_arrival(...)`. If `process_arrival` fails, the session is permanently at the new scene with no rewards applied.
- `start_quest.py:21-23`: Same pattern.
- `combat.py:257-261` in `resolve_combat_end`: `combat_state.save()` and then `session.save()` execute as separate committed transactions before `process_arrival`. A failure between any of these leaves the game in inconsistent state.

The fix in all three cases is the same: wrap `advance_to_scene + process_arrival` (and the preceding saves in `resolve_combat_end`) in an outer `with transaction.atomic():` block. Because `process_arrival` uses its own `transaction.atomic()` internally, SQLite/Django will correctly downgrade that inner call to a savepoint when inside an outer transaction.

---

### Invariant: Unguarded FK pointers (combat encounter scenes, entrance scenes, target scenes)
**One unguarded pointer - pre-existing, tracked in ARCHITECTURE.md.**

`combat.py:68` - `CombatEncounter.objects.select_related('enemy').get(scene=scene)` in `initialize_combat_state` has no try/except. If a scene has `scene_type='combat'` but no `CombatEncounter` row, this raises an unhandled `DoesNotExist` and produces a 500. Crucially, this path is called from `scene_detail` (view level), where there is no `GameplayError` handler to catch it.

The `run_enemy_attack` gameplay orchestrator *does* catch `CombatEncounter.DoesNotExist` and converts it to a `GameplayError` - but only for the enemy-resolve path, not for initialization.

All other pointers are correctly guarded:
- `quest.entrance_scene` -> `start_quest.py:17`, raises `GameplayError`
- `choice.target_scene` -> `resolve_choice.py:34`, raises `GameplayError`
- `choice.success_scene/failure_scene` -> `resolve_choice.py:23-32`, raises `GameplayError`
- `encounter.victory_scene/defeat_scene` -> `resolve_combat_end`, raises `GameplayError`

---

## 2. Service Layer Structure

**Well-bounded and appropriately scoped:**

| Service | Lines | Assessment |
|---|---|---|
| `scene.py` | 115 | Clean - roll resolution, choice filtering, notice board |
| `arrival.py` | 61 | Clean - single function, well-documented, atomic |
| `flags.py` | 41 | Clean - single responsibility |
| `flag_registry.py` | 102 | Clean - registry validation. Legacy allowance tracked |
| `inventory.py` | 160 | Clean - all item/contact/territory operations |
| `property_service.py` | 112 | Clean - turn income and property rewards |
| `combat_engine.py` | 37 | Clean - pure math, zero DB access |
| `types.py` | 85 | Clean - data types only |
| `gameplay/*` | 4 small files | Clean - thin orchestration shells |
| `quest_builder/*` | package | Clean - properly decomposed |

**Structural problem: `combat.py:79-156` and `159-227`**

`execute_player_attack` and `execute_enemy_attack` call `build_render_context` from the session service at the end of their logic. This means the combat service has a compile-time dependency on the template rendering layer, and assembles full page contexts (including social data, hub data, property lists) inside functions whose domain is combat mechanics. Any change to the render context's structure ripples into these functions.

The fix: these functions should return `(logs, structured_result)` - e.g., an updated `CombatState` and `stats` - and the gameplay orchestrators in `gameplay/combat.py` should assemble the render context. `gameplay/combat.py` already exists precisely for this purpose. This is the most significant structural issue in the service layer.

**Moderate concern: `progression.py` layout**

Constants (`XP_THRESHOLDS`, `MAX_LEVEL`, `RANK_TITLES`, `LEVEL_UP_FLAVOR`, `XP_AWARDS`) are placed at lines 140-176, after the functions at lines 1-138 that reference them. Readers encounter `MAX_LEVEL` and `XP_THRESHOLDS` mid-function before finding their definitions. Moving constants above functions is a one-time readability fix.

---

## 3. Model Layer

**Clean overall - no business logic in models.**

- **`world.py`**: `Scene.clean()` is thorough - enforces `ending_type`/`scene_type` bi-implication (the April audit finding is resolved), key prefix convention, roll stat validity. `Choice.clean()` validates routing semantics and flag name registry. `validate_choice_routing()` enforces quest ownership and hub-return rules correctly. All appropriate for model validation.

- **`player.py`**: Data-only. Constraints use `UniqueConstraint`. The heat TODO comment (`player.py:38-40`) is explicit and intentional.

- **`requirements.py`**: The evaluator registry pattern is correct and extensible. Adding a new condition type is a single decorated function, not a modified chain. This is good design.

- **`combat.py`**: `CombatState` still uses 4 separate nullable fields for the pending enemy attack. The `enemy_attack_pending` property correctly consolidates the null-checks and `consume_enemy_attack` reads all four into a `PendingEnemyAttack` dataclass. Functional, but structurally verbose. Still tracked debt.

**Three minor model gaps (none causing current bugs):**

1. **`CompletedQuest.ending_type`** (`player.py:125`) is a bare `CharField(max_length=20)` with no `choices=` argument. Values come through a controlled path (`maybe_complete_quest` -> `next_scene.ending_type`), which is validated by `Scene.clean()`. The constraint chain works but is indirect; a direct `choices=` on the field would catch authoring or import errors at the DB edge.

2. **`Requirement.evaluate()`** (`requirements.py:99-102`) silently returns `False` for unknown `condition_type` values. A typo in an authoring tool would silently fail all players on a gate rather than raising a visible error. A `logging.warning()` call for the unknown-type branch would surface authoring mistakes.

3. **`PlayerStats.heat`** is floor-clamped to `max(0, ...)` in services but carries no `MinValueValidator` at the model level. Minor inconsistency between runtime and DB constraint.

---

## 4. View Layer

**Clean, with one known violation (covered in Â§1).**

- **`combat.py`**: All three views are POST-only, fully delegate to `gameplay.*`, and handle `GameplayError`. Exactly right.
- **`quests.py`**: Same pattern. Clean.
- **`navigation.py:game_hub`**: Session creation and redirect. Clean.
- **`navigation.py:choice_resolve`**: POST-only, delegates to `gameplay.resolve_choice`, builds context from result. Clean.
- **Quest builder views**: All views delegate to service functions. The hand-rolled `gang_id_{index}` / `standing_change_{index}` loop in `scenes.py:273-286` is already tracked in the debt register.

**One minor inconsistency:**

`player.py:32` - `level_up` calls `spend_stat_point` and `restore_hp_on_stat_upgrade` (correctly, as services), then constructs and writes the log entry itself: `log_event(session, f"{public_name.upper()} increased to {new_value}, {healed} HP restored.")`. The string-formatting of that log message is arguably game logic (what gets reported and how) that belongs in the service, not the view. Low impact, but inconsistent with the "services return log strings" direction being applied elsewhere.

---

## 5. Code Quality and Patterns

**Dead code:**

- `shared.py:38-57` (`_render_current_scene`): defined, never called. Safe to delete.

**Inconsistent patterns:**

1. `quest_builder/__init__.py:33-38`: Private aliases assigned immediately after the same names are imported - `_build_canvas_data = build_canvas_data`, etc. - then exported in `__all__`. Private names in `__all__` is self-contradictory; they appear to have no callers. If they existed for backward compatibility, that compat window has passed. These six assignments should be removed.

2. Log flushing uses `flush_event_log` (batch) for main log queues and `log_event` (single-entry) for combat init logs, producing two separate `_trim_overflow` calls per transition. This works but means the EventLog trim runs twice. Appending the combat init log to the main queue before flushing once would be cleaner.

**`combat.py` calls into the rendering layer:**

`execute_player_attack` and `execute_enemy_attack` call `build_render_context`, meaning the combat service imports and depends on the session/rendering service. See Â§2 for the full analysis and fix direction.

**ARCHITECTURE.md is stale:**

The Package Layout section lists modules that no longer exist: `jobs.py`, `jobs_common.py`, `jobs_eligibility.py`, `jobs_flags.py`, `jobs_lifecycle.py`, `jobs_listing.py`, `jobs_rewards.py`, `jobs_rolls.py` (all removed). It also lists `views.py` and `quest_builder_views.py` as monolith files - both are now packages. The Core Flow section still includes the jobs sub-loop. The Known Refactor Priorities links to `refactor-inventory.md` which has been deleted. The doc was marked "Last Verified Against Code: 2026-05-02" but was not updated during the recent refactor sprint.

---

## 6. Known Debt vs Undocumented Debt

### April 2026 audit items - current status

| Item | Status |
|---|---|
| `arrival.py`: no `transaction.atomic` wrapper | â Resolved - atomic block present |
| `views.py`: `target_scene` used without None check | â Resolved for choice routing; â ï¸ `CombatEncounter` still unguarded in `initialize_combat_state` |
| `combat.py`/`property_service.py`: `EventLog.objects.create()` direct calls | â Resolved - helpers used throughout |
| `models/world.py`: `Scene.clean()` doesn't enforce `ending_type` â `scene_type` | â Resolved - bi-implication enforced at lines 182-185 |
| `quest_builder.py`: God-file | â Resolved - proper package with split modules |
| `PlayerContext` construction repeated | â Resolved - `build_player_context()` helper |
| `views.py`: session loading repeated in every view | â Resolved - `@require_game_session` decorator |
| `progression.py`: TOCTOU race on `CompletedQuest` | â Resolved - `get_or_create` used |
| `constants.py`: `STAT_FIELD_MAP` naming confusion | â Resolved - `STAT_DISPLAY_NAMES` / `STAT_FIELDS` |
| `requirements.py`: 30-line `elif` chain | â Resolved - evaluator registry pattern |
| `arrival.py`: effect pipeline hard to reorder/extend | â ï¸ Open - `advance_to_scene` still outside atomic scope |
| `models/combat.py`: 4 nullable fields for pending attack | â ï¸ Open - still present |

### Tech debt register items - current status

| Item | Status |
|---|---|
| Legacy flag allowance path | â ï¸ Confirmed present (`Choice.clean()` lines 278-304) |
| Dual event trigger names | â ï¸ Confirmed present (`dual_event_triggers` in quest builder views) |
| Import orchestration key-based detection | Unverified - importers not audited |
| Heat-decay deferred | â ï¸ Confirmed (TODO comment `player.py:38-40`) |
| Dense context assembly | â Partially addressed - three named builder functions in `session.py` |
| Hand-rolled POST row parsing | â ï¸ Confirmed (`scene_gang_standings_save` `scenes.py:273-286`) |

### Newly found - not in any tracked document

1. **`shared.py:_render_current_scene` is dead code** (lines 38-57). Never called. Delete it.

2. **Outer atomicity gap in transition sequences** - `advance_to_scene` + `process_arrival` are not wrapped in an outer `transaction.atomic()` in `resolve_choice.py`, `start_quest.py`, or `resolve_combat_end`. This is distinct from and more severe than the April audit item, which only asked for `process_arrival` to be internally atomic.

3. **`quest_builder/__init__.py` private aliases in `__all__`** (lines 33-38, 67-73) - six dead re-assignments that contradict the visibility semantics of `__all__`.

4. **ARCHITECTURE.md is significantly stale** - lists the removed jobs subsystem, the pre-refactor monolith file layout, and a deleted `refactor-inventory.md`.

5. **`Requirement.evaluate()` silently returns `False` for unknown condition types** (`requirements.py:101`). An authoring typo would silently gate all players. A log warning for the unknown-type branch would surface these errors.

6. **`CompletedQuest.ending_type` has no model-level `choices=` constraint** (`player.py:125`). Values are currently controlled via the quest system but the DB has no enforcement.

---

## Priority summary

| Priority | Finding |
|---|---|
| Correctness | Outer atomicity gap: `advance_to_scene` not inside outer `transaction.atomic()` in `resolve_choice.py`, `start_quest.py`, `resolve_combat_end` |
| Correctness | `CombatEncounter.DoesNotExist` unhandled in `initialize_combat_state:68` -> uncaught 500 |
| Structural | `execute_player_attack`/`execute_enemy_attack` call `build_render_context` - combat service owns a rendering concern |
| Structural | `scene_detail` GET writes `CombatState` and `EventLog` - write-side effect on read path |
| Quality | `shared.py:_render_current_scene` is dead code |
| Quality | ARCHITECTURE.md is stale - lists removed modules and pre-refactor layout |
| Quality | `quest_builder/__init__.py` private aliases in `__all__` |
| Tracked debt | Legacy flag allowance path, dual trigger names, hand-rolled POST parsing, pending-attack 4-field model, heat-decay TODO |

---

## Source: refactor-audit-2026-05-07.md

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
4. Duplicated write log now behavior spread across gameplay modules instead of one event-emission contract.

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

---

## Source: tech-debt-register.md

# Tech Debt Register

## Scope
Inventory of shortcuts, workarounds, missing features, and scaling risks observed in the current codebase.

## Active debt

### High

1. Legacy allowance path remains in flag validation for existing rows.
- Files:
  - [`game/models/world.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/world.py)
  - [`game/services/flag_registry.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/flag_registry.py)
- Evidence:
  - `Choice.clean()` passes prior persisted values as `legacy_values` into `validate_flag_name(...)`.
- Risk:
  - Keeps transitional invalid historical states alive and weakens strict registry invariants.

2. Compatibility event contract still emits dual legacy + normalized trigger names.
- Files:
  - [`.docs/ENDPOINT_RESPONSE_CONTRACT.md`](/C:/Users/colin/PycharmProjects/soloBrowserGame/.docs/ENDPOINT_RESPONSE_CONTRACT.md)
  - [`game/quest_builder_views/scenes.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views/scenes.py)
  - [`game/quest_builder_views/choices.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views/choices.py)
- Risk:
  - Dual naming (`sceneUpdated` + `scene.updated`, etc.) increases long-term backend/frontend contract complexity.

3. Import orchestration still depends on key-based detection and centralized dispatch.
- Files:
  - [`game/services/importers/orchestrator.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/orchestrator.py)
- Evidence:
  - `detect_import_type(...)` infers domain from top-level YAML keys.
  - `IMPORT_HANDLERS` central map controls per-domain execution.
- Risk:
  - Ambiguous or malformed content can route to unexpected import paths; behavior remains stringly/config-shaped.

### Medium

1. Heat-decay gameplay rule is still deferred.
- File:
  - [`game/models/player.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/player.py)
- Evidence:
  - Inline TODO explicitly says planned per-turn heat decay is not implemented.
- Risk:
  - Balance/economy behavior can drift from intended design.

2. Context assembly remains dense and cross-domain.
- File:
  - [`game/services/session.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/session.py)
- Risk:
  - New panel/features can impact unrelated rendering paths and expand coupling.

3. Hand-rolled POST row parsing still exists in quest builder endpoints.
- File:
  - [`game/quest_builder_views/scenes.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views/scenes.py)
- Evidence:
  - `scene_gang_standings_save` manually loops `gang_id_<n>`/`standing_change_<n>` keys.
- Risk:
  - Input-shape bugs and inconsistent parsing behavior versus shared parser helpers.

### Operability / hygiene

1. Generated `__pycache__` artifacts are present in the repository tree.
- Paths:
  - Multiple `__pycache__` directories under `core/` and `game/**`.
- Risk:
  - Repo noise and accidental stale artifact commits.

2. Encoding/mojibake artifacts remain in user-facing strings/comments.
- Files seen with artifacts:
  - [`game/models/player.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/player.py)
  - [`game/services/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/combat.py)
- Risk:
  - Text quality issues and possible rendering inconsistencies.

1

