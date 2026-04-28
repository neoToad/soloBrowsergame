# Tech Debt Register

## Scope
Inventory of shortcuts, workarounds, missing features, and scaling risks observed in the current codebase. No code changes were made.

## Critical debt (likely to hurt as codebase grows)

1. Monolithic view/controller surfaces increase change risk and regression probability.
- Files:
  - [`game/quest_builder_views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views.py)
  - [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py)
- Risk:
  - High coupling across unrelated endpoints; small edits can break multiple flows.
  - Hard to enforce architecture rule “business logic in services only” consistently.

2. Monolithic admin module with mixed concerns.
- File: [`game/admin.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/admin.py)
- Risk:
  - Registration, inlines, and custom route wiring are all centralized; maintenance cost and review complexity will rise sharply.

3. Combat service still carries migration-era compatibility logic.
- Files:
  - [`game/services/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/combat.py)
  - [`game/models/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/combat.py)
- Evidence:
  - Legacy pending attack fallback (`pending_enemy_attack` JSON compatibility path).
- Risk:
  - Dual-path behavior complicates debugging and correctness, especially around state transitions.

4. Import pipeline is broad and procedural with stringly-typed dispatch.
- Files:
  - [`game/services/importers/domain.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/domain.py)
  - [`game/services/importers/orchestrator.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/orchestrator.py)
- Risk:
  - Easier to introduce partial-import bugs and harder to reason about rollback/error boundaries as content grows.

## High debt (important to address soon)

1. Legacy allowance code embedded in model validation.
- Files:
  - [`game/models/world.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/world.py)
  - [`game/models/jobs.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/jobs.py)
  - [`game/services/flag_registry.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/flag_registry.py)
- Risk:
  - Accepting legacy values can keep invalid historical states alive and complicate future invariants.

2. Public API leaks private internals in jobs service aggregator.
- File: [`game/services/jobs.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/jobs.py)
- Evidence:
  - `__all__` exports underscore-prefixed internals (`_roll_check`, `_tier_rank`, etc.).
- Risk:
  - Internal implementation details become de facto public contracts.

3. Duplicated recon-tier text and mapping logic.
- Files:
  - [`game/services/jobs_lifecycle.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/jobs_lifecycle.py)
  - [`game/services/jobs_listing.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/jobs_listing.py)
- Risk:
  - Drift between duplicate helpers and inconsistent behavior over time.

4. Repeated inline error/trigger response boilerplate in quest builder endpoints.
- File: [`game/quest_builder_views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views.py)
- Risk:
  - Inconsistent status/messages/trigger payloads across endpoints.

## Missing features / unfinished behavior

1. Heat-decay gameplay rule explicitly deferred.
- File: [`game/models/player.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/player.py)
- Evidence:
  - TODO comment indicates planned heat decay not implemented.
- Risk:
  - Economy/heat progression balance may diverge from design intent.

2. Compatibility alias/event-contract burden still active.
- Files:
  - [`.docs/ENDPOINT_RESPONSE_CONTRACT.md`](/C:/Users/colin/PycharmProjects/soloBrowserGame/.docs/ENDPOINT_RESPONSE_CONTRACT.md)
  - [`game/quest_builder_views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views.py)
- Risk:
  - Dual event naming (`legacy + normalized`) increases long-term frontend/backend contract complexity.

## Scaling/operability debt

1. Large fixture-driven content with import/export-heavy workflows but limited modularization.
- Files:
  - [`game/fixtures/scene.json`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/fixtures/scene.json)
  - [`game/fixtures/choice.json`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/fixtures/choice.json)
- Risk:
  - Content maintenance and merge conflicts worsen as narrative size grows.

2. Tests are concentrated in very large modules.
- Files:
  - [`game/tests/test_jobs_views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_jobs_views.py)
  - [`game/tests/test_navigation.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_navigation.py)
  - [`game/tests/test_combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_combat.py)
- Risk:
  - Slower authoring/review cycles and harder pinpointing of behavioral regressions.

3. Generated artifacts appear in repository tree (`__pycache__`).
- Path examples under `game/**/__pycache__/...`
- Risk:
  - Repository noise, larger diffs, accidental stale artifact commits.

4. Encoding/mojibake artifacts in source text/comments.
- Files seen with artifacts:
  - [`game/admin.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/admin.py)
  - [`game/services/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/combat.py)
  - [`game/models/player.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/player.py)
- Risk:
  - UI text quality issues and potential serialization/render inconsistencies.

## Maintainability debt patterns

1. Service functions often return loosely structured dictionaries rather than typed return objects.
- Files:
  - [`game/services/jobs_lifecycle.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/jobs_lifecycle.py)
  - [`game/services/jobs_listing.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/jobs_listing.py)
- Risk:
  - Contract drift and key-name breakage during refactors.

2. Context assembly is dense and cross-domain.
- File: [`game/services/session.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/session.py)
- Risk:
  - Any new panel/feature can impact unrelated rendering paths.

3. Request parsing loops hand-coded in multiple endpoints.
- File: [`game/quest_builder_views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views.py)
- Risk:
  - Input-shape bugs and duplicated parsing quirks.

## Debt from transitional migration support

1. Legacy gate/flag migration history remains embedded in runtime assumptions.
- Files:
  - [`game/migrations/0006_migrate_legacy_gates.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/migrations/0006_migrate_legacy_gates.py)
  - [`game/migrations/0007_remove_legacy_gate_fields.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/migrations/0007_remove_legacy_gate_fields.py)
  - [`game/migrations/0008_replace_scene_flags.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/migrations/0008_replace_scene_flags.py)
  - Runtime legacy hooks in model/service code listed above.
- Risk:
  - Transitional behavior becoming permanent and obscuring true domain rules.

## Suggested prioritization

1. Break up `quest_builder_views.py`, `views.py`, and `admin.py` (largest maintenance and coupling win).
2. Retire combat legacy pending-attack fallback once migration cutoff is confirmed.
3. Split importer domain module and formalize typed handler registry.
4. Consolidate duplicated jobs helpers and tighten service public API.
5. Clean repository hygiene (`__pycache__`, encoding normalization) and enforce via CI checks.
6. Track and implement deferred gameplay rule (heat decay) with explicit design/tests.
