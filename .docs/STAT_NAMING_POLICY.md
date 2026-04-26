## Stat Naming Policy

### Canonical Internal Names
- Use DB field names everywhere in code paths, API payloads, fixtures, and requirements:
  - `strength`
  - `agility`
  - `intellect`
  - `charisma`

### Display Labels
- Use display labels only for player-facing text/UI copy:
  - `muscle`
  - `reflexes`
  - `cunning`
  - `nerve`

### Rules
- Services and views must accept canonical DB names for stat mutations and checks.
- Templates may render display labels but must post canonical DB names in request payloads.
- Authoring/import content (`roll_stat`, `stat_name`) must use canonical DB names.

