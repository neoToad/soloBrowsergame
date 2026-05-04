from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseNotAllowed

from .models import (
    Choice, GameSession, Item,
    Quest, Scene,
)
from .models.events import log_event
from .services.session     import load_session_context, create_session, build_render_context
from .services.combat      import initialize_combat_state, get_active_combat_state
from .services.progression import spend_stat_point, restore_hp_on_stat_upgrade
from .services             import gameplay
from .services.types       import GameplayError
from .presentation import responses as response_utils
from .utils import get_effective_stats
from .constants import SESSION_KEY, STAT_FIELDS


def require_game_session(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        session_pk = request.session.get(SESSION_KEY)
        if not session_pk:
            return redirect('game_hub')
        kwargs['session_context'] = load_session_context(session_pk)
        return view_func(request, *args, **kwargs)

    return _wrapped


def _htmx_response(request, context):
    response = response_utils.render_htmx_fragment(
        request,
        'game/partials/htmx_response.html',
        context,
    )
    scene = context.get('scene')
    if scene:
        from django.urls import reverse
        response['HX-Push-Url'] = reverse('scene_detail', kwargs={'scene_key': scene.key})
    return response


def _render_current_scene(request, session, *, extra_context=None):
    session, stats, inventory, effective_stats, completed_map = load_session_context(session.pk)
    scene = session.current_scene
    combat_state, combat_init_log = initialize_combat_state(session, scene)
    if combat_init_log:
        log_event(session, combat_init_log)
    context = build_render_context(
        session, scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state,
    )
    if extra_context:
        context.update(extra_context)
    if response_utils.is_htmx(request):
        return _htmx_response(request, context)
    return redirect('scene_detail', scene_key=scene.key)


def root_redirect(request):
    return redirect('game_hub')


def game_hub(request):
    session_pk = request.session.get(SESSION_KEY)

    if not session_pk:
        game_session = create_session(request)
    else:
        try:
            game_session = GameSession.objects.get(pk=session_pk)
        except GameSession.DoesNotExist:
            game_session = create_session(request)

    return redirect('scene_detail', scene_key=game_session.current_scene.key)


@require_game_session
def scene_detail(request, scene_key, *, session_context):
    game_session, stats, inventory, effective_stats, completed_map = session_context
    scene        = get_object_or_404(Scene, key=scene_key)
    combat_state, combat_init_log = initialize_combat_state(game_session, scene)
    if combat_init_log:
        log_event(game_session, combat_init_log)

    context = build_render_context(
        game_session, scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state,
    )
    return render(request, 'game/scene.html', context)


@require_game_session
def choice_resolve(request, choice_id, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, stats, inventory, _, completed_map = session_context
    choice = get_object_or_404(Choice, pk=choice_id)
    try:
        result = gameplay.resolve_choice(session_context, choice)
    except GameplayError as exc:
        return response_utils.error_response(request, message=str(exc), status=exc.status)

    context = build_render_context(
        session, result.next_scene, stats, result.effective_stats, inventory, completed_map,
        combat_state=result.combat_state,
        turn_summary=result.turn_summary,
        roll_result=result.roll_result,
    )
    if response_utils.is_htmx(request):
        return _htmx_response(request, context)
    return redirect('scene_detail', scene_key=result.next_scene.key)


@require_game_session
def start_quest(request, quest_key, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, stats, inventory, _, completed_map = session_context
    quest = get_object_or_404(Quest, key=quest_key, is_unlocked=True)
    try:
        result = gameplay.start_quest(session_context, quest)
    except GameplayError as exc:
        return response_utils.error_response(request, message=str(exc), status=exc.status)

    context = build_render_context(
        session, result.next_scene, stats, result.effective_stats, inventory, completed_map,
        combat_state=result.combat_state,
    )
    if response_utils.is_htmx(request):
        return _htmx_response(request, context)
    return redirect('scene_detail', scene_key=result.next_scene.key)


@require_game_session
def combat_attack(request, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:
        context = gameplay.run_player_attack(session_context)
    except GameplayError as exc:
        return response_utils.error_response(request, message=str(exc), status=exc.status)

    return _htmx_response(request, context)


@require_game_session
def combat_resolve_enemy(request, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:
        context = gameplay.run_enemy_attack(session_context)
    except GameplayError as exc:
        return response_utils.error_response(request, message=str(exc), status=exc.status)

    return _htmx_response(request, context)


@require_game_session
def combat_continue(request, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:
        context = gameplay.run_combat_continue(session_context)
    except GameplayError as exc:
        return response_utils.error_response(request, message=str(exc), status=exc.status)

    return _htmx_response(request, context)


@require_game_session
def level_up(request, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, stats, inventory, effective_stats, completed_map = session_context

    stat_name = request.POST.get('stat', '')
    try:
        public_name, _field, new_value = spend_stat_point(stats, stat_name, STAT_FIELDS)
    except ValueError as exc:
        return response_utils.error_response(request, message=str(exc), status=400)

    post_upgrade_effective_stats = get_effective_stats(stats, inventory)
    healed = restore_hp_on_stat_upgrade(stats, post_upgrade_effective_stats.max_hp)
    log_event(session, f"{public_name.upper()} increased to {new_value}, {healed} HP restored.")

    scene           = session.current_scene
    effective_stats = get_effective_stats(stats, inventory)
    combat_state    = get_active_combat_state(session)

    context = build_render_context(
        session, scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state,
    )
    return _htmx_response(request, context)


@require_game_session
def use_item(request, item_id, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, stats, inventory, _, completed_map = session_context
    item = get_object_or_404(Item, pk=item_id)
    try:
        result = gameplay.use_item(session_context, item)
    except GameplayError as exc:
        return response_utils.error_response(request, message=str(exc), status=exc.status)

    context = build_render_context(
        session, session.current_scene, stats, result.effective_stats, inventory, completed_map,
        combat_state=result.combat_state,
    )
    return _htmx_response(request, context)
