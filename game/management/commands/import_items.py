import yaml

from django.core.management.base import BaseCommand
from django.db import transaction

from game.models.items import Item


class Command(BaseCommand):
    help = "Import items from a YAML file"

    def add_arguments(self, parser):
        parser.add_argument("yaml_path", type=str, help="Path to the items YAML file")

    def handle(self, *args, **options):
        with open(options["yaml_path"], encoding="utf-8") as f:
            data = yaml.safe_load(f)

        with transaction.atomic():
            items = data.get("items") or []
            for idata in items:
                obj, created = Item.objects.update_or_create(
                    key=idata["key"],
                    defaults={
                        "name": idata["name"],
                        "description": idata["description"],
                        "is_consumable": idata.get("is_consumable", False),
                        "effect_type": idata.get("effect_type") or "",
                        "effect_stat": idata.get("effect_stat") or "",
                        "effect_value": idata.get("effect_value", 0),
                        "passive_stat": idata.get("passive_stat") or "",
                        "passive_value": idata.get("passive_value", 0),
                    },
                )
                verb = "Created" if created else "Updated"
                self.stdout.write(f"  Item: {verb} '{obj.key}'")
            self.stdout.write(f"Items: {len(items)} processed")