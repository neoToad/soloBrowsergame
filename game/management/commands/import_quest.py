import yaml

from django.core.management.base import BaseCommand
from django.db import transaction

from game.models.world import Arc, Quest, Scene


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