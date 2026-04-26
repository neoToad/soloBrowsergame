import yaml

from django.core.management.base import BaseCommand
from django.db import transaction

from game.models.combat import Enemy
from game.models.world import Contact


class Command(BaseCommand):
    help = "Import enemies and contacts from a YAML file"

    def add_arguments(self, parser):
        parser.add_argument("yaml_path", type=str, help="Path to the enemies_and_contacts YAML file")

    def handle(self, *args, **options):
        with open(options["yaml_path"], encoding="utf-8") as f:
            data = yaml.safe_load(f)

        with transaction.atomic():
            enemies = data.get("enemies") or []
            for edata in enemies:
                obj, created = Enemy.objects.update_or_create(
                    key=edata["key"],
                    defaults={
                        "name": edata["name"],
                        "description": edata["description"],
                        "max_hp": edata.get("max_hp", 10),
                        "attack_modifier": edata.get("attack_modifier", 0),
                        "defense": edata.get("defense", 8),
                        "damage_min": edata.get("damage_min", 1),
                        "damage_max": edata.get("damage_max", 4),
                    },
                )
                verb = "Created" if created else "Updated"
                self.stdout.write(f"  Enemy: {verb} '{obj.key}'")
            self.stdout.write(f"Enemies: {len(enemies)} processed")

            contacts = data.get("contacts") or []
            for cdata in contacts:
                obj, created = Contact.objects.update_or_create(
                    key=cdata["key"],
                    defaults={
                        "name": cdata["name"],
                        "description": cdata.get("description", ""),
                    },
                )
                verb = "Created" if created else "Updated"
                self.stdout.write(f"  Contact: {verb} '{obj.key}'")
            self.stdout.write(f"Contacts: {len(contacts)} processed")