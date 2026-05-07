from game.constants import SESSION_KEY
from game.models import GameSession


def start_game_session(client):
    client.get("/game/")
    return GameSession.objects.get(pk=client.session[SESSION_KEY])
