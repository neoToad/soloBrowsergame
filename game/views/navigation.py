from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from game.constants import SESSION_KEY
from game.models import Choice, GameSession, Scene
from game.models.events import log_event
from game.presentation import responses as response_utils
from game.services import gameplay, progression
from game.services.combat import initialize_combat_state
from game.services.session import build_render_context, create_session
from game.services.types import GameplayError
from game.views.shared import _htmx_response, require_game_session


def root_redirect(request):
    return redirect("game_hub")


def game_hub(request):
    session_pk = request.session.get(SESSION_KEY)

    if not session_pk:
        game_session = create_session(request)
    else:
        try:
            game_session = GameSession.objects.get(pk=session_pk)
        except GameSession.DoesNotExist:
            game_session = create_session(request)

    return redirect("scene_detail", scene_key=game_session.current_scene.key)


@require_game_session
def scene_detail(request, scene_key, *, session_context):
    game_session, stats, inventory, effective_stats, completed_map = session_context
    scene = get_object_or_404(Scene, key=scene_key)
    combat_state, combat_init_log = initialize_combat_state(game_session, scene)
    if combat_init_log:
        log_event(game_session, combat_init_log)

    context = build_render_context(
        game_session,
        scene,
        stats,
        effective_stats,
        inventory,
        completed_map,
        combat_state=combat_state,
    )
    context["all_quests_complete"] = progression.all_quests_complete(game_session)
    return render(request, "game/scene.html", context)


@require_game_session
def choice_resolve(request, choice_id, *, session_context):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    session, stats, inventory, _, completed_map = session_context
    choice = get_object_or_404(Choice, pk=choice_id)
    try:
        result = gameplay.resolve_choice(session_context, choice)
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
        turn_summary=result.turn_summary,
        roll_result=result.roll_result,
    )
    context["all_quests_complete"] = progression.all_quests_complete(session)
    if response_utils.is_htmx(request):
        return _htmx_response(request, context)
    return redirect("scene_detail", scene_key=result.next_scene.key)
