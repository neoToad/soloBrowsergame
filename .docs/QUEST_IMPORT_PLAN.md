# Quest YAML Import — Implementation Plan

**Target file:** `game/management/commands/import_quest.py`
**Run with:** `python manage.py import_quest quests/the-call.yaml`
**Reference:** `.docs/QUEST_YAML_IMPORT.md`

---

## Prompt 1 — Scaffold + Quest + Scene base records

Create `game/management/commands/import_quest.py`.

### What to implement:
- `Command.handle()` reads the YAML path argument, loads the file with `yaml.safe_load`, wraps everything in `transaction.atomic`.
- **Step 1 – Quest:** `update_or_create` keyed on `key`. Set `title`, `description`, `is_repeatable`, `arc_order`. If `arc` is non-null, look up `Arc.objects.get(key=...)`. Leave `entrance_scene=None` and requirements/M2M empty for now.
- **Step 2 – Scenes (pass 1):** Iterate `data['scenes']`. For each, `update_or_create` keyed on `key`. Set all scalar fields: `scene_type`, `title`, `body`, `order`, `requires_roll`, `roll_stat` (empty string if null), `roll_difficulty` (default 10 if null), `ending_type` (empty string if null), `cash_change`, `rep_change`, `heat_change`. Leave all FK fields (`consume_item`, `receive_property`, `lose_property`) as `None` for now. Collect results into `scene_map: dict[str, Scene]`.
- **Step 3 – entrance_scene:** After all scenes exist, resolve `quest.entrance_scene = scene_map[data['quest']['entrance_scene']]` and `quest.save()`.
- Print a summary line per step using `self.stdout.write`.

### Notes:
- `roll_stat`: YAML uses `null` when no roll — store as `""` (blank) in DB.
- `ending_type`: YAML uses `null` when no ending — store as `""`.
- `roll_difficulty`: YAML sends `null` when unused — store as `10` (model default).

---

## Prompt 2 — Choices

Add a `_import_choices(scene_data, scene_obj, scene_map)` helper and call it in `handle()` after all scenes exist.

### What to implement:
- For each choice dict in `scene_data['choices']`, `update_or_create` keyed on `(scene=scene_obj, label=..., order=...)`.
- Set `arrival_flavor`, `failure_arrival_flavor` (empty string if null), `set_flag_name`, `clear_flag_name` (empty string if null).
- Resolve FKs: `target_scene`, `success_scene`, `failure_scene` — look up from `scene_map` if non-null, else `None`. These keys may point to hub scenes not in this YAML (e.g. `hub__apartment`), so fall back to `Scene.objects.get(key=...)` if not in scene_map.
- Requirements left empty for now (`choice.requirements.clear()` — handled in Prompt 3).

---

## Prompt 3 — Requirements (Quest + Choice)

Add `_import_requirement_groups(groups_data)` helper that returns a list of saved `RequirementGroup` instances.

### What to implement:
- For each group dict, `get_or_create` a `RequirementGroup` by `label`. Set `logic`. Then for each condition in `conditions`:
  - `create` (or reuse) a `Requirement` — set `condition_type`, `flag_name`, `stat_name`, `stat_value`.
  - FK lookups: `required_item` → `Item.objects.get(key=...)`, `required_quest` → `Quest.objects.get(key=...)`, `required_contact` → `Contact.objects.get(key=...)`. Each is null if the YAML field is null.
  - `group.requirements.add(req)`.
- Return list of groups.
- After choices are created: iterate scenes → iterate choices → call helper → `choice.requirements.set(groups)`.
- For quest requirements: call helper → `quest.requirements.set(groups)`.

### Notes:
- Requirements are re-created cleanly each import run: clear the group's `requirements` M2M before re-adding, so re-runs don't duplicate conditions.

---

## Prompt 4 — SceneItems, SceneContacts, CombatEncounters + M2M finalisation

Three helpers + M2M wiring, all called from `handle()`.

### SceneItems:
- `_import_scene_items(scene_data, scene_obj)`: delete existing `SceneItem` rows for the scene, then create fresh ones. Look up `Item.objects.get(key=scene_item['item'])`. Set `quantity`, `award_once`.

### SceneContacts:
- `_import_scene_contacts(scene_data, scene_obj)`: delete existing `SceneContact` rows for the scene, then create fresh. Look up `Contact.objects.get(key=...)`. Set `action`, `award_once`.

### CombatEncounters:
- `_import_combat_encounter(scene_data, scene_obj, scene_map)`: only runs when `scene_data['scene_type'] == 'combat'`. Uses `update_or_create(scene=scene_obj)`. Look up `Enemy.objects.get(key=...)`. Resolve `victory_scene` and `defeat_scene` from `scene_map` (with `Scene.objects.get` fallback for cross-quest keys).

### M2M finalisation:
- `quest.scenes.set(scene_map.values())` — all scenes created for this quest.
- `quest.hub_scenes.set(Scene.objects.filter(key__in=data['quest']['hub_scenes']))` — hub scenes already exist in DB.

---

## Import order summary (matches spec)

| Step | Prompt |
|------|--------|
| 1. Quest record | 1 |
| 2. All Scene records (scalars only) | 1 |
| 3. Quest.entrance_scene resolved | 1 |
| 4. All Choice records | 2 |
| 5. RequirementGroups + Requirements | 3 |
| 6. SceneItem records | 4 |
| 7. SceneContact records | 4 |
| 8. CombatEncounter records | 4 |
| 9. Quest.scenes M2M | 4 |
| 10. Quest.hub_scenes M2M | 4 |