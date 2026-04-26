from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseNotAllowed

from .models import (
    Choice, GameSession, Item,
    Quest, Scene,
    ContactJobOffer, Job, JobApproach, JobRun,
)
from .models.events import log_event, flush_event_log
from .services.session     import load_session_context, create_session, build_render_context
from .services.combat      import initialize_combat_state, get_active_combat_state
from .services.progression import spend_stat_point
from .services             import gameplay
from .services.types       import GameplayError
from .services             import jobs as jobs_service
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
def job_recon_start(request, job_key, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, *_ = session_context
    job = get_object_or_404(Job, key=job_key, is_active=True)

    try:
        recon_preview = jobs_service.start_recon(session, job)
    except jobs_service.JobRulesError as exc:
        return response_utils.error_response(request, message=str(exc), status=403)

    return _render_current_scene(request, session, extra_context={'job_recon_preview': recon_preview})


@require_game_session
def job_recon_commit(request, job_key, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, *_ = session_context
    job = get_object_or_404(Job, key=job_key, is_active=True)

    try:
        run = jobs_service.commit_recon(session, job)
    except jobs_service.JobRulesError as exc:
        return response_utils.error_response(request, message=str(exc), status=403)

    flush_event_log(session, [f"You commit to {job.title}. Beat 1 begins."])
    return _render_current_scene(request, session, extra_context={'job_run': run})


@require_game_session
def job_recon_walk_away(request, job_key, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, *_ = session_context
    job = get_object_or_404(Job, key=job_key, is_active=True)
    jobs_service.increment_turn(session)
    flush_event_log(session, [f"You walk away from {job.title} for now."])
    return _render_current_scene(request, session)


@require_game_session
def job_contact_start(request, offer_id, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, *_ = session_context
    offer = get_object_or_404(ContactJobOffer, pk=offer_id, is_active=True)

    try:
        run = jobs_service.start_contact_job(session, offer)
    except jobs_service.JobRulesError as exc:
        return response_utils.error_response(request, message=str(exc), status=403)

    flush_event_log(session, [f"{offer.contact.name} lines up a job: {offer.job.title}."])
    return _render_current_scene(request, session, extra_context={'job_run': run})


@require_game_session
def job_run_beat_1(request, run_id, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    approach_key = (request.POST.get('approach') or '').strip()
    if not approach_key:
        return response_utils.error_response(request, message="Missing approach key.", status=400)

    session, *_ = session_context
    run = get_object_or_404(JobRun, pk=run_id)
    approach = JobApproach.objects.filter(job_id=run.job_id, key=approach_key).first()
    if approach is None:
        return response_utils.error_response(request, message="Invalid approach key.", status=400)

    try:
        result = jobs_service.resolve_beat_1(session, run, approach)
    except jobs_service.JobRulesError as exc:
        return response_utils.error_response(request, message=str(exc), status=403)

    outcome = "success" if result['roll'].success else "failure"
    flush_event_log(session, [f"Beat 1 ({approach.label}): {outcome}."])
    return _render_current_scene(request, session, extra_context={'job_beat_1': result})


@require_game_session
def job_run_beat_2(request, run_id, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    action_key = (request.POST.get('action') or '').strip()
    if not action_key:
        return response_utils.error_response(request, message="Missing beat 2 action key.", status=400)

    session, *_ = session_context
    run = get_object_or_404(JobRun, pk=run_id)

    try:
        result = jobs_service.resolve_beat_2(session, run, action_key)
    except jobs_service.JobRulesError as exc:
        return response_utils.error_response(request, message=str(exc), status=403)

    flush_event_log(session, [f"Beat 2 resolved: {result['variant'].title}."])
    return _render_current_scene(request, session, extra_context={'job_beat_2': result})


@require_game_session
def job_run_abort(request, run_id, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, *_ = session_context
    run = get_object_or_404(JobRun, pk=run_id)

    try:
        jobs_service.abort_job_run(session, run)
    except jobs_service.JobRulesError as exc:
        return response_utils.error_response(request, message=str(exc), status=403)

    flush_event_log(session, [f"You abort {run.job.title}."])
    return _render_current_scene(request, session)


@require_game_session
def job_run_resolve(request, run_id, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, *_ = session_context
    run = get_object_or_404(JobRun, pk=run_id)

    try:
        result = jobs_service.resolve_beat_3(session, run)
    except jobs_service.JobRulesError as exc:
        return response_utils.error_response(request, message=str(exc), status=403)

    rewards = result['rewards']
    flush_event_log(
        session,
        [
            f"Job complete: +${rewards['cash']} cash, {rewards['heat']} heat, {rewards['rep']} rep.",
        ],
    )
    return _render_current_scene(request, session, extra_context={'job_result': result})


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

    log_event(session, f"{public_name.upper()} increased to {new_value}.")

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
