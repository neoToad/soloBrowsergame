# Current Task

## What We're Building
Improving **core gameplay depth** and **narrative scale** by expanding the Property and Rival systems, while maintaining high-quality **authoring tools**.

## Status

### Done
- **Property & Turn System**: Implemented `Property`, `PlayerProperty`, `RivalClaim`. Turn logic runs on Quest Completion.
- **Quest Builder (Canvas)**: Added a graph-based UI for visual quest authoring with AJAX-powered scene/choice editing.
- **Admin Polish**: `RequirementGroupInline` added to Scene and Choice admins; `ChoiceInline` expanded with routing fields.
- **Management Commands**: `scaffold_quest` and `export_quest` for content workflow.
- **UI Enhancements**: Item detail modals (`<dialog>`) and property turn summaries.

### In Progress
- quest builder
- **Property Upgrades**: Implementing logic for `upgrade_tier` affecting income/heat/rep.
- **Natural Key Support**: Adding `natural_key()` to core models to ensure `export_quest` fixtures are portable across databases.
- **Street Content Expansion**: Adding more contestable properties and associated resolution quests.

### Next
- **Heat Decay**: Implementing turn-based heat reduction (planned in `PlayerStats`).
- **Passive vs Active Management**: Options to spend cash to lower heat or hire protection (to reduce rival contest chance).
- **Visual Polish**: Improved styling for the Quest Builder canvas and turn summary panel.

## Decisions Made This Session
- **Admin-first authoring**: Scene keys still require manual `{quest_key}__{scene_slug}` prefixing for now, but `key_format_note` added to admin for guidance.
- **Quest Builder Integration**: The builder is now the primary way to manage complex quest flows, bypassing the traditional tabular admin for narrative design.
- **Turn Trigger**: Stick to Quest Completion for property processing to keep the game loop focused on missions.
- **Natural Keys**: Decided to prioritize natural keys over a custom exporter to leverage Django's built-in serialization safely.

