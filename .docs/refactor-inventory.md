# Refactor Inventory (Codebase-Wide)

## Scope
This is a static refactor audit of the current repository. No code changes were made.

Last reviewed: 2026-05-07. Status legend: ✅ Resolved · ⚠️ Partial · ❌ Not started · 🗑️ Obsolete (code removed)

---

## Highest-value refactor targets

1. ❌ `game/quest_builder_views.py` is a God-view module — now **683 lines** (grew from 636).
- File: [`game/quest_builder_views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views.py)
- Why refactor:
  - Heavy duplication of `response_utils.error_response(...)` payloads and inline template paths.
  - Repeated POST parsing loops (`scene_items_save`, `scene_contacts_save`) that should be shared utilities/forms.
  - Mixed concerns: request parsing + permission checks + data shaping + rendering + trigger protocol.
- Suggested direction:
  - Split by resource (`scene_*`, `choice_*`, `quest_*`) into separate modules.
  - Introduce a small helper for standardized inline admin errors and trigger envelopes.
  - Move repeated POST row extraction into service/form helpers.
  - `game/presentation/responses.py` already exists — use it here instead of duplicating error patterns.

2. ❌ `game/admin.py` is overloaded — now **561 lines** (down from 590, but not split).
- File: [`game/admin.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/admin.py)
- Why refactor:
  - Too many responsibilities in one file.
  - Large `QuestAdmin.get_urls()` block is brittle and hard to review.
  - Several text rendering helpers are embedded where reusable admin mixins would be cleaner.
- Suggested direction:
  - Split into `admin/` package by domain (world, player, jobs, combat, quest_builder integration).
  - Extract quest-builder admin URL definitions into a dedicated module.

3. ⚠️ `game/views.py` reduced but still a single module — now **223 lines** (down from 371).
- File: [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py)
- What changed:
  - `require_game_session` decorator added — eliminates session-loading repetition across views.
  - Jobs and job-run views removed entirely (jobs system gone).
  - `_htmx_response` now routes through a single template.
  - Combat/quest/item logic delegated to `services/gameplay/` use-case modules.
- Still to do:
  - `views.py` is still one file; domain split into `views/navigation.py`, `views/combat.py`, etc. not done.

4. ❌ `game/services/combat.py` — now **405 lines** (grew from 370).
- File: [`game/services/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/combat.py)
- Why refactor:
  - Pure roll math (`resolve_player_attack`, `resolve_enemy_attack`) coexists with DB persistence and scene-transition orchestration.
  - Legacy pending attack fallback logic still present (`_has_legacy_pending_enemy_attack_field`, JSON fallback path at lines 342–400).
  - String formatting/log assembly repeated across player/enemy paths.
- Note: `game/services/gameplay/combat.py` partially separates orchestration from roll math, but the core file still mixes concerns.
- Suggested direction:
  - Isolate/remove legacy compatibility path behind a migration cutoff.
  - The orchestration wrapper in `gameplay/combat.py` is the right pattern — continue moving persistence/scene-transition logic there and leave `services/combat.py` as pure engine.

5. ❌ `game/services/importers/domain.py` — now **403 lines** (grew from 352).
- File: [`game/services/importers/domain.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/domain.py)
- Why refactor:
  - Handles items/enemies/world/hubs/quests in one module.
  - Bookkeeping patterns are now centralized via `ImportResult` (see import pipeline below), but per-domain import functions are still all in this file.
  - Hard to extend safely due to broad function surface.
- Suggested direction:
  - Split into per-domain import modules (`items.py`, `world.py`, `hubs.py`, `quests.py`).

---

## Architecture-rule mismatches (business logic leaking into views)

1. 🗑️ Jobs input validation and domain object lookup logic in views.
- **Resolved by removal.** The jobs system (`jobs_lifecycle.py`, `jobs_listing.py`, job model, job views) has been entirely removed from the codebase. This issue no longer exists.

