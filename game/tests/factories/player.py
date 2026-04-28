import factory

from game.models import GameSession, PlayerStats

from game.constants import HUB_START_SCENE_KEY
from .base import BaseFactory
from .world import HubSceneFactory


class GameSessionFactory(BaseFactory):
    class Meta:
        model = GameSession

    session_key = factory.Sequence(lambda n: f"test-session-{n}")
    current_scene = factory.SubFactory(HubSceneFactory, key=HUB_START_SCENE_KEY)
    flags = factory.LazyFunction(dict)


class PlayerStatsFactory(BaseFactory):
    class Meta:
        model = PlayerStats

    session = factory.SubFactory(GameSessionFactory)


class GameSessionWithStatsFactory(GameSessionFactory):
    @factory.post_generation
    def with_stats(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted is False:
            return
        PlayerStats.objects.get_or_create(session=self)
