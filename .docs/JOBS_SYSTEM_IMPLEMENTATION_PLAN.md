# Jobs System Implementation Plan

## Goal
Implement a replayable Jobs system (separate from fixed narrative quests) with:
- district recon entry,
- contact-offered jobs,
- 4-beat job flow,
- recon tiers driven by effective Cunning,
- run-scaling rewards,
- cooldowns and persistent job/contact flags,
- HTMX UI integration in hub/scene flow.

Architecture constraint: all gameplay/business logic must live in services; views only orchestrate request/response.

## Implementation Strategy
Build this in vertical slices so each step is testable and does not destabilize existing quest gameplay.

1. Add data model + migrations for jobs, runs, cooldowns, contact offers.
2. Build `game/services/jobs.py` as the single rules engine.
3. Add recon/contact entry endpoints and templates.
4. Add beat progression endpoints and reward/cooldown application.
5. Integrate notice-board-style rendering for district targets and contacts.
6. Seed initial jobs/contacts and add regression + rules tests.

## Slice Plan

### Slice 1: Data Model + Admin Wiring
Deliverables:
- New models in `game/models/jobs.py` (or `world.py` if you prefer existing pattern consistency):
  - `Job`
  - `JobApproach`
  - `JobBeatVariant`
  - `JobRun`
  - `PlayerJobState` (run_count, cooldown_until_turn)
  - `ContactJobOffer` (contact-specific gating/cooldown)
- `GameSession.turn_counter` integer field (for cooldown math).
- Model/admin registration and migration.

Rules encoded at model level:
- Job base cooldown in turns.
- Recon tier thresholds (0/7/12) as constants.
- Contact offer cooldown independent from base job cooldown.
- Optional requirement groups or flag gates for unlocks.

Acceptance checks:
- Migrations apply cleanly.
- Admin can create jobs with approaches + beat variants + contact offers.

### Slice 2: Jobs Service Layer
Create `game/services/jobs.py` with pure gameplay logic:
- `get_recon_tier(effective_stats) -> low|mid|high`
- `get_recon_modifiers(tier)`
- `list_district_targets(session, scene, ctx)`
- `list_contact_offers(session, scene, ctx)`
- `start_recon(session, job)`
- `commit_recon(session, job)`
- `start_contact_job(session, contact_offer)`
- `resolve_beat_1(session, run, approach)`
- `resolve_beat_2(session, run, action)`
- `resolve_beat_3(session, run)`
- `apply_job_rewards(session, run)`
- `apply_job_cooldowns(session, run)`
- `increment_turn(session)`

Rules to implement in services:
- Contact intel always uses high-tier recon modifiers.
- Beat 1 failure sets `approach_{path}_failed` and Beat 2 penalty flag.
- Beat 2 branch selected by Beat 1 approach flag.
- Run milestones set `ran_{job_slug}_{n}x` for 3/5/10.
- Completion sets cooldowns and increments run counts.

Acceptance checks:
- Unit tests cover tiering, payouts, cooldown gate logic, flag setting.

### Slice 3: HTTP Endpoints + HTMX Flow
Add routes + thin views:
- `POST /game/jobs/recon/<job_key>/`
- `POST /game/jobs/recon/<job_key>/commit/`
- `POST /game/jobs/recon/<job_key>/walk-away/`
- `POST /game/jobs/contact/<offer_id>/start/`
- `POST /game/jobs/run/<run_id>/beat1/`
- `POST /game/jobs/run/<run_id>/beat2/`
- `POST /game/jobs/run/<run_id>/abort/`
- `POST /game/jobs/run/<run_id>/resolve/`

View responsibilities only:
- load session/context,
- call jobs service,
- flush logs,
- render HTMX partial response.

Acceptance checks:
- End-to-end playthrough works fully via HTMX without full-page reload.

### Slice 4: UI/Template Integration
Update templates:
- `templates/game/partials/scene_panel.html`
- New partials:
  - `game/partials/jobs_board.html`
  - `game/partials/job_recon_modal.html` (or inline panel)
  - `game/partials/job_run_panel.html`
  - `game/partials/contact_offers.html`

UI behavior:
- District hubs show caseable job targets.
- Cooldown targets remain visible with turns remaining.
- Contact panels show first-meet intro / standard offer / nothing-available state.
- Beat 0 omitted for contact starts.

Acceptance checks:
- Recon choices vary by tier.
- Cooldown messaging visible and accurate.

### Slice 5: Reward Curves + Balancing Constants
Implement explicit reward policy constants in service:
- Run 0-2: base cash/heat/rep.
- Run 3-6: cash +15-25%, heat -10%, rep +20%.
- Run 7+: cash +30-45%, heat -20%, rep back to base.
- Final cash = selected reward range * recon payout modifier.

