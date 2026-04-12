# Current Task

## What We're Building
Improving the inventory system by adding an item detail modal using the HTML5 `<dialog>` element to provide clearer descriptions and usage feedback.

## Status

### Done
- Implemented an item detail modal using `<dialog>` in `templates/game/partials/inventory.html`.
- Added CSS for `dialog.item-modal`, including styling for backdrop, headers, and footer in `static/css/game.css`.
- Added a global click listener in `base.html` to close any open `<dialog>` when clicking the backdrop.
- Integrated HTMX in the item modal 'USE' button to trigger item effects and close the modal on success.
- Updated the inventory layout to use a vertical list of buttons (`item-list` and `item-name-btn`).
- Expanded `game/fixtures/items.json` with clearer descriptions and property definitions (active effects, passive bonuses, and consumables).

### In Progress
- Verification of item effects (healing, stat buffs) through the new UI.

### Next
- Add visual feedback for passive stat bonuses in the mobile stats bar.
- Refine the 'USE' button state for non-usable items or items with requirements.
- Tech Debt
- Property System
- Flag System
- 

## Decisions Made This Session
- Used native HTML5 `<dialog>` for modals instead of custom absolute-positioned `div`s to simplify backdrop handling and accessibility.
- Implemented backdrop closing via a global event listener on `body` in `base.html` for a consistent UX.
- Used HTMX's `hx-on::after-request` inside the modal to ensure the dialog closes only after a successful item usage request.

