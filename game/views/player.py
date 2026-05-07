from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404

from game.constants import STAT_FIELDS
from game.models import Item
from game.models.events import log_event
from game.presentation import responses as response_utils
from game.services import gameplay
from game.services.combat import get_active_combat_state
from game.services.progression import restore_hp_on_stat_upgrade, spend_stat_point
from game.services.session import build_render_context
from game.services.types import GameplayError
from game.utils import get_effective_stats
from game.views.shared import _htmx_response, require_game_session


@require_game_session
def level_up(request, *, session_context):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    session, stats, inventory, effective_stats, completed_map = session_context

    stat_name = request.POST.get("stat", "")
    try:
        public_name, _field, new_value = spend_stat_point(stats, stat_name, STAT_FIELDS)
    except ValueError as exc:
        return response_utils.error_response(request, message=str(exc), status=400)

    post_upgrade_effective_stats = get_effective_stats(stats, inventory)
    healed = restore_hp_on_stat_upgrade(stats, post_upgrade_effective_stats.max_hp)
    log_event(session, f"{public_name.upper()} increased to {new_value}, {healed} HP restored.")

    scene = session.current_scene
    effective_stats = get_effective_stats(stats, inventory)
    combat_state = get_active_combat_state(session)

    context = build_render_context(
        session,
        scene,
        stats,
        effective_stats,
        inventory,
        completed_map,
        combat_state=combat_state,
    )
    return _htmx_response(request, context)


@require_game_session
def use_item(request, item_id, *, session_context):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    session, stats, inventory, _, completed_map = session_context
    item = get_object_or_404(Item, pk=item_id)
    try:
        result = gameplay.use_item(session_context, item)
    except GameplayError as exc:
        return response_utils.error_response(request, message=str(exc), status=exc.status)

    context = build_render_context(
        session,
        session.current_scene,
        stats,
        result.effective_stats,
        inventory,
        completed_map,
        combat_state=result.combat_state,
    )
    return _htmx_response(request, context)
