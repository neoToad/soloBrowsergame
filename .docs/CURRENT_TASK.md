# Current Task

## What We're Building
Improving **core gameplay depth** and **narrative scale** by expanding the Job system with multi-stage progression (recon → contact → multi-beat execution), while maintaining high-quality **authoring tools**.

## Status

### Just Implemented (Latest)
- **Jobs Phase 2 - Full Service Layer**: Complete jobs service (`game/services/jobs.py`) with `JobRun` state machine:
  - Recon phase with tiered intellect-based access (low/mid/high tiers based on cunning thresholds: 0/7/12)
  - Multi-beat job execution (Beats 1-3) with approach selection and branching variants
  - Beat 1: Roll-based success → sets `approach_<key>` flags, tracks beat 2 penalty state
  - Beat 2: Branching on selected approach via `JobBeatVariant.approach` FK; optional roll with DC +2 penalty if failed Beat 1
  - Beat 3: Resolution phase applying rewards and cooldowns atomically
- **Reward Buckets**: Three-tier progression multipliers based on run count:
  - Runs 0-2 (learning): cash ×1.0, heat ×1.0, rep ×1.0
  - Runs 3-6 (familiar): cash ×1.15–1.25, heat ×0.9, rep ×1.2
  - Runs 7+ (veteran): cash ×1.30–1.45, heat ×0.80, rep ×1.0
- **Contact Job Offers**: `ContactJobOffer` model + state machine for contact-driven job delivery (always high-tier recon)
- **Cooldown System**: Per-job and per-contact cooldown tracking via `PlayerJobState`/`PlayerContactOfferState`
- **Milestone Flags**: Auto-trigger at runs 3, 5, 10 (`ran_<job_key>_<n>x`)
- **Full Test Coverage**: Comprehensive tests in `game/tests/test_jobs.py` covering recon tiers, beat resolution, rewards, cooldowns

### Done (Prior Work)
- **Two-Phase Combat**: Player attack resolves first (with roll widget); enemy counter-attack pre-rolled and stored on `CombatState`; player clicks "Brace yourself" to reveal enemy roll and apply damage. Enemy roll widget uses the same slot-machine animation as player rolls.
- **Property & Turn System**: Implemented `Property`, `PlayerProperty`, `RivalClaim`. Turn logic runs on Quest Completion.
- **Quest Builder (Canvas)**: Graph-based UI for visual quest authoring with AJAX-powered scene/choice editing, drag-and-drop positioning, and per-scene panels for items, combat, and requirements.
- **Quest Builder — Hub Assignment**: `Quest.hub_scenes` M2M field links quests to hub scenes. Notice board filters by current hub scene. Validator warns when an unlocked quest has no hub scenes assigned.
- **Quest Builder — Validation**: `validate_quest()` detects orphan scenes, missing routing, duplicate keys, roll-scene misconfigurations, combat scenes without encounters, and ending scenes missing a hub-return choice.
- **Flag System**: `GameSession.flags` JSONField + `flags.py` service (`has_flag`, `set_flag`, `clear_flag`). Choices can `set_flag_name` / `clear_flag_name` on take.
- **Admin Polish**: `RequirementGroupInline` added to Scene and Choice admins; `ChoiceInline` expanded with routing fields.
- **Management Commands**: `scaffold_quest` and `export_quest` for content workflow.
- **UI Enhancements**: Item detail modals (`<dialog>`) and property turn summaries.

### In Progress
- **Jobs Phase 3 — UI Components**: Building job board partials (recon targets, contact offers display) and job run panel with beat progression stepper.
- **Heat Decay**: Turn-based heat reduction (planned in `PlayerStats` — `TODO` comment in model).
- **Passive vs Active Management**: Options to spend cash to lower heat or hire protection (to reduce rival contest chance).
- **Visual Polish**: Improved styling for the Quest Builder canvas and turn summary panel.

### Next
- **Jobs Phase 4 — Hubs Importer**: Bulk populate jobs/contacts from `yaml_files/hubs/` (commit `ed8b527` "Hubs importer").
- **Audio Integration**: Voice lines for job beats via `game/models/audio.py`.
- **Job Reputation Mechanics**: Track standing changes per run.

## Decisions Made
- **Admin-first authoring**: Scene keys still require manual `{quest_key}__{scene_slug}` prefixing for now, but `key_format_note` added to admin for guidance.
- **Quest Builder as primary tool**: The builder bypasses the traditional tabular admin for narrative design.
- **Turn Trigger**: Stick to Quest Completion for property processing to keep the game loop focused on missions.
- **Natural Keys**: Prioritize natural keys over a custom exporter to leverage Django's built-in serialization safely.
- **Hub filtering**: Notice board uses `Quest.hub_scenes` M2M rather than a single FK, so a quest can appear on multiple hub boards.
- **Jobs as separate subsystem**: Job progression lives in its own state machine (`JobRun`) with explicit beat gates and cooldowns; rewards apply at Beat 3 completion only.
