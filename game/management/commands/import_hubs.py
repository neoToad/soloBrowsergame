import yaml

from django.core.management.base import BaseCommand
from django.db import transaction

from game.models.world import Scene, Choice, Contact, SceneItem, SceneContact
from game.models.items import Item
from game.models.requirements import Requirement, RequirementGroup


class Command(BaseCommand):
    help = "Import hub scenes from a YAML file"

    def add_arguments(self, parser):
        parser.add_argument("yaml_path", type=str, help="Path to the hubs YAML file")

    def handle(self, *args, **options):
        with open(options["yaml_path"], encoding="utf-8") as f:
            data = yaml.safe_load(f)

        with transaction.atomic():
            # Step 1 — Scenes (pass 1: scalars only, no FKs)
            scene_map: dict[str, Scene] = {}
            for hdata in data["hubs"]:
                roll = hdata.get("roll", {}) or {}
                arrival = hdata.get("arrival", {}) or {}
                scene, created = Scene.objects.update_or_create(
                    key=hdata["key"],
                    defaults={
                        "scene_type": hdata["scene_type"],
                        "title": hdata["title"],
                        "body": hdata["body"],
                        "order": hdata.get("order", 0),
                        "requires_roll": roll.get("requires_roll", False),
                        "roll_stat": roll.get("roll_stat") or "",
                        "roll_difficulty": roll.get("roll_difficulty") or 10,
                        "ending_type": "",
                        "cash_change": arrival.get("cash_change", 0),
                        "rep_change": arrival.get("rep_change", 0),
                        "heat_change": arrival.get("heat_change", 0),
                        "consume_item": self._get_or_warn(Item, arrival.get("consume_item")),
                        "receive_property": None,
                        "lose_property": None,
                    },
                )
                scene_map[scene.key] = scene
                verb = "Created" if created else "Updated"
                self.stdout.write(f"  Scene: {verb} '{scene.key}'")
            self.stdout.write(f"Step 1 — Scenes: {len(scene_map)} processed")

            # Step 2 — Choices
            total_choices = 0
            for hdata in data["hubs"]:
                scene_obj = scene_map[hdata["key"]]
                self._import_choices(hdata, scene_obj, scene_map)
                total_choices += len(hdata.get("choices") or [])
            self.stdout.write(f"Step 2 — Choices: {total_choices} processed")

            # Step 3 — Requirements
            for hdata in data["hubs"]:
                scene_obj = scene_map[hdata["key"]]
                for choice_data in (hdata.get("choices") or []):
                    choice_obj = Choice.objects.get(
                        scene=scene_obj,
                        label=choice_data["label"],
                        order=choice_data.get("order", 0),
                    )
                    groups = self._import_requirement_groups(choice_data.get("requirements") or [])
                    choice_obj.requirements.set(groups)
            self.stdout.write("Step 3 — Requirements processed")

            # Step 4 — SceneItems, SceneContacts
            for hdata in data["hubs"]:
                scene_obj = scene_map[hdata["key"]]
                self._import_scene_items(hdata, scene_obj)
                self._import_scene_contacts(hdata, scene_obj)
            self.stdout.write("Step 4 — SceneItems, SceneContacts processed")

    def _get_or_warn(self, model, key):
        if not key:
            return None
        try:
            return model.objects.get(key=key)
        except model.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"  WARNING: {model.__name__} '{key}' not found in DB — FK set to null"))

    def _resolve_scene(self, key, scene_map):
        if key is None:
            return None
        if key in scene_map:
            return scene_map[key]
        try:
            return Scene.objects.get(key=key)
        except Scene.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"  WARNING: scene '{key}' not found in DB — FK set to null"))

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
            obj.requirements.clear()

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
                    required_item=self._get_or_warn(Item, cdata.get("required_item")),
                    required_quest=None,
                    required_contact=self._get_or_warn(Contact, cdata.get("required_contact")),
                )
                group.requirements.add(req)
            groups.append(group)
        return groups

    def _import_scene_items(self, scene_data, scene_obj):
        SceneItem.objects.filter(scene=scene_obj).delete()
        for entry in (scene_data.get("scene_items") or scene_data.get("items") or []):
            SceneItem.objects.create(
                scene=scene_obj,
                item=self._get_or_warn(Item, entry["item"]),
                quantity=entry.get("quantity", 1),
                award_once=entry.get("award_once", True),
            )

    def _import_scene_contacts(self, scene_data, scene_obj):
        SceneContact.objects.filter(scene=scene_obj).delete()
        for entry in (scene_data.get("scene_contacts") or scene_data.get("contacts") or []):
            SceneContact.objects.create(
                scene=scene_obj,
                contact=self._get_or_warn(Contact, entry["contact"]),
                action=entry.get("action", "gain"),
                award_once=entry.get("award_once", True),
            )