import factory

from game.models import CombatEncounter, Enemy

from .base import BaseFactory
from .world import SceneFactory


class EnemyFactory(BaseFactory):
    class Meta:
        model = Enemy

    key = factory.Sequence(lambda n: f"enemy-{n}")
    name = factory.Sequence(lambda n: f"Enemy {n}")
    description = "A foe."
    max_hp = 10
    attack_modifier = 0
    defense = 8
    damage_min = 1
    damage_max = 4


class CombatEncounterFactory(BaseFactory):
    class Meta:
        model = CombatEncounter

    scene = factory.SubFactory(SceneFactory, combat=True)
    enemy = factory.SubFactory(EnemyFactory)
    victory_scene = None
    defeat_scene = None
    victory_arrival_flavor = ""
    defeat_arrival_flavor = ""
