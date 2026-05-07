from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect

from game.models import Quest
from game.presentation import responses as response_utils
from game.services import gameplay
from game.services.session import build_render_context
from game.services.types import GameplayError
from game.views.shared import _htmx_response, require_game_session


@require_game_session
def start_quest(request, quest_key, *, session_context):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    session, stats, inventory, _, completed_map = session_context
    quest = get_object_or_404(Quest, key=quest_key, is_unlocked=True)
    try:
        result = gameplay.start_quest(session_context, quest)
    except GameplayError as exc:
        return response_utils.error_response(request, message=str(exc), status=exc.status)

    context = build_render_context(
        session,
        result.next_scene,
        stats,
        result.effective_stats,
        inventory,
        completed_map,
        combat_state=result.combat_state,
    )
    if response_utils.is_htmx(request):
        return _htmx_response(request, context)
    return redirect("scene_detail", scene_key=result.next_scene.key)
