from django.http import HttpResponseNotAllowed

from game.presentation import responses as response_utils
from game.services import gameplay
from game.services.types import GameplayError
from game.views.shared import _htmx_response, require_game_session


@require_game_session
def combat_attack(request, *, session_context):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        context = gameplay.run_player_attack(session_context)
    except GameplayError as exc:
        return response_utils.error_response(request, message=str(exc), status=exc.status)

    return _htmx_response(request, context)


@require_game_session
def combat_resolve_enemy(request, *, session_context):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        context = gameplay.run_enemy_attack(session_context)
    except GameplayError as exc:
        return response_utils.error_response(request, message=str(exc), status=exc.status)

    return _htmx_response(request, context)


@require_game_session
def combat_continue(request, *, session_context):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        context = gameplay.run_combat_continue(session_context)
    except GameplayError as exc:
        return response_utils.error_response(request, message=str(exc), status=exc.status)

    return _htmx_response(request, context)
