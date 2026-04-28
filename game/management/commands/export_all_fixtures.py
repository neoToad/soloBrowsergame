import json
import os

from django.core import serializers
from django.core.management.base import BaseCommand

from game.models.combat import CombatEncounter, Enemy
from game.models.items import Item
from game.models.jobs import ContactJobOffer, Job, JobApproach, JobBeatVariant
from game.models.property import Property
from game.models.requirements import Requirement, RequirementGroup
from game.models.world import Arc, Choice, Contact, Quest, Scene, SceneItem

MODELS = [
    ("item", Item),
    ("arc", Arc),
    ("quest", Quest),
    ("scene", Scene),
    ("choice", Choice),
    ("sceneitem", SceneItem),
    ("contact", Contact),
    ("job", Job),
    ("jobapproach", JobApproach),
    ("jobbeatvariant", JobBeatVariant),
    ("contactjoboffer", ContactJobOffer),
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
