# Refactor Inventory (Codebase-Wide)

## Scope
This is a static refactor audit of the current repository. No code changes were made.

## Highest-value refactor targets

1. `game/quest_builder_views.py` is a God-view module (636 lines) with repeated response/error/trigger patterns.
- File: [`game/quest_builder_views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views.py)
- Why refactor:
  - Heavy duplication of `response_utils.error_response(...)` payloads and inline template paths.
  - Repeated POST parsing loops (`scene_items_save`, `scene_contacts_save`) that should be shared utilities/forms.
  - Mixed concerns: request parsing + permission checks + data shaping + rendering + trigger protocol.
- Suggested direction:
  - Split by resource (`scene_*`, `choice_*`, `quest_*`) into separate modules.
  - Introduce a small helper for standardized inline admin errors and trigger envelopes.
  - Move repeated POST row extraction into service/form helpers.

2. `game/admin.py` is overloaded (590 lines) and mixes registration, inlines, custom URLs, and builder wiring.
- File: [`game/admin.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/admin.py)
- Why refactor:
  - Too many responsibilities in one file.
  - Large `QuestAdmin.get_urls()` block is brittle and hard to review.
  - Several text rendering helpers are embedded where reusable admin mixins would be cleaner.
- Suggested direction:
  - Split into `admin/` package by domain (world, player, jobs, combat, quest_builder integration).
  - Extract quest-builder admin URL definitions into a dedicated module.

3. `game/views.py` central gameplay view module is too broad (371 lines, many endpoints).
- File: [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py)
- Why refactor:
  - Single module handles navigation, jobs, combat, progression, inventory.
  - Repeated method guards and error handling patterns.
  - `_render_current_scene` couples multiple cross-cutting concerns.
- Suggested direction:
  - Split views by bounded context (`views/navigation.py`, `views/jobs.py`, `views/combat.py`, etc.).
  - Introduce lightweight decorators/utilities for POST-only and standard gameplay error handling.

4. `game/services/combat.py` contains legacy-compatibility and orchestration complexity in one place (370 lines).
- File: [`game/services/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/combat.py)
- Why refactor:
  - Mixes pure roll math, DB persistence, scene transitions, render-context shaping.
  - Legacy pending attack fallback logic still present (`_has_legacy_pending_enemy_attack_field`, JSON fallback path).
  - String formatting/log assembly repeated across player/enemy paths.
- Suggested direction:
  - Separate pure combat engine from persistence/scene-transition orchestrator.
  - Isolate/remove legacy compatibility path behind a migration cutoff.

5. `game/services/importers/domain.py` is a large procedural importer with many responsibilities (352 lines).
- File: [`game/services/importers/domain.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/domain.py)
- Why refactor:
  - Handles items/enemies/world/hubs/quests in one module.
  - Repeated create/update bookkeeping and similar hydration/validation patterns.
  - Hard to extend safely due to broad function surface.
- Suggested direction:
  - Split into per-domain import modules (`items.py`, `world.py`, `hubs.py`, `quests.py`).
  - Introduce shared helper layer for upsert + result accounting.

## Architecture-rule mismatches (business logic leaking into views)

1. Jobs input validation and domain object lookup logic in views.
- File: [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py)
- Examples:
  - `job_run_beat_1`: validates `approach` key and resolves `JobApproach` directly in view.
  - `job_run_beat_2`: validates `action` key in view.
- Refactor:
  - Move request-to-command validation and entity resolution into service-layer command handlers.

2. Quest builder views embed significant business/process rules.
- File: [`game/quest_builder_views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views.py)
- Examples:
  - Ownership checks and request-shape rules repeated across choice/scene endpoints.
  - Normalization logic (boolean parsing, dynamic row parsing) inline.
- Refactor:
  - Keep views thin; move rule-heavy parsing/validation into quest_builder services/forms.

## Duplication and consistency issues

1. Repeated inline error template literals and trigger payloads.
- File: [`game/quest_builder_views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views.py)
- Refactor:
  - central constants/helper for inline error response.

2. Repeated recon-tier text selection logic across modules.
- Files:
  - [`game/services/jobs_lifecycle.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/jobs_lifecycle.py)
  - [`game/services/jobs_listing.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/jobs_listing.py)
- Refactor:
  - consolidate `_get_recon_text_for_tier` into single shared helper.

3. Event trigger naming duplication (`snake_case` + `dot.case`) repeated manually.
- File: [`game/quest_builder_views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views.py)
- Refactor:
  - helper that emits both naming conventions from one source object.

## Data model refactor candidates

1. Legacy-compatibility code in model validation paths.
- Files:
  - [`game/models/world.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/world.py)
  - [`game/models/jobs.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/jobs.py)
- Why:
  - `clean()` methods include legacy-value allowance behavior that may no longer be needed.
- Refactor:
  - remove legacy branches after migration window is closed.

2. Potential model-method extraction opportunity for routing validation.
- File: [`game/models/world.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/world.py)
- Why:
  - Scene/Choice routing semantics are spread between models/services/views.
