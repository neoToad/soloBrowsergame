# Test Audit: Coverage Gaps, Incorrect Tests, and Improvement Opportunities

## Scope
Reviewed test suite under `game/tests/` and compared it against core runtime paths in views/services/importers.

## High-priority gaps (missing coverage)

1. Uncovered non-HTMX branches in many views
- Evidence: [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:60), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:62), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:117), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:139), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:352), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:371)
- Most endpoint tests call HTMX (`HTTP_HX_REQUEST=true`), so redirect/full-page behaviors are mostly untested.
- Missing checks: redirect targets, no-HTMX error rendering, and `HX-Push-Url` behavior consistency.
- Note: combat endpoints at [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:300), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:313), and [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:326) currently share the same HTMX response path regardless of request headers.

2. Large missing branch coverage in job endpoints
- Evidence: method guards and validation branches are untested in [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:144), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:177), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:190), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:207), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:217), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:232), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:253), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:270)
- Current tests cover many happy paths, but not `405` behavior for non-POST requests, invalid approach key for beat 1, or abort path assertions.

3. Combat gameplay service error branches not directly covered
- Evidence: [`game/services/gameplay/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/gameplay/combat.py:23), [`game/services/gameplay/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/gameplay/combat.py:29), [`game/services/gameplay/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/gameplay/combat.py:41), [`game/services/gameplay/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/gameplay/combat.py:45), [`game/services/gameplay/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/gameplay/combat.py:63), [`game/services/gameplay/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/gameplay/combat.py:65), [`game/services/gameplay/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/gameplay/combat.py:73)
- Missing cases: no active combat state, inactive combat state, no pending enemy attack, no pending victory, missing encounter for continue.

4. Importer domain edge/failure paths under-tested
- Evidence: uncovered input-validation and warning paths in [`game/services/importers/domain.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/domain.py:33), [`game/services/importers/domain.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/domain.py:97), [`game/services/importers/domain.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/domain.py:159), [`game/services/importers/domain.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/domain.py:173), [`game/services/importers/domain.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/domain.py:190), [`game/services/importers/domain.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/domain.py:203)
- Missing cases: invalid item payloads through `import_items_data`, property-key auto-slug warning assertion, scene item/contact deletion+recreate behavior, missing enemy warning for combat encounter import.

5. Progression reward logging branches not fully exercised
- Evidence: [`game/services/progression.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/progression.py:67), [`game/services/progression.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/progression.py:73), [`game/services/progression.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/progression.py:79), [`game/services/progression.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/progression.py:121)
- Missing cases: `apply_stat_rewards` positive/negative formatting and heat floor behavior, fallback level-up flavor path in `maybe_complete_quest` (`LEVEL_UP_FLAVOR.get(..., default)`).

6. Response helpers are partially untested
- Evidence: [`game/presentation/responses.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/presentation/responses.py:33), [`game/presentation/responses.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/presentation/responses.py:41), [`game/presentation/responses.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/presentation/responses.py:56), [`game/presentation/responses.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/presentation/responses.py:69)
- Missing cases: `redirect_or_htmx` in both modes, `error_response` context merge path, `empty_response` trigger attachment.

## Incorrect or misleading tests

1. Misnamed test claims quest completion but does not assert it
- Evidence: [`test_combat_victory_and_quest_completion`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_combat.py:47)
- It validates scene transition after `combat_continue`, but does not assert `CompletedQuest` creation or XP/events. Name overstates coverage.

2. Session-isolation test checks only status code
- Evidence: [`test_job_run_beat_1_for_run_from_other_session_returns_403`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/tests/test_jobs_views.py:128)
- It should also assert no mutation on foreign `JobRun` and no changes to current session log/state. Current assertion can miss side effects.

## Tests that should be improved

1. Add method-guard tests for every POST-only endpoint
- Targets: [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:99), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:122), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:143), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:159), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:176), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:188), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:205), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:230), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:251), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:268), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:291), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:304), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:317), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:330), [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py:356)

2. Add non-HTMX integration tests for key flows
- Choice resolve, start quest, combat actions, level-up, use-item, and job endpoints should verify redirect vs fragment behavior and full-page error templates.

3. Strengthen assertions for side effects, not only response status
- Job and combat view tests should assert turn counters, run status transitions, event log entries, and absence of unintended cross-session writes.

4. Add direct unit tests for helper functions currently covered indirectly
- `response_utils.redirect_or_htmx`, `response_utils.empty_response`, and combat gameplay guard helpers are currently validated mostly via broader integration tests.

## Coverage-driven candidates (from existing coverage artifact)

1. Biggest practical gaps by file include:
- [`game/views.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/views.py)
- [`game/services/importers/domain.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/domain.py)
- [`game/services/gameplay/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/gameplay/combat.py)
- [`game/services/progression.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/progression.py)
- [`game/presentation/responses.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/presentation/responses.py)

## Notes
- I did not modify code or tests.
- This report is based on current repository tests plus `coverage.json` branch/line evidence.
