from functools import wraps

from django.shortcuts import redirect

from game.constants import SESSION_KEY
from game.presentation import responses as response_utils
from game.services.session import build_render_context, load_session_context
from game.services.combat import initialize_combat_state
from game.models.events import log_event


def require_game_session(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        session_pk = request.session.get(SESSION_KEY)
        if not session_pk:
            return redirect("game_hub")
        kwargs["session_context"] = load_session_context(session_pk)
        return view_func(request, *args, **kwargs)

    return _wrapped


def _htmx_response(request, context):
    response = response_utils.render_htmx_fragment(
        request,
        "game/partials/htmx_response.html",
        context,
    )
    scene = context.get("scene")
    if scene:
        from django.urls import reverse

        response["HX-Push-Url"] = reverse("scene_detail", kwargs={"scene_key": scene.key})
    return response


def _render_current_scene(request, session, *, extra_context=None):
    session, stats, inventory, effective_stats, completed_map = load_session_context(session.pk)
    scene = session.current_scene
    combat_state, combat_init_log = initialize_combat_state(session, scene)
    if combat_init_log:
        log_event(session, combat_init_log)
    context = build_render_context(
        session,
        scene,
        stats,
        effective_stats,
        inventory,
        completed_map,
        combat_state=combat_state,
    )
    if extra_context:
        context.update(extra_context)
    if response_utils.is_htmx(request):
        return _htmx_response(request, context)
    return redirect("scene_detail", scene_key=scene.key)
