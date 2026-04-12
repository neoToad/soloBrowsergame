# Current Task

## What We're Building
Implementing a **Property System** to add passive progression, resource management (cash, heat, rep), and risk-reward gameplay via rival contests triggered by high "Heat".

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
- Balancing heat-to-contest ratios (currently 1/200 chance per point of heat).
- Testing rival claim resolution scenes (Victory vs. Defeat outcomes).
- Ensuring UI feedback for newly unlocked resolution scenes is prominent enough.

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

