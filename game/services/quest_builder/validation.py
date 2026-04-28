from ...models.combat import CombatEncounter
from ...models.world import Choice, Quest, Scene


class QuestValidator:
    def __init__(self, quest_id):
        self.quest = Quest.objects.get(pk=quest_id)
        scenes_qs = self.quest.scenes.only("id", "key", "title", "scene_type", "requires_roll")
        self.scenes = list(scenes_qs)
        scene_ids = [s.id for s in self.scenes]
        self.scene_id_set = set(scene_ids)
        self.entry_scene_id = self.quest.entrance_scene_id

        choices_qs = Choice.objects.filter(scene_id__in=scene_ids).only(
            "id", "scene_id", "label", "target_scene_id", "success_scene_id", "failure_scene_id"
        )
        self.choices = list(choices_qs)

        external_target_ids = set()
        for c in self.choices:
            for tid in (c.target_scene_id, c.success_scene_id, c.failure_scene_id):
                if tid and tid not in self.scene_id_set:
                    external_target_ids.add(tid)
        self.external_scene_types: dict[int, str] = {}
        if external_target_ids:
            self.external_scene_types = {
                s.id: s.scene_type
                for s in Scene.objects.filter(pk__in=external_target_ids).only("id", "scene_type")
            }

        encounters_qs = CombatEncounter.objects.filter(scene_id__in=scene_ids).only(
            "id", "scene_id", "victory_scene_id", "defeat_scene_id"
        )
        self.encounters = list(encounters_qs)
        self.encounter_scene_ids = {e.scene_id for e in self.encounters}

        self.choices_by_scene: dict[int, list] = {}
        for c in self.choices:
            self.choices_by_scene.setdefault(c.scene_id, []).append(c)

        self.pointed_to: set[int] = set()
        for c in self.choices:
            for tid in (c.target_scene_id, c.success_scene_id, c.failure_scene_id):
                if tid:
                    self.pointed_to.add(tid)
        for e in self.encounters:
            for tid in (e.victory_scene_id, e.defeat_scene_id):
                if tid:
                    self.pointed_to.add(tid)

    def validate(self):
        warnings = []
        warnings += self._check_no_hub_scenes()
        warnings += self._check_duplicate_keys()
        warnings += self._check_orphan_scenes()
        warnings += self._check_missing_routing()
        for scene in self.scenes:
            warnings += self._check_scene(scene)
        return warnings

    def _check_no_hub_scenes(self):
        if self.quest.is_unlocked and not self.quest.hub_scenes.exists():
            return [{
                "type": "no_hub_scenes",
                "scene_id": None,
                "choice_id": None,
                "message": "Quest is unlocked but has no hub scenes assigned â€” it will not appear on any notice board.",
            }]
        return []

    def _check_duplicate_keys(self):
        warnings = []
        seen_keys = {}
        for scene in self.scenes:
            if scene.key in seen_keys:
                warnings.append({
                    "type": "duplicate_key",
                    "scene_id": scene.id,
                    "choice_id": None,
                    "message": f'Duplicate key "{scene.key}" â€” scene "{scene.title}" shares a key with scene ID {seen_keys[scene.key]}.',
                })
            else:
                seen_keys[scene.key] = scene.id
        return warnings

    def _check_orphan_scenes(self):
        warnings = []
        for scene in self.scenes:
            if scene.id not in self.pointed_to and scene.id != self.entry_scene_id:
                warnings.append({
                    "type": "orphan_scene",
                    "scene_id": scene.id,
                    "choice_id": None,
                    "message": f'Scene "{scene.title}" is not reachable â€” no choices point to it and it is not the entry scene.',
                })
        return warnings

    def _check_missing_routing(self):
        warnings = []
        for c in self.choices:
            if not c.target_scene_id and not c.success_scene_id and not c.failure_scene_id:
                warnings.append({
                    "type": "missing_routing",
                    "scene_id": c.scene_id,
                    "choice_id": c.id,
                    "message": f'Choice "{c.label}" has no routing target set.',
                })
        return warnings

    def _check_scene(self, scene):
        warnings = []
        scene_choices = self.choices_by_scene.get(scene.id, [])
        warnings += self._check_missing_roll_target(scene, scene_choices)
        warnings += self._check_roll_direct_choice(scene, scene_choices)
        warnings += self._check_empty_scene(scene, scene_choices)
        warnings += self._check_combat_missing_encounter(scene)
        warnings += self._check_ending_no_hub_return(scene, scene_choices)
        return warnings

    def _check_missing_roll_target(self, scene, scene_choices):
        if not scene.requires_roll:
            return []
        has_full_roll = any(c.success_scene_id and c.failure_scene_id for c in scene_choices)
        if has_full_roll:
            return []
        return [{
            "type": "missing_roll_target",
            "scene_id": scene.id,
            "choice_id": None,
            "message": f'Scene "{scene.title}" requires a roll but has no choice with both success and failure targets set.',
        }]

    def _check_roll_direct_choice(self, scene, scene_choices):
        if not scene.requires_roll:
            return []
        return [
            {
                "type": "roll_direct_choice",
                "scene_id": scene.id,
                "choice_id": c.id,
                "message": f'Scene "{scene.title}" requires a roll but choice "{c.label}" uses a direct target â€” this is probably a mistake.',
            }
            for c in scene_choices if c.target_scene_id
        ]

    def _check_empty_scene(self, scene, scene_choices):
        if scene_choices or scene.scene_type in ("ending", "hub"):
            return []
        if scene.scene_type == "combat" and scene.id in self.encounter_scene_ids:
            return []
        return [{
            "type": "empty_scene",
            "scene_id": scene.id,
            "choice_id": None,
            "message": f'Scene "{scene.title}" has no choices.',
        }]

    def _check_combat_missing_encounter(self, scene):
        if scene.scene_type != "combat" or scene.id in self.encounter_scene_ids:
            return []
        return [{
            "type": "combat_missing_encounter",
            "scene_id": scene.id,
            "choice_id": None,
            "message": f'Scene "{scene.title}" is a combat scene but has no combat encounter configured.',
        }]

    def _check_ending_no_hub_return(self, scene, scene_choices):
        if scene.scene_type != "ending":
            return []
        has_hub_return = any(
            c.target_scene_id and self.external_scene_types.get(c.target_scene_id) == "hub"
            for c in scene_choices
        )
        if has_hub_return:
            return []
        return [{
            "type": "ending_no_hub_return",
            "scene_id": scene.id,
            "choice_id": None,
            "message": f'Ending scene "{scene.title}" has no "return to hub" choice â€” players will have no way to leave after the quest ends.',
        }]


def validate_quest(quest_id):
    return QuestValidator(quest_id).validate()
