# Unified YAML Export Plan (Hubs, Contacts, Enemies, World, Items)

## Goal
Implement exporter(s) that mirror the current YAML importer shape so authored content can round-trip cleanly for all content domains, not just quests.

## Current State
- Quest export exists and is canonicalized:
  - `game/management/commands/export_quest.py`
  - `game/services/quest_export.py`
- Importers already support these YAML roots via orchestrator type detection:
  - `items`
  - `enemies` / `contacts` (type: `enemies_contacts`)
  - `hubs`
  - `gangs` / `properties` / `territories` (type: `world`)
  - `quest`
- `yaml_files/` already uses split files by domain (e.g. `items.yaml`, `contacts.yaml`, `hubs/hubs.yaml`).

## Desired Output Contract
Add exports that follow the same schema currently accepted by `import_all` and `import_single_source`:

1. `items.yaml`
- root key: `items`

2. `enemies.yaml` and `contacts.yaml`
- either separate files (`enemies` and `contacts`) or combined (`enemies` + `contacts`)
- recommend separate by default to match current repo layout

3. `hubs/hubs.yaml`
- root key: `hubs`
- include same scene shape importer expects for hubs

4. `gangs.yaml`, `properties.yaml`, `territories.yaml`
- root keys: `gangs`, `properties`, `territories`
- recommend separate by default to match current repo layout

## Implementation Approach
Use the same pattern as quest export:
- one service module that builds payload dicts + renders YAML + computes default output paths
- management command wrappers that call those services
- deterministic ordering for stable diffs

### 1. Add domain export service
Create `game/services/domain_export.py` with:
- `build_items_payload() -> dict`
- `build_enemies_payload() -> dict`
- `build_contacts_payload() -> dict`
- `build_hubs_payload() -> dict`
- `build_gangs_payload() -> dict`
- `build_properties_payload() -> dict`
- `build_territories_payload() -> dict`
- `render_yaml(payload: dict) -> str` using `yaml.safe_dump(sort_keys=False, allow_unicode=False)`

Also add optional combined payload helpers for convenience:
- `build_enemies_contacts_payload()`
- `build_world_payload()`

### 2. Add export command(s)
Preferred: one new orchestration command plus optional focused commands.

Option A (recommended):
- Add `game/management/commands/export_all_yaml.py`
- flags:
  - `--types items,enemies,contacts,hubs,gangs,properties,territories`
  - `--out-dir yaml_files`
  - `--combined-world` (write one world file)
  - `--combined-enemies-contacts` (write one file)

Option B (extra ergonomic, optional):
- add focused commands:
  - `export_items`
  - `export_enemies_contacts`
  - `export_hubs`
  - `export_world`

### 3. Canonical ordering rules
Apply consistent ordering so exports are git-friendly:
- items/enemies/contacts/gangs/properties/territories by `key`
- hubs by `order`, then `key`
- hub choices by `order`, then `id`
- nested lists stable by DB id unless domain requires custom order

### 4. Hub payload completeness
For hubs, include fields importer currently reads:
- scene identity/type/body/order
- roll block
- arrival block
- `choices`
- `scene_items`
- `scene_contacts`

Ensure hub export includes newer arrival fields too:
- `receive_territory`
- `lose_territory`
- `discover_territory`
- `gang_standing_changes`

## File-Level Change Plan
1. Add service:
- `game/services/domain_export.py`

2. Add command:
- `game/management/commands/export_all_yaml.py`

3. (Optional) add small wrappers for focused commands:
- `game/management/commands/export_items.py`
- `game/management/commands/export_enemies_contacts.py`
- `game/management/commands/export_hubs.py`
- `game/management/commands/export_world.py`

4. Reuse existing quest exporter unchanged for quest files:
- `game/services/quest_export.py`
- `game/management/commands/export_quest.py`

## Test Plan
Add/extend tests in:
- `game/tests/test_export_quest.py` (keep as-is)
- new `game/tests/test_export_domain_yaml.py`

Test cases:
1. Export command writes expected files for selected types.
2. Payload root keys match importer detection (`items`, `hubs`, `enemies`, etc.).
3. Deterministic ordering (keys/order assertions).
4. Round-trip: export domain YAML -> run corresponding import command -> assert records exist and key relations resolve.
5. Hubs export/import round-trip includes arrival + scene items + contacts + gang standing changes.

## Rollout Sequence
1. Implement `domain_export.py` payload builders.
2. Implement `export_all_yaml` command writing split files by default.
3. Add tests for file creation + schema shape.
4. Add round-trip tests via existing import commands.
5. Run targeted tests and adjust field normalization if any import drift appears.

## Risks and Mitigations
- Risk: export schema drift from importer assumptions.
  - Mitigation: round-trip tests per type and strict key naming parity with importer code.
- Risk: unstable output ordering creates noisy diffs.
  - Mitigation: explicit `.order_by(...)` everywhere.
- Risk: hubs/scene relation gaps (missing optional blocks).
  - Mitigation: include empty lists/`null` defaults matching current quest export style.

## Acceptance Criteria
- A command can export YAML for hubs, contacts/enemies, world, and items using importer-compatible shapes.
- Exported YAML imports cleanly via existing import commands.
- Output is deterministic and matches current repository split-file conventions.
- Automated tests cover schema and round-trip behavior.
