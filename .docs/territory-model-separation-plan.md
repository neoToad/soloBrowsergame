# Territory Model Separation Plan (Prompt-By-Prompt)

## Prompt 1: Add New Models and Keep Existing Behavior
Goal: Introduce dedicated territory models without breaking current gameplay.

- Add `Territory` model with fields equivalent to current territory-like `Property` fields:
  - `key`, `name`, `description`
  - `cash_per_turn`, `heat_per_turn`, `rep_per_turn`
  - `is_contestable`, `resolution_scene`
- Add `PlayerTerritory` model:
  - `session` FK to `GameSession`
  - `territory` FK to `Territory`
  - `is_contested` boolean
- Keep `Property` unchanged in this prompt to avoid immediate breakage.
- Register new models in admin.
- Add baseline model tests for create/query behavior.

Definition of done:
- Migrations run.
- New models appear in admin.
- Tests for model creation pass.

## Prompt 2: Add Scene Territory Arrival Fields
Goal: Make scene arrival effects explicitly support territories.

- In `Scene` (`game/models/world.py`), add:
  - `receive_territory` FK to `Territory` (nullable)
  - `lose_territory` FK to `Territory` (nullable)
- Keep existing `receive_property` and `lose_property`.
- Add `Scene.clean()` validation to prevent conflicting rewards/losses if needed:
  - e.g., disallow both `receive_property` and `receive_territory` simultaneously when that is not intended.
- Update admin `SceneAdmin` fieldsets/autocomplete fields to include territory fields.

Definition of done:
- Scene can store territory arrivals.
- Admin scene editor can author new fields.
- Validation rules covered by tests.

## Prompt 3: Data Migration from Property(type=territory)
Goal: Safely migrate existing territory data out of `Property`.

- Create data migration that:
  - Copies `Property` rows where `property_type="territory"` into `Territory`.
  - Copies owned rows from `PlayerProperty` into `PlayerTerritory` for those territory properties.
  - Maps `Scene.receive_property/lose_property` references (when they point to territory properties) into `Scene.receive_territory/lose_territory`.
- Keep legacy rows intact during this prompt (no deletions yet).
- Make migration idempotent and key-based where possible.

Definition of done:
- Existing DB data is represented in new tables.
- Scene references to territory effects are preserved.
- Migration test validates record counts and key mapping.

## Prompt 4: Service Refactor (Business Logic in Services)
Goal: Move runtime territory logic to dedicated territory paths.

- Update `game/services/session.py`:
  - Build `all_territories` from `Territory`.
  - Build `owned_territory_ids` from `PlayerTerritory`.
- Refactor property/territory reward handling:
  - Either extend `property_service.py` or add `territory_service.py`.
  - Ensure arrival rewards/losses apply both property and territory fields.
- Update contest/income logic:
  - Property loops operate on `PlayerProperty`.
  - Territory loops operate on `PlayerTerritory`.
- Keep views thin; no business logic in views.

Definition of done:
- Runtime behavior uses territory models directly.
- No direct territory logic depends on `Property.property_type` anymore.
- Service-layer tests pass.

## Prompt 5: Quest Builder and Admin Authoring Updates
Goal: Allow content authors to manage territories separately from properties.

- Update quest builder parser/mutations:
  - `receive_territory_id`, `lose_territory_id` form values.
  - Persist these to `Scene`.
- Update quest builder scene panel template:
  - Add territory dropdowns.
  - Keep property dropdowns for business/safehouse effects.
- Update session admin inlines to include `PlayerTerritory`.

Definition of done:
- Authors can assign territory rewards/losses in builder.
- Admin displays and edits territory ownership.

## Prompt 6: Importer and YAML Schema Split
Goal: Separate content import pipelines for properties and territories.

- In `yaml_files/world_data.yaml`:
  - Move territory entries from `properties:` to new `territories:` block.
- In `game/services/importers/domain.py`:
  - Import `properties` into `Property` only.
  - Import `territories` into `Territory`.
  - Resolve arrival fields for both property and territory keys.
- Update importer docs/comments.

Definition of done:
- Import succeeds with new schema.
- Territory content is created in `Territory`, not `Property`.

## Prompt 7: Cleanup Legacy Territory-in-Property Paths
Goal: Remove legacy territory coupling after migration and refactor are stable.

- Remove `territory` from `Property.PROPERTY_TYPES`.
- Add constraints/validation so new territory data cannot be created as `Property`.
- Optionally remove legacy territory `Property` rows after confirming no references remain.
- Update any lingering code paths that filter by `property_type="territory"`.

Definition of done:
- Territories are fully isolated from `Property` model usage.
- No production code depends on `Property.property_type == "territory"`.

## Prompt 8: Regression Test Sweep and Verification
Goal: Prove no gameplay regressions.

- Add/adjust tests for:
  - Territory rendering context (`all_territories`, `owned_territory_ids`)
  - Arrival rewards/losses for property and territory
  - Turn income/heat/rep behavior for owned territories
  - Contest flows for territories (if enabled)
  - Importer coverage for `territories:` schema
  - Data migration correctness
- Run focused test modules first, then broader suite.

Definition of done:
- All targeted tests pass.
- Critical gameplay loops involving ownership remain intact.

## Prompt 9: Rollout and Safety Checklist
Goal: Ship incrementally with low risk.

- Rollout order:
  1. Additive schema (new models + new scene fields)
  2. Data migration
  3. Dual-read/write where necessary
  4. Service switch to new territory models
  5. Importer/schema switch
  6. Legacy cleanup
- Verify at each stage:
  - Admin authoring works
  - Scene transitions and arrival effects work
  - No null reference issues in templates/services
- Keep a temporary compatibility window until post-migration verification is complete.

Definition of done:
- Incremental deploy path documented and executable.
- No hard cutover before data + behavior verification.
