# Codebase Audit Report — soloBrowserGame

*Audit date: 2026-05-07. Code verified against current HEAD.*

---

## 1. Violations of Architectural Invariants

### Invariant: Services should not write EventLog directly
**Clean — no violations.**

`EventLog.objects.create()` exists in exactly one place: `models/events.py:9`, inside the `log_event()` helper. All gameplay code reaches EventLog through `flush_event_log()` or `log_event()`. The direction of travel — services return strings, callers flush — is being followed, with `log_event` called from views only for single post-transition log entries (combat init). The ARCHITECTURE.md correctly notes this is a transition-period pattern, not a permanent exception. Nothing to fix here beyond the existing direction.

---

### Invariant: Write-side effects on GET paths
**One violation, pre-existing and tracked.**

`navigation.py:37-39` — `scene_detail` is a GET handler that calls `initialize_combat_state(game_session, scene)`, which can CREATE a `CombatState` row and produce an init log, followed by `log_event(game_session, combat_init_log)`. A read-only page view is writing to two tables.

`shared.py:38-57` — `_render_current_scene` has the identical problem (calls `initialize_combat_state` + `log_event` on a GET). However, this function is **never called anywhere** — it is dead code (see §5).

The violation in `scene_detail` is already listed in ARCHITECTURE.md's Known Refactor Priorities: "Remove write-side effects from `scene_detail` GET path." The correct fix is to handle combat initialization only on POST transitions (e.g., move it to `resolve_choice`) and drop the write from the GET view.

---

### Invariant: Missing atomic boundaries around multi-step state transitions
**One gap, newly identified — not in any tracked document.**

`process_arrival` is now correctly wrapped in `transaction.atomic()` — the April 2026 audit item is resolved. But the *calling sequences* are not wrapped in an outer transaction:

- `resolve_choice.py:49-51`: `advance_to_scene(session, next_scene)` (writes `session.current_scene`) runs before `process_arrival(...)`. If `process_arrival` fails, the session is permanently at the new scene with no rewards applied.
- `start_quest.py:21-23`: Same pattern.
- `combat.py:257-261` in `resolve_combat_end`: `combat_state.save()` and then `session.save()` execute as separate committed transactions before `process_arrival`. A failure between any of these leaves the game in inconsistent state.

The fix in all three cases is the same: wrap `advance_to_scene + process_arrival` (and the preceding saves in `resolve_combat_end`) in an outer `with transaction.atomic():` block. Because `process_arrival` uses its own `transaction.atomic()` internally, SQLite/Django will correctly downgrade that inner call to a savepoint when inside an outer transaction.

---

### Invariant: Unguarded FK pointers (combat encounter scenes, entrance scenes, target scenes)
**One unguarded pointer — pre-existing, tracked in ARCHITECTURE.md.**

`combat.py:68` — `CombatEncounter.objects.select_related('enemy').get(scene=scene)` in `initialize_combat_state` has no try/except. If a scene has `scene_type='combat'` but no `CombatEncounter` row, this raises an unhandled `DoesNotExist` and produces a 500. Crucially, this path is called from `scene_detail` (view level), where there is no `GameplayError` handler to catch it.

The `run_enemy_attack` gameplay orchestrator *does* catch `CombatEncounter.DoesNotExist` and converts it to a `GameplayError` — but only for the enemy-resolve path, not for initialization.

All other pointers are correctly guarded:
- `quest.entrance_scene` → `start_quest.py:17`, raises `GameplayError`
- `choice.target_scene` → `resolve_choice.py:34`, raises `GameplayError`
- `choice.success_scene/failure_scene` → `resolve_choice.py:23-32`, raises `GameplayError`
- `encounter.victory_scene/defeat_scene` → `resolve_combat_end`, raises `GameplayError`

---

## 2. Service Layer Structure

**Well-bounded and appropriately scoped:**

| Service | Lines | Assessment |
|---|---|---|
| `scene.py` | 115 | Clean — roll resolution, choice filtering, notice board |
| `arrival.py` | 61 | Clean — single function, well-documented, atomic |
| `flags.py` | 41 | Clean — single responsibility |
| `flag_registry.py` | 102 | Clean — registry validation. Legacy allowance tracked |
| `inventory.py` | 160 | Clean — all item/contact/territory operations |
| `property_service.py` | 112 | Clean — turn income and property rewards |
| `combat_engine.py` | 37 | Clean — pure math, zero DB access |
| `types.py` | 85 | Clean — data types only |
| `gameplay/*` | 4 small files | Clean — thin orchestration shells |
| `quest_builder/*` | package | Clean — properly decomposed |

**Structural problem: `combat.py:79-156` and `159-227`**

`execute_player_attack` and `execute_enemy_attack` call `build_render_context` from the session service at the end of their logic. This means the combat service has a compile-time dependency on the template rendering layer, and assembles full page contexts (including social data, hub data, property lists) inside functions whose domain is combat mechanics. Any change to the render context's structure ripples into these functions.

