# Current Task

## What We're Building
Improving **backend authoring UX** — making it faster and less error-prone to add new scenes and quests via the Django admin and management commands.

## Status

### Done
- Implemented an item detail modal using `<dialog>` in `templates/game/partials/inventory.html`.
- Added CSS for `dialog.item-modal` in `static/css/game.css` and backdrop closing in `base.html`.
- Verified item effects (healing, stat buffs) through the new UI.
- Created `Property`, `PlayerProperty`, and `RivalClaim` models.
- Implemented `property_service.py` to handle turn income, heat-based rival contest rolls, and contest resolution logic.
- Integrated property turns into `choice_resolve` (triggered by quest completion).
- Added `turn_summary.html` partial to display income and active threats after a quest.
- Added Property management to the Django admin.

### In Progress
- **Admin polish** (`game/admin.py`):
  - `prepopulated_fields` + fieldsets on `SceneAdmin`
  - Expand `ChoiceInline` to include `success_scene`, `failure_scene`, `requires_roll`
  - Fieldsets + routing description on `ChoiceAdmin`
  - `RequirementGroupInline` on Scene and Choice (eliminates the 4-step requirements detour)
- **Management commands**:
  - `scaffold_quest <key> <title>` — creates stub quest with entrance + victory/defeat endings
  - `export_quest <key>` — dumps a quest and all related objects to a loadable fixture

### Next
- Implement property upgrade tiers (increasing income or reducing heat more effectively).
- Add "Passive" vs "Active" property management (e.g., paying a bribe to lower heat immediately).
- Visual polish for the turn summary modal/panel.
- Expand "street" content to include more contestable properties.

## Decisions Made This Session
- **Turn Trigger**: Property income and rival checks fire only on **Quest Completion** (not every scene) to prevent resource bloat and keep questing as the primary driver of time.
- **Heat as Risk**: Heat acts as a linear probability modifier for rival contests, creating a natural "push your luck" mechanic.
- **Scene-Based Resolution**: Rival contests are resolved via standard game scenes/quests, reusing existing engine mechanics for "Victory" and "Defeat" endings.
- **Native Dialogs**: Continued use of `<dialog>` for the new turn summary to maintain UI consistency with the inventory modal.
- **Admin-first authoring**: Scene keys still need the `{quest_key}__{scene_slug}` prefix typed manually for now; `prepopulated_fields` fills the slug portion only. The convention is documented via help_text on the key field.

