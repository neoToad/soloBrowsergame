# Tech Debt Register

## Scope
Inventory of shortcuts, workarounds, missing features, and scaling risks observed in the current codebase.

## Active debt

### High

1. Legacy allowance path remains in flag validation for existing rows.
- Files:
  - [`game/models/world.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/world.py)
  - [`game/services/flag_registry.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/flag_registry.py)
- Evidence:
  - `Choice.clean()` passes prior persisted values as `legacy_values` into `validate_flag_name(...)`.
- Risk:
  - Keeps transitional invalid historical states alive and weakens strict registry invariants.

2. Compatibility event contract still emits dual legacy + normalized trigger names.
- Files:
  - [`.docs/ENDPOINT_RESPONSE_CONTRACT.md`](/C:/Users/colin/PycharmProjects/soloBrowserGame/.docs/ENDPOINT_RESPONSE_CONTRACT.md)
  - [`game/quest_builder_views/scenes.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views/scenes.py)
  - [`game/quest_builder_views/choices.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views/choices.py)
- Risk:
  - Dual naming (`sceneUpdated` + `scene.updated`, etc.) increases long-term backend/frontend contract complexity.

3. Import orchestration still depends on key-based detection and centralized dispatch.
- Files:
  - [`game/services/importers/orchestrator.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/importers/orchestrator.py)
- Evidence:
  - `detect_import_type(...)` infers domain from top-level YAML keys.
  - `IMPORT_HANDLERS` central map controls per-domain execution.
- Risk:
  - Ambiguous or malformed content can route to unexpected import paths; behavior remains stringly/config-shaped.

### Medium

1. Heat-decay gameplay rule is still deferred.
- File:
  - [`game/models/player.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/player.py)
- Evidence:
  - Inline TODO explicitly says planned per-turn heat decay is not implemented.
- Risk:
  - Balance/economy behavior can drift from intended design.

2. Context assembly remains dense and cross-domain.
- File:
  - [`game/services/session.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/session.py)
- Risk:
  - New panel/features can impact unrelated rendering paths and expand coupling.

3. Hand-rolled POST row parsing still exists in quest builder endpoints.
- File:
  - [`game/quest_builder_views/scenes.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/quest_builder_views/scenes.py)
- Evidence:
  - `scene_gang_standings_save` manually loops `gang_id_<n>`/`standing_change_<n>` keys.
- Risk:
  - Input-shape bugs and inconsistent parsing behavior versus shared parser helpers.

### Operability / hygiene

1. Generated `__pycache__` artifacts are present in the repository tree.
- Paths:
  - Multiple `__pycache__` directories under `core/` and `game/**`.
- Risk:
  - Repo noise and accidental stale artifact commits.

2. Encoding/mojibake artifacts remain in user-facing strings/comments.
- Files seen with artifacts:
  - [`game/models/player.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/models/player.py)
  - [`game/services/combat.py`](/C:/Users/colin/PycharmProjects/soloBrowserGame/game/services/combat.py)
- Risk:
  - Text quality issues and possible rendering inconsistencies.

1