- Refactor:
  - encapsulate route-shape validation in model/service validators to reduce duplicated assumptions.

## Service-layer design refactor targets

1. `game/services/session.py` context builder is very dense and mixes gameplay/social/jobs presentation concerns.
- File: [`game/services/session.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/session.py)
- Refactor:
  - break context assembly into composable providers with explicit contracts.

2. `game/services/export_game_state.py` is large and likely needs decomposition.
- File: [`game/services/export_game_state.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/export_game_state.py)
- Why:
  - high line count and broad payload responsibility.
- Refactor:
  - split serializers by domain sections with schema/version module.

3. Jobs package has some leaky private exports.
- File: [`game/services/jobs.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/jobs.py)
- Why:
  - re-exports private helpers (`_roll_check`, `_tier_rank`, etc.) via public aggregator.
- Refactor:
  - tighten public API; avoid exporting underscore-prefixed internals.

## Import pipeline refactor targets

1. Type detection + dispatch is stringly-typed.
- File: [`game/services/importers/orchestrator.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/orchestrator.py)
- Refactor:
  - use enum/typed registry for import types and handlers.

2. Shared import bookkeeping is repeated.
- File: [`game/services/importers/domain.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/domain.py)
- Refactor:
  - centralize `created/updated/deleted/warn` patterns and upsert wrappers.

## Template/UI layer refactor targets

1. Inline JavaScript embedded in admin partial templates.
- Files:
  - [`templates/admin/quest_builder/partials/items_section.html`](/C:/Users/colin/PycharmProjects/soloBrowserGame/templates/admin/quest_builder/partials/items_section.html)
  - [`templates/admin/quest_builder/partials/contacts_section.html`](/C:/Users/colin/PycharmProjects/soloBrowserGame/templates/admin/quest_builder/partials/contacts_section.html)
  - [`templates/admin/quest_builder/partials/requirements_section.html`](/C:/Users/colin/PycharmProjects/soloBrowserGame/templates/admin/quest_builder/partials/requirements_section.html)
- Why:
  - duplicated DOM-template row-add logic, harder to lint/test.
- Refactor:
  - extract shared JS to a static module and parameterize selectors/data attributes.

## Technical debt markers and cleanup candidates

1. Explicit TODO remains in production model.
- File: [`game/models/player.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/player.py)
- Note:
  - `heat decay per turn` TODO indicates incomplete gameplay rule placement.

2. Legacy migration shims still active.
- Files:
  - [`game/services/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/combat.py)
  - [`game/models/world.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/world.py)
  - [`game/models/jobs.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/jobs.py)
- Refactor:
  - plan explicit debt retirement issue(s) with removal criteria.

3. Encoding artifacts in source strings/doc comments.
- Files seen with mojibake-like glyphs:
  - [`game/admin.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/admin.py)
  - [`game/services/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/combat.py)
  - [`game/models/player.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/player.py)
- Refactor:
  - normalize text encoding and enforce via lint/test gate.

4. Committed `__pycache__` artifacts appear in repository tree.
- Path examples under `game/**/__pycache__/...`
- Refactor:
  - enforce `.gitignore` hygiene and remove generated artifacts from version control.

## Test-suite refactor opportunities

1. Very large integration-heavy test modules are hard to maintain.
- Files:
  - [`game/tests/test_jobs_views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_jobs_views.py)
  - [`game/tests/test_navigation.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_navigation.py)
  - [`game/tests/test_combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_combat.py)
- Refactor:
  - split by endpoint/behavioral area and introduce reusable assertion helpers.

2. Repeated setup patterns should move to shared fixtures/factories.
- Files across `game/tests/`.
- Refactor:
  - centralize session/bootstrap, common job graph builders, and HTMX helper assertions.

## Medium/low priority structure cleanups

1. URL/view segmentation could be clearer for admin builder vs runtime game flows.
- Files:
  - [`game/urls.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/urls.py)
  - [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py)

2. Import ordering/style and helper naming consistency can be standardized.
- Cross-cutting minor cleanup for readability.

3. Some service modules are still broad despite package split.
- Files:
  - [`game/services/progression.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/progression.py)
  - [`game/services/jobs_listing.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/jobs_listing.py)
  - [`game/services/quest_builder/canvas.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/quest_builder/canvas.py)

## Suggested refactor order

1. Extract and slim `quest_builder_views.py` + shared response helpers.
2. Split `admin.py` into domain modules.
3. Split runtime `views.py` by domain and push validation/lookup logic down to services.
4. Decompose `services/combat.py` and retire legacy pending-attack compatibility.
5. Decompose `services/importers/domain.py` into domain-specific import modules.
6. Consolidate jobs shared helpers and tighten public service exports.
7. Template JS extraction and test suite modularization.
