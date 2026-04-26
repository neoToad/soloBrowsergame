## Endpoint Response Contract

### Scope
- Gameplay endpoints in `game/views.py`
- Quest builder endpoints in `game/quest_builder_views.py`

### Success
- HTMX request: return HTML partial content that can be swapped directly.
- HTMX mutation with client event side-effects: set `HX-Trigger` with JSON payload.
- Non-HTMX request: redirect for normal gameplay navigation flows.

### Error
- Return `4xx` with structured HTML (never plain-text response bodies).
- HTMX gameplay errors render `templates/game/partials/scene_error.html`.
- HTMX quest-builder errors render `templates/admin/quest_builder/partials/inline_error.html`.
- Non-HTMX errors render HTML via `templates/game/error.html` (gameplay) or the quest-builder inline error template.

### Trigger Naming
- Keep legacy event names for compatibility:
  - `sceneUpdated`
  - `choiceCreated`
  - `choiceUpdated`
  - `choiceDeleted`
- Emit normalized aliases alongside legacy names:
  - `scene.updated`
  - `choice.created`
  - `choice.updated`
  - `choice.deleted`

