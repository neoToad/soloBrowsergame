import json
import os

from django.core import serializers
from django.core.management.base import BaseCommand

from game.models.combat import CombatEncounter, Enemy
from game.models.items import Item
from game.models.property import Property
from game.models.requirements import Requirement, RequirementGroup
from game.models.world import Arc, Choice, Quest, Scene, SceneItem, SceneUnlock

MODELS = [
    ("item", Item),
    ("arc", Arc),
    ("quest", Quest),
    ("scene", Scene),
    ("choice", Choice),
    ("sceneitem", SceneItem),
    ("sceneunlock", SceneUnlock),
    ("enemy", Enemy),
    ("combatencounter", CombatEncounter),
    ("requirement", Requirement),
    ("requirementgroup", RequirementGroup),
    ("property", Property),
]

FIXTURES_DIR = os.path.join("game", "fixtures")


class Command(BaseCommand):
    help = "Export all game data models to fixture JSON files"

    def handle(self, *args, **options):
        os.makedirs(FIXTURES_DIR, exist_ok=True)

        for name, model in MODELS:
            queryset = model.objects.all()
            data = serializers.serialize(
                "json",
                queryset,
                indent=2,
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True,
            )
            # Validate it's non-empty before writing
            parsed = json.loads(data)
            path = os.path.join(FIXTURES_DIR, f"{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
            self.stdout.write(
                self.style.SUCCESS(f"  {name}: {len(parsed)} objects -> {path}")
            )

        self.stdout.write(self.style.SUCCESS("Export complete."))