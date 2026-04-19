"""
Shared factory helpers for test setup. Use these instead of loading fixture files
when tests only need a bootstrapped session or simple model instances.
"""
from .models import Scene, GameSession, PlayerStats, Quest, Choice, Enemy
from .models.items import Item
from .models.combat import CombatEncounter
from .constants import HUB_START_SCENE_KEY


def make_hub_scene(**kwargs):
    defaults = dict(key=HUB_START_SCENE_KEY, title='Main Square', body='.', scene_type='hub')
    defaults.update(kwargs)
    return Scene.objects.create(**defaults)


def make_game_session(client):
    """
    Creates the minimal hub scene, bootstraps a GameSession via the test client's
    /game/ request, and returns the created GameSession.
    Requires an active test client that has not yet hit /game/.
    """
    make_hub_scene()
    client.get('/game/')
    return GameSession.objects.first()


def make_quest(key='test__quest', **kwargs):
    defaults = dict(key=key, title='Test Quest', description='')
    defaults.update(kwargs)
    return Quest.objects.create(**defaults)


def make_scene(quest, key, scene_type='normal', **kwargs):
    defaults = dict(key=key, title=key, body='', scene_type=scene_type)
    defaults.update(kwargs)
    scene = Scene.objects.create(**defaults)
    quest.scenes.add(scene)
    return scene


def make_choice(scene, label='Go', **kwargs):
    return Choice.objects.create(scene=scene, label=label, order=1, **kwargs)


def make_enemy(**kwargs):
    defaults = dict(name='Test Enemy', hp=10, strength=5, agility=5, description='A foe.')
    defaults.update(kwargs)
    return Enemy.objects.create(**defaults)


def make_item(key='test__item', **kwargs):
    defaults = dict(key=key, name='Test Item', description='')
    defaults.update(kwargs)
    return Item.objects.create(**defaults)


def make_combat_encounter(scene, enemy, **kwargs):
    return CombatEncounter.objects.create(scene=scene, enemy=enemy, **kwargs)