2. ❌ Quest builder views embed significant business/process rules.
- File: [`game/quest_builder_views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views.py)
- Examples:
  - Ownership checks and request-shape rules repeated across choice/scene endpoints.
  - Normalization logic (boolean parsing, dynamic row parsing) inline.
- Refactor:
  - Keep views thin; move rule-heavy parsing/validation into quest_builder services/forms.

---

## Duplication and consistency issues

1. ✅ Repeated inline error template literals and trigger payloads.
- **Resolved.** `game/presentation/responses.py` now provides `error_response()`, `render_htmx_fragment()`, `attach_triggers()`, and `empty_response()`. Used in `views.py`; needs adoption in `quest_builder_views.py`.

2. 🗑️ Repeated recon-tier text selection logic across modules.
- **Obsolete.** Both `jobs_lifecycle.py` and `jobs_listing.py` have been removed along with the jobs system.

3. ❌ Event trigger naming duplication (`snake_case` + `dot.case`) repeated manually.
- File: [`game/quest_builder_views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views.py)
- Refactor:
  - helper that emits both naming conventions from one source object.

---

## Data model refactor candidates

1. ⚠️ Legacy-compatibility code in model validation paths.
- Files:
  - [`game/models/world.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/world.py) — `clean()` improved: now enforces `ending_type ↔ scene_type == "ending"` bidirectionally.
  - `game/models/jobs.py` — **gone** (jobs system removed).
- Remaining:
  - Review world.py `clean()` for any remaining legacy-value allowances that are no longer needed.

2. ❌ Potential model-method extraction opportunity for routing validation.
- File: [`game/models/world.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/world.py)
- Why:
  - Scene/Choice routing semantics are spread between models/services/views.
- Refactor:
  - encapsulate route-shape validation in model/service validators to reduce duplicated assumptions.

---

## Service-layer design refactor targets

1. ❌ `game/services/session.py` context builder is dense — **157 lines**, mixes gameplay/social/jobs presentation concerns.
- File: [`game/services/session.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/session.py)
- Refactor:
  - break context assembly into composable providers with explicit contracts.

2. ⚠️ `game/services/export_game_state.py` partially decomposed — **277 lines** (player/session export).
- Files:
  - [`game/services/export_game_state.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/export_game_state.py) — player/session state export, still 277 lines.
  - [`game/services/domain_export.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/domain_export.py) — world/domain data export extracted, 254 lines.
  - [`game/services/quest_export.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/quest_export.py) — quest export extracted, 172 lines.
- Still to do:
  - `export_game_state.py` itself could be further split by domain section.

3. 🗑️ Jobs package leaky private exports (`_roll_check`, `_tier_rank`).
- **Obsolete.** The jobs package has been removed.

---

## Import pipeline refactor targets

1. ⚠️ Type detection + dispatch is still stringly-typed.
- File: [`game/services/importers/orchestrator.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/orchestrator.py)
- What changed: `ImportResult`/`ImportCounts` dataclasses added to `importers/types.py` (good).
- Still to do: `detect_import_type()` returns plain strings; `_import_typed_data()` dispatches via `if/elif` string chain. Replace with an enum registry mapping type → handler function.

2. ✅ Shared import bookkeeping is repeated.
- **Resolved.** `game/services/importers/types.py` provides `ImportResult` with centralized `record_created()`, `record_updated()`, `record_deleted()`, `warn()`, and `merge()` methods.

---

## Template/UI layer refactor targets

1. ❌ Inline JavaScript embedded in admin partial templates.
- Files:
  - [`templates/admin/quest_builder/partials/items_section.html`](/C:/Users/colin/PycharmProjects/soloBrowserGame/templates/admin/quest_builder/partials/items_section.html)
  - [`templates/admin/quest_builder/partials/contacts_section.html`](/C:/Users/colin/PycharmProjects/soloBrowserGame/templates/admin/quest_builder/partials/contacts_section.html)
  - [`templates/admin/quest_builder/partials/requirements_section.html`](/C:/Users/colin/PycharmProjects/soloBrowserGame/templates/admin/quest_builder/partials/requirements_section.html)
  - [`templates/admin/quest_builder/partials/scene_panel.html`](/C:/Users/colin/PycharmProjects/soloBrowserGame/templates/admin/quest_builder/partials/scene_panel.html)
  - [`templates/admin/quest_builder/partials/choice_panel.html`](/C:/Users/colin/PycharmProjects/soloBrowserGame/templates/admin/quest_builder/partials/choice_panel.html)
- Why:
  - duplicated DOM-template row-add logic, harder to lint/test.
- Refactor:
  - extract shared JS to a static module and parameterize selectors/data attributes.

---

## Technical debt markers and cleanup candidates

1. ❌ Explicit TODO remains in production model.
- File: [`game/models/player.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/player.py) line 38
- Note:
  - `heat decay per turn` TODO indicates incomplete gameplay rule placement.

