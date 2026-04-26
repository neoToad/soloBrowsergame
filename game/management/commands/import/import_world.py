import yaml

from django.core.management.base import BaseCommand
from django.db import transaction

from game.models.world import Gang, Scene
from game.models.property import Property


class Command(BaseCommand):
    help = "Import gangs and properties from a YAML file"

    def add_arguments(self, parser):
        parser.add_argument("yaml_path", type=str, help="Path to the world data YAML file")

    def handle(self, *args, **options):
        with open(options["yaml_path"], encoding="utf-8") as f:
            data = yaml.safe_load(f)

        with transaction.atomic():
            self._import_gangs(data)
            self._import_properties(data)

    def _import_gangs(self, data):
        gangs = data.get("gangs") or []
        for gdata in gangs:
            obj, created = Gang.objects.update_or_create(
                key=gdata["key"],
                defaults={
                    "name": gdata["name"],
                    "description": gdata.get("description", ""),
                },
            )
            verb = "Created" if created else "Updated"
            self.stdout.write(f"  Gang: {verb} '{obj.key}'")
        self.stdout.write(f"Gangs: {len(gangs)} processed")

    def _import_properties(self, data):
        properties = data.get("properties") or []
        for pdata in properties:
            resolution_scene = self._resolve_scene(pdata.get("resolution_scene"))
            obj, created = Property.objects.update_or_create(
                name=pdata["name"],
                defaults={
                    "property_type": pdata["property_type"],
                    "cash_per_turn": pdata.get("cash_per_turn", 0),
                    "heat_per_turn": pdata.get("heat_per_turn", 0),
                    "rep_per_turn": pdata.get("rep_per_turn", 0),
                    "is_contestable": pdata.get("is_contestable", False),
                    "resolution_scene": resolution_scene,
                },
            )
            verb = "Created" if created else "Updated"
            self.stdout.write(f"  Property: {verb} '{obj.name}'")
        self.stdout.write(f"Properties: {len(properties)} processed")

    def _resolve_scene(self, key):
        if not key:
            return None
        try:
            return Scene.objects.get(key=key)
        except Scene.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"  WARNING: Scene '{key}' not found in DB — FK set to null"))
            return None