The fix: these functions should return `(logs, structured_result)` — e.g., an updated `CombatState` and `stats` — and the gameplay orchestrators in `gameplay/combat.py` should assemble the render context. `gameplay/combat.py` already exists precisely for this purpose. This is the most significant structural issue in the service layer.

**Moderate concern: `progression.py` layout**

Constants (`XP_THRESHOLDS`, `MAX_LEVEL`, `RANK_TITLES`, `LEVEL_UP_FLAVOR`, `XP_AWARDS`) are placed at lines 140-176, after the functions at lines 1-138 that reference them. Readers encounter `MAX_LEVEL` and `XP_THRESHOLDS` mid-function before finding their definitions. Moving constants above functions is a one-time readability fix.

---

## 3. Model Layer

**Clean overall — no business logic in models.**

- **`world.py`**: `Scene.clean()` is thorough — enforces `ending_type`/`scene_type` bi-implication (the April audit finding is resolved), key prefix convention, roll stat validity. `Choice.clean()` validates routing semantics and flag name registry. `validate_choice_routing()` enforces quest ownership and hub-return rules correctly. All appropriate for model validation.

- **`player.py`**: Data-only. Constraints use `UniqueConstraint`. The heat TODO comment (`player.py:38-40`) is explicit and intentional.

- **`requirements.py`**: The evaluator registry pattern is correct and extensible. Adding a new condition type is a single decorated function, not a modified chain. This is good design.

- **`combat.py`**: `CombatState` still uses 4 separate nullable fields for the pending enemy attack. The `enemy_attack_pending` property correctly consolidates the null-checks and `consume_enemy_attack` reads all four into a `PendingEnemyAttack` dataclass. Functional, but structurally verbose. Still tracked debt.

**Three minor model gaps (none causing current bugs):**

1. **`CompletedQuest.ending_type`** (`player.py:125`) is a bare `CharField(max_length=20)` with no `choices=` argument. Values come through a controlled path (`maybe_complete_quest` → `next_scene.ending_type`), which is validated by `Scene.clean()`. The constraint chain works but is indirect; a direct `choices=` on the field would catch authoring or import errors at the DB edge.

2. **`Requirement.evaluate()`** (`requirements.py:99-102`) silently returns `False` for unknown `condition_type` values. A typo in an authoring tool would silently fail all players on a gate rather than raising a visible error. A `logging.warning()` call for the unknown-type branch would surface authoring mistakes.

3. **`PlayerStats.heat`** is floor-clamped to `max(0, ...)` in services but carries no `MinValueValidator` at the model level. Minor inconsistency between runtime and DB constraint.

---

## 4. View Layer

**Clean, with one known violation (covered in §1).**

- **`combat.py`**: All three views are POST-only, fully delegate to `gameplay.*`, and handle `GameplayError`. Exactly right.
- **`quests.py`**: Same pattern. Clean.
- **`navigation.py:game_hub`**: Session creation and redirect. Clean.
- **`navigation.py:choice_resolve`**: POST-only, delegates to `gameplay.resolve_choice`, builds context from result. Clean.
- **Quest builder views**: All views delegate to service functions. The hand-rolled `gang_id_{index}` / `standing_change_{index}` loop in `scenes.py:273-286` is already tracked in the debt register.

**One minor inconsistency:**

`player.py:32` — `level_up` calls `spend_stat_point` and `restore_hp_on_stat_upgrade` (correctly, as services), then constructs and writes the log entry itself: `log_event(session, f"{public_name.upper()} increased to {new_value}, {healed} HP restored.")`. The string-formatting of that log message is arguably game logic (what gets reported and how) that belongs in the service, not the view. Low impact, but inconsistent with the "services return log strings" direction being applied elsewhere.

---

## 5. Code Quality and Patterns

**Dead code:**

- `shared.py:38-57` (`_render_current_scene`): defined, never called. Safe to delete.

**Inconsistent patterns:**

1. `quest_builder/__init__.py:33-38`: Private aliases assigned immediately after the same names are imported — `_build_canvas_data = build_canvas_data`, etc. — then exported in `__all__`. Private names in `__all__` is self-contradictory; they appear to have no callers. If they existed for backward compatibility, that compat window has passed. These six assignments should be removed.

2. Log flushing uses `flush_event_log` (batch) for main log queues and `log_event` (single-entry) for combat init logs, producing two separate `_trim_overflow` calls per transition. This works but means the EventLog trim runs twice. Appending the combat init log to the main queue before flushing once would be cleaner.

**`combat.py` calls into the rendering layer:**

`execute_player_attack` and `execute_enemy_attack` call `build_render_context`, meaning the combat service imports and depends on the session/rendering service. See §2 for the full analysis and fix direction.

**ARCHITECTURE.md is stale:**

