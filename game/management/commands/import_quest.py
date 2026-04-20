import yaml

from django.core.management.base import BaseCommand
from django.db import transaction

from game.models.world import Arc, Quest, Scene, Choice, Contact
from game.models.items import Item
from game.models.requirements import Requirement, RequirementGroup


class Command(BaseCommand):
    help = "Import a quest from a YAML file"

    def add_arguments(self, parser):
        parser.add_argument("yaml_path", type=str, help="Path to the quest YAML file")

    def handle(self, *args, **options):
        with open(options["yaml_path"], encoding="utf-8") as f:
            data = yaml.safe_load(f)

        with transaction.atomic():
            # Step 1 — Quest
            qdata = data["quest"]
            arc = None
            if qdata.get("arc"):
                arc = Arc.objects.get(key=qdata["arc"])

            quest, created = Quest.objects.update_or_create(
                key=qdata["key"],
                defaults={
                    "title": qdata["title"],
                    "description": qdata["description"],
                    "is_repeatable": qdata.get("is_repeatable", False),
                    "arc_order": qdata.get("arc_order", 0),
                    "arc": arc,
                    "entrance_scene": None,
                },
            )
            verb = "Created" if created else "Updated"
            self.stdout.write(f"Step 1 — Quest: {verb} '{quest.key}'")

            # Step 2 — Scenes (pass 1: scalars only, no FKs)
            scene_map: dict[str, Scene] = {}
            for sdata in data["scenes"]:
                roll = sdata.get("roll", {}) or {}
                scene, created = Scene.objects.update_or_create(
                    key=sdata["key"],
                    defaults={
                        "scene_type": sdata["scene_type"],
                        "title": sdata["title"],
                        "body": sdata["body"],
                        "order": sdata.get("order", 0),
                        "requires_roll": roll.get("requires_roll", False),
                        "roll_stat": roll.get("roll_stat") or "",
                        "roll_difficulty": roll.get("roll_difficulty") or 10,
                        "ending_type": sdata.get("ending_type") or "",
                        "cash_change": sdata.get("cash_change", 0),
                        "rep_change": sdata.get("rep_change", 0),
                        "heat_change": sdata.get("heat_change", 0),
                        "consume_item": None,
                        "receive_property": None,
                        "lose_property": None,
                    },
                )
                scene_map[scene.key] = scene
                verb = "Created" if created else "Updated"
                self.stdout.write(f"  Scene: {verb} '{scene.key}'")
            self.stdout.write(f"Step 2 — Scenes: {len(scene_map)} processed")

            # Step 3 — entrance_scene
            entrance_key = qdata["entrance_scene"]
            quest.entrance_scene = scene_map[entrance_key]
            quest.save()
            self.stdout.write(f"Step 3 — entrance_scene set to '{entrance_key}'")

            # Step 4 — Choices
            total_choices = 0
            for sdata in data["scenes"]:
                scene_obj = scene_map[sdata["key"]]
                self._import_choices(sdata, scene_obj, scene_map)
                total_choices += len(sdata.get("choices") or [])
            self.stdout.write(f"Step 4 — Choices: {total_choices} processed")

            # Step 5 — Requirements
            for sdata in data["scenes"]:
                scene_obj = scene_map[sdata["key"]]
                for choice_data in (sdata.get("choices") or []):
                    choice_obj = Choice.objects.get(
                        scene=scene_obj,
                        label=choice_data["label"],
                        order=choice_data.get("order", 0),
                    )
                    groups = self._import_requirement_groups(choice_data.get("requirements") or [])
                    choice_obj.requirements.set(groups)

            quest_groups = self._import_requirement_groups(qdata.get("requirements") or [])
            quest.requirements.set(quest_groups)
            self.stdout.write("Step 5 — Requirements processed")

    def _resolve_scene(self, key, scene_map):
        if key is None:
            return None
        if key in scene_map:
            return scene_map[key]
        return Scene.objects.get(key=key)

    def _import_choices(self, scene_data, scene_obj, scene_map):
        for choice in (scene_data.get("choices") or []):
            obj, _ = Choice.objects.update_or_create(
                scene=scene_obj,
                label=choice["label"],
                order=choice.get("order", 0),
                defaults={
                    "arrival_flavor":         choice.get("arrival_flavor") or "",
                    "failure_arrival_flavor": choice.get("failure_arrival_flavor") or "",
                    "set_flag_name":          choice.get("set_flag_name") or "",
                    "clear_flag_name":        choice.get("clear_flag_name") or "",
                    "target_scene":           self._resolve_scene(choice.get("target_scene"), scene_map),
                    "success_scene":          self._resolve_scene(choice.get("success_scene"), scene_map),
                    "failure_scene":          self._resolve_scene(choice.get("failure_scene"), scene_map),
                },
            )
            obj.requirements.clear()  # populated in Step 5

    def _import_requirement_groups(self, groups_data):
        groups = []
        for gdata in (groups_data or []):
            group, _ = RequirementGroup.objects.get_or_create(label=gdata["label"])
            group.logic = gdata.get("logic", "all")
            group.save()
            group.requirements.clear()
            for cdata in (gdata.get("conditions") or []):
                req = Requirement.objects.create(
                    condition_type=cdata["condition_type"],
                    flag_name=cdata.get("flag_name") or "",
                    stat_name=cdata.get("stat_name") or "",
                    stat_value=cdata.get("stat_value") or 0,
                    required_ending_type=cdata.get("required_ending_type") or "",
                    required_item=Item.objects.get(key=cdata["required_item"]) if cdata.get("required_item") else None,
                    required_quest=Quest.objects.get(key=cdata["required_quest"]) if cdata.get("required_quest") else None,
                    required_contact=Contact.objects.get(key=cdata["required_contact"]) if cdata.get("required_contact") else None,
                )
                group.requirements.add(req)
            groups.append(group)
        return groups