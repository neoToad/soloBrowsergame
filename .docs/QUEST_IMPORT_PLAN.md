# Quest YAML Import — Implementation Plan

**Target file:** `game/management/commands/import_quest.py`
**Run with:** `python manage.py import_quest quests/the-call.yaml`
**Reference:** `.docs/QUEST_YAML_IMPORT.md`

---




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