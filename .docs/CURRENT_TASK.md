# Current Task

## What We're Building
Improving **core gameplay depth** and **narrative scale** by expanding the Property and Rival systems, while maintaining high-quality **authoring tools**.

## Status

### Done
- **Property & Turn System**: Implemented `Property`, `PlayerProperty`, `RivalClaim`. Turn logic runs on Quest Completion.
- **Quest Builder (Canvas)**: Graph-based UI for visual quest authoring with AJAX-powered scene/choice editing, drag-and-drop positioning, and per-scene panels for items, combat, and requirements.
- **Quest Builder — Hub Assignment**: `Quest.hub_scenes` M2M field links quests to hub scenes. Notice board filters by current hub scene. Validator warns when an unlocked quest has no hub scenes assigned.
- **Quest Builder — Validation**: `validate_quest()` detects orphan scenes, missing routing, duplicate keys, roll-scene misconfigurations, combat scenes without encounters, and ending scenes missing a hub-return choice.
- **Flag System**: `GameSession.flags` JSONField + `flags.py` service (`has_flag`, `set_flag`, `clear_flag`). Choices can `set_flag_name` / `clear_flag_name` on take.
- **Admin Polish**: `RequirementGroupInline` added to Scene and Choice admins; `ChoiceInline` expanded with routing fields.
- **Management Commands**: `scaffold_quest` and `export_quest` for content workflow.
- **UI Enhancements**: Item detail modals (`<dialog>`) and property turn summaries.

### In Progress
- **Property Upgrades**: Implementing logic for `upgrade_tier` affecting income/heat/rep.
- **Natural Key Support**: Adding `natural_key()` to core models to ensure `export_quest` fixtures are portable across databases.
- **Street Content Expansion**: Adding more contestable properties and associated resolution quests.

### Next
- **Heat Decay**: Turn-based heat reduction (planned in `PlayerStats` — `TODO` comment in model).
- **Passive vs Active Management**: Options to spend cash to lower heat or hire protection (to reduce rival contest chance).
- **Visual Polish**: Improved styling for the Quest Builder canvas and turn summary panel.

## Decisions Made
- **Admin-first authoring**: Scene keys still require manual `{quest_key}__{scene_slug}` prefixing for now, but `key_format_note` added to admin for guidance.
- **Quest Builder as primary tool**: The builder bypasses the traditional tabular admin for narrative design.
- **Turn Trigger**: Stick to Quest Completion for property processing to keep the game loop focused on missions.
- **Natural Keys**: Prioritize natural keys over a custom exporter to leverage Django's built-in serialization safely.
- **Hub filtering**: Notice board uses `Quest.hub_scenes` M2M rather than a single FK, so a quest can appear on multiple hub boards.