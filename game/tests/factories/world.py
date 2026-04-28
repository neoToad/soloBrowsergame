import factory

from game.constants import HUB_START_SCENE_KEY
from game.models import Choice, Contact, Quest, Scene

from .base import BaseFactory


class QuestFactory(BaseFactory):
    class Meta:
        model = Quest

    key = factory.Sequence(lambda n: f"quest-{n}")
    title = factory.Sequence(lambda n: f"Test Quest {n}")
    description = ""
    is_unlocked = True
    is_repeatable = False


class SceneFactory(BaseFactory):
    class Meta:
        model = Scene

    key = factory.Sequence(lambda n: f"scene-{n}")
    title = factory.Sequence(lambda n: f"Scene {n}")
    body = ""
    scene_type = "normal"
    order = 0
    requires_roll = False
    roll_stat = ""
    roll_difficulty = 10
    ending_type = ""

    class Params:
        hub = factory.Trait(scene_type="hub")
        combat = factory.Trait(scene_type="combat")
        ending_victory = factory.Trait(scene_type="ending", ending_type="victory")
        ending_defeat = factory.Trait(scene_type="ending", ending_type="defeat")


class HubSceneFactory(SceneFactory):
    key = HUB_START_SCENE_KEY
    title = "Main Square"
    body = "."
    scene_type = "hub"


class ChoiceFactory(BaseFactory):
    class Meta:
        model = Choice

    scene = factory.SubFactory(SceneFactory)
    label = "Go"
    order = 1
    target_scene = None
    success_scene = None
    failure_scene = None


class ContactFactory(BaseFactory):
    class Meta:
        model = Contact

    key = factory.Sequence(lambda n: f"contact-{n}")
    name = factory.Sequence(lambda n: f"Contact {n}")
    description = ""