The Package Layout section lists modules that no longer exist: `jobs.py`, `jobs_common.py`, `jobs_eligibility.py`, `jobs_flags.py`, `jobs_lifecycle.py`, `jobs_listing.py`, `jobs_rewards.py`, `jobs_rolls.py` (all removed). It also lists `views.py` and `quest_builder_views.py` as monolith files — both are now packages. The Core Flow section still includes the jobs sub-loop. The Known Refactor Priorities links to `refactor-inventory.md` which has been deleted. The doc was marked "Last Verified Against Code: 2026-05-02" but was not updated during the recent refactor sprint.

---

## 6. Known Debt vs Undocumented Debt

### April 2026 audit items — current status

| Item | Status |
|---|---|
| `arrival.py`: no `transaction.atomic` wrapper | ✅ Resolved — atomic block present |
| `views.py`: `target_scene` used without None check | ✅ Resolved for choice routing; ⚠️ `CombatEncounter` still unguarded in `initialize_combat_state` |
| `combat.py`/`property_service.py`: `EventLog.objects.create()` direct calls | ✅ Resolved — helpers used throughout |
| `models/world.py`: `Scene.clean()` doesn't enforce `ending_type` ↔ `scene_type` | ✅ Resolved — bi-implication enforced at lines 182-185 |
| `quest_builder.py`: God-file | ✅ Resolved — proper package with split modules |
| `PlayerContext` construction repeated | ✅ Resolved — `build_player_context()` helper |
| `views.py`: session loading repeated in every view | ✅ Resolved — `@require_game_session` decorator |
| `progression.py`: TOCTOU race on `CompletedQuest` | ✅ Resolved — `get_or_create` used |
| `constants.py`: `STAT_FIELD_MAP` naming confusion | ✅ Resolved — `STAT_DISPLAY_NAMES` / `STAT_FIELDS` |
| `requirements.py`: 30-line `elif` chain | ✅ Resolved — evaluator registry pattern |
| `arrival.py`: effect pipeline hard to reorder/extend | ⚠️ Open — `advance_to_scene` still outside atomic scope |
| `models/combat.py`: 4 nullable fields for pending attack | ⚠️ Open — still present |

### Tech debt register items — current status

| Item | Status |
|---|---|
| Legacy flag allowance path | ⚠️ Confirmed present (`Choice.clean()` lines 278-304) |
| Dual event trigger names | ⚠️ Confirmed present (`dual_event_triggers` in quest builder views) |
| Import orchestration key-based detection | Unverified — importers not audited |
| Heat-decay deferred | ⚠️ Confirmed (TODO comment `player.py:38-40`) |
| Dense context assembly | ✅ Partially addressed — three named builder functions in `session.py` |
| Hand-rolled POST row parsing | ⚠️ Confirmed (`scene_gang_standings_save` `scenes.py:273-286`) |

### Newly found — not in any tracked document

1. **`shared.py:_render_current_scene` is dead code** (lines 38-57). Never called. Delete it.

2. **Outer atomicity gap in transition sequences** — `advance_to_scene` + `process_arrival` are not wrapped in an outer `transaction.atomic()` in `resolve_choice.py`, `start_quest.py`, or `resolve_combat_end`. This is distinct from and more severe than the April audit item, which only asked for `process_arrival` to be internally atomic.

3. **`quest_builder/__init__.py` private aliases in `__all__`** (lines 33-38, 67-73) — six dead re-assignments that contradict the visibility semantics of `__all__`.

4. **ARCHITECTURE.md is significantly stale** — lists the removed jobs subsystem, the pre-refactor monolith file layout, and a deleted `refactor-inventory.md`.

5. **`Requirement.evaluate()` silently returns `False` for unknown condition types** (`requirements.py:101`). An authoring typo would silently gate all players. A log warning for the unknown-type branch would surface these errors.

6. **`CompletedQuest.ending_type` has no model-level `choices=` constraint** (`player.py:125`). Values are currently controlled via the quest system but the DB has no enforcement.

---

## Priority summary

| Priority | Finding |
|---|---|
| Correctness | Outer atomicity gap: `advance_to_scene` not inside outer `transaction.atomic()` in `resolve_choice.py`, `start_quest.py`, `resolve_combat_end` |
| Correctness | `CombatEncounter.DoesNotExist` unhandled in `initialize_combat_state:68` → uncaught 500 |
| Structural | `execute_player_attack`/`execute_enemy_attack` call `build_render_context` — combat service owns a rendering concern |
| Structural | `scene_detail` GET writes `CombatState` and `EventLog` — write-side effect on read path |
| Quality | `shared.py:_render_current_scene` is dead code |
| Quality | ARCHITECTURE.md is stale — lists removed modules and pre-refactor layout |
| Quality | `quest_builder/__init__.py` private aliases in `__all__` |
| Tracked debt | Legacy flag allowance path, dual trigger names, hand-rolled POST parsing, pending-attack 4-field model, heat-decay TODO |