Acceptance checks:
- Deterministic tests for payout/heat/rep values across run buckets.

### Slice 6: Content Seeding
Add fixtures (or data migration) for initial templates:
- Store robbery
- Protection racket
- Courier run
- Debt collection

And contact roster:
- Pawn shop owner
- Carla the fence
- Mickey Two-Fingers
- Court clerk
- Dock foreman

Acceptance checks:
- Fresh DB load exposes expected district jobs and unlock progression.

### Slice 7: Regression + Integration Tests
Add tests in `game/tests/`:
- Model tests for gating/cooldowns.
- Service tests for beat branching and flags.
- View tests for HTMX endpoint responses.
- Integration test for full replay loop:
  - recon -> beat1 -> beat2 -> beat3 -> cooldown -> replay.
- Integration test for contact unlock + independent cooldown.

Acceptance checks:
- `python manage.py test` passes with new jobs suite.

## Recommended File Targets
- `game/models/jobs.py` (new)
- `game/models/__init__.py`
- `game/admin.py`
- `game/services/jobs.py` (new)
- `game/services/session.py` (turn counter integration)
- `game/views.py`
- `game/urls.py`
- `templates/game/partials/*.html` (jobs partials)
- `game/tests/test_jobs.py` (new)
- `game/fixtures/*.json` or migration-based seed

## Implementation Prompts
Use these prompts sequentially in separate coding passes.

### Prompt 1: Data Model Pass DONE
"Implement Slice 1 from `.docs/JOBS_SYSTEM_IMPLEMENTATION_PLAN.md`.
Create first-class job models and migrations, including session turn counter support.
Keep all business logic out of views. Register admin screens for authoring jobs, approaches, beat variants, and contact offers.
Return:
1. files changed,
2. migration names,
3. any schema tradeoffs made."

### Prompt 2: Jobs Service Engine Pass Done
"Implement Slice 2.
Create `game/services/jobs.py` containing all rules for recon tiering, beat progression, flags, reward scaling, and cooldown handling.
Use existing flag service (`game/services/flags.py`) and effective stat conventions.
Add focused service tests for tier thresholds, flag writes, branching, and cooldown calculations.
Return:
1. service API added,
2. tests added,
3. any TODOs left."

### Prompt 3: Views + URLs Pass
"Implement Slice 3.
Add job endpoints and thin views that delegate to jobs services only.
Preserve existing quest/combat behavior.
Ensure HTMX responses use existing `_htmx_response()` and render context conventions.
Add view tests for happy-path and permission/gating failures.
Return:
1. routes added,
2. endpoint contract summary,
3. test results."

### Prompt 4: Template/UI Pass
"Implement Slice 4.
Add jobs partial templates and integrate them into scene panel rendering for hub scenes.
Show recon, commit/walk-away, contact offers, and cooldown visibility.
Do not introduce JS frameworks; HTMX + server-rendered templates only.
Return:
1. template files added/updated,
2. context keys required,
3. screenshots or textual render checks."

### Prompt 5: Rewards/Balancing Pass
"Implement Slice 5.
Centralize reward scaling constants in jobs service.
Apply run-bucket and recon-modifier payout math exactly as documented.
Add deterministic tests proving payout/heat/rep behavior at run counts 0, 3, 7.
Return:
1. formulas implemented,
2. test cases,
3. balancing assumptions."

### Prompt 6: Seed Content Pass
"Implement Slice 6.
Seed initial jobs and contacts from the Jobs spec (store robbery, protection racket, courier run, debt collection + contact roster).
Prefer fixtures consistent with existing project patterns.
Return:
1. seed files changed,
2. exact keys/slugs created,
3. manual verification steps."

### Prompt 7: Full Test + Hardening Pass
"Implement Slice 7.
Add end-to-end replayability coverage and contact unlock/cooldown integration tests.
Run full test suite and fix regressions.
Return:
1. test summary,
2. unresolved risks,
3. follow-up cleanup suggestions."

## Open Design Decisions (Resolve Early)
- Whether jobs should reuse `Scene` graph objects for beats, or use dedicated `JobBeat*` models. ** JobBeat*
- Whether cooldowns tick only on scene transitions or on any meaningful action. **Meaningful Action
- Whether contact unlock requirements should reuse existing `RequirementGroup` models directly. ** REUSE

Recommended defaults:
- Use dedicated job models (clear separation from authored quests).
- Tick cooldown by `GameSession.turn_counter` on each successful player choice resolution.
- Reuse `RequirementGroup` where possible to minimize new gating DSL.
