from game.models import GameSession

from .world import HubSceneFactory


def bootstrap_game_session(client):
    HubSceneFactory()
    client.get('/game/')
    return GameSession.objects.first()