2. ❌ Legacy migration shims still active.
- File: [`game/services/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/combat.py) lines 342–400
- `_has_legacy_pending_enemy_attack_field` and JSON fallback path still present.
- `game/models/jobs.py` legacy compat removed (file gone).
- Refactor:
  - plan explicit retirement: check if any live sessions still carry the legacy `pending_enemy_attack` JSON field, then drop the fallback path.

3. ✅ Encoding artifacts in source strings/doc comments.
- **Resolved.** Remaining non-ASCII characters (`—`, `→`, `–`) are intentional formatting in game log strings and admin display helpers, not encoding corruption.

4. ❌ Committed `__pycache__` artifacts appear in repository tree.
- Paths: `core/__pycache__/`, `game/__pycache__/`, and nested `game/**/__pycache__/`.
- `.gitignore` has `__pycache__/` but the directories were committed before the rule was added.
- Refactor:
  - `git rm --cached -r core/__pycache__ game/__pycache__` (and any nested ones), then commit.

---

## Test-suite refactor opportunities

1. ❌ Very large integration-heavy test modules are hard to maintain.
- Files:
  - [`game/tests/test_combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_combat.py) — **664 lines**
  - [`game/tests/test_navigation.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_navigation.py) — **625 lines**
  - `game/tests/test_jobs_views.py` — **gone** (removed with jobs system)
- Refactor:
  - split by endpoint/behavioral area and introduce reusable assertion helpers.

2. ❌ Repeated setup patterns should move to shared fixtures/factories.
- Files across `game/tests/`.
- Refactor:
  - centralize session/bootstrap, common builders, and HTMX helper assertions.

---

## Medium/low priority structure cleanups

1. ❌ URL/view segmentation could be clearer for admin builder vs runtime game flows.
- Files:
  - [`game/urls.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/urls.py)
  - [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py)

2. ❌ Import ordering/style and helper naming consistency can be standardized.
- Cross-cutting minor cleanup for readability.

3. ⚠️ Some service modules are still broad despite package split.
- Files:
  - [`game/services/progression.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/progression.py) — **176 lines**
  - [`game/services/quest_builder/canvas.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/quest_builder/canvas.py) — **235 lines**
  - `game/services/jobs_listing.py` — **gone**

---

## Architectural additions since original audit (good patterns to extend)

These didn't exist before and represent positive structural progress:

- **`game/presentation/responses.py`** — centralized HTMX/error response helpers. Adopt in `quest_builder_views.py`.
- **`game/services/gameplay/` package** (`resolve_choice.py`, `start_quest.py`, `use_item.py`, `combat.py`) — use-case orchestration layer. The right place for remaining view-side logic that's not pure HTTP concerns.
- **`game/services/types.py`** — shared domain types (`GameplayError`, `ChoiceResult`, `PendingEnemyAttack`, `EffectiveStats`, etc.). Extend here rather than defining types inline.
- **`game/services/quest_builder/` package** — fully split from the original 776-line monolith into `canvas.py`, `mutations.py`, `validation.py`, `requirements.py`, `parsing.py`, `shared.py`.
- **`game/services/importers/types.py`** — `ImportResult`/`ImportCounts` dataclasses centralize import bookkeeping.

---

## Suggested refactor order

1. ❌ Remove `__pycache__` from git tracking (5-minute cleanup, reduces noise).
2. ❌ Retire legacy pending-attack fallback in `services/combat.py` (clear debt, enables simplification).
3. ❌ Extract and slim `quest_builder_views.py` using `presentation/responses.py` + quest_builder service layer.
4. ❌ Split `admin.py` into domain modules.
5. ❌ Finish splitting `views.py` by domain and formalize `services/gameplay/` as the canonical use-case layer.
6. ❌ Split `services/importers/domain.py` into per-domain import modules; replace string dispatch with enum registry.
7. ❌ Template JS extraction and test suite modularization.