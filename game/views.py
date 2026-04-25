from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseNotAllowed
from django.template.loader import render_to_string

from .models import (
    Choice, CombatEncounter, CombatState, GameSession, Item,
    Quest, Scene,
    ContactJobOffer, Job, JobApproach, JobRun,
)
from .models.events import log_event, flush_event_log
from .services.session     import load_session_context, create_session, build_render_context, build_player_context
from .services.scene       import resolve_roll
from .services.combat      import (
    initialize_combat_state, get_active_combat_state, resolve_combat_end,
    resolve_player_attack as resolve_player_attack_util,
    resolve_enemy_attack as resolve_enemy_attack_util,
)
from .services.inventory   import get_player_inventory, consume_item as consume_item_util
from .services.flags       import set_flag, clear_flag
from .services.arrival     import process_arrival
from .services.property_service import apply_property_rewards
from .services.progression import XP_AWARDS, LEVEL_UP_FLAVOR, spend_stat_point
from .services import jobs as jobs_service
from .utils import stat_modifier, get_effective_stats, RollResult, DamageResult
from .constants import SESSION_KEY, STAT_FIELD_MAP, USE_ITEM_FLAVOR


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
    scene_html       = render_to_string('game/partials/scene_panel.html',      context, request)
    stats_html       = render_to_string('game/partials/stats_bar.html',        context, request)
    top_stats_html   = render_to_string('game/partials/top_stats_bar.html',    context, request)
    log_html         = render_to_string('game/partials/event_log.html',        context, request)
    inventory_html   = render_to_string('game/partials/inventory.html',        context, request)
    mobile_html      = render_to_string('game/partials/mobile_stats_bar.html', context, request)
    territories_html = render_to_string('game/partials/territories.html',      context, request)
    response = HttpResponse(scene_html + stats_html + top_stats_html + log_html + inventory_html + mobile_html + territories_html)
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
    if request.headers.get('HX-Request') == 'true':
        return _htmx_response(request, context)
    return redirect('scene_detail', scene_key=scene.key)


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

    apply_property_rewards(game_session, scene)
    context = build_render_context(
        game_session, scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state,
    )
    context['session'] = game_session
    return render(request, 'game/scene.html', context)


@require_game_session
def choice_resolve(request, choice_id, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, stats, inventory, effective_stats, completed_map = session_context
    choice = get_object_or_404(Choice, pk=choice_id)
    if choice.scene_id != session.current_scene_id:
        return HttpResponse("Choice is not available from your current scene.", status=403)

    scene = choice.scene

    log_queue = []

    # ROUTING
    if scene.requires_roll:
        next_scene, roll_log, roll_result = resolve_roll(scene, choice, effective_stats)
        log_queue.append(roll_log)
    else:
        next_scene = choice.target_scene
        if next_scene is None:
            return HttpResponse("This choice has no destination configured.", status=500)
        roll_result = None

    # ARRIVAL FLAVOR
    if roll_result and not roll_result.success and choice.failure_arrival_flavor:
        log_queue.append(choice.failure_arrival_flavor)
    elif choice.arrival_flavor:
        log_queue.append(choice.arrival_flavor)

    # FLAGS
    if choice.set_flag_name:
        set_flag(session, choice.set_flag_name)
    if choice.clear_flag_name:
        clear_flag(session, choice.clear_flag_name)

    session.current_scene = next_scene
    session.save()

    arrival_logs, turn_summary = process_arrival(session, stats, inventory, completed_map, next_scene)
    log_queue.extend(arrival_logs)
    flush_event_log(session, log_queue)

    combat_state, combat_init_log = initialize_combat_state(session, next_scene)
    if combat_init_log:
        log_event(session, combat_init_log)
    effective_stats = get_effective_stats(stats, inventory)

    is_htmx = request.headers.get('HX-Request') == 'true'
    if is_htmx:
        context = build_render_context(
            session, next_scene, stats, effective_stats, inventory, completed_map,
            combat_state=combat_state,
            turn_summary=turn_summary,
            roll_result=roll_result,
        )
        return _htmx_response(request, context)
    return redirect('scene_detail', scene_key=next_scene.key)


@require_game_session
def start_quest(request, quest_key, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, stats, inventory, effective_stats, completed_map = session_context
    quest = get_object_or_404(Quest, key=quest_key, is_unlocked=True)

    ctx = build_player_context(effective_stats, inventory, completed_map, flags=session.flags)
    if quest.requirements.exists():
        if not all(rg.evaluate(ctx) for rg in quest.requirements.all()):
            return HttpResponse("Quest requirements not met.", status=403)

    next_scene = quest.entrance_scene
    session.current_scene = next_scene
    session.save()

    arrival_logs, _ = process_arrival(session, stats, inventory, completed_map, next_scene)
    flush_event_log(session, [f"You took the job: {quest.title}.", *arrival_logs])

    combat_state, combat_init_log = initialize_combat_state(session, next_scene)
    if combat_init_log:
        log_event(session, combat_init_log)
    effective_stats = get_effective_stats(stats, inventory)

    is_htmx = request.headers.get('HX-Request') == 'true'
    if is_htmx:
        context = build_render_context(
            session, next_scene, stats, effective_stats, inventory, completed_map,
            combat_state=combat_state,
        )
        return _htmx_response(request, context)
    return redirect('scene_detail', scene_key=next_scene.key)


@require_game_session
def job_recon_start(request, job_key, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, *_ = session_context
    job = get_object_or_404(Job, key=job_key, is_active=True)

    try:
        recon_preview = jobs_service.start_recon(session, job)
    except jobs_service.JobRulesError as exc:
        return HttpResponse(str(exc), status=403)

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
        return HttpResponse(str(exc), status=403)

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
        return HttpResponse(str(exc), status=403)

    flush_event_log(session, [f"{offer.contact.name} lines up a job: {offer.job.title}."])
    return _render_current_scene(request, session, extra_context={'job_run': run})


@require_game_session
def job_run_beat_1(request, run_id, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    approach_key = (request.POST.get('approach') or '').strip()
    if not approach_key:
        return HttpResponse("Missing approach key.", status=400)

    session, *_ = session_context
    run = get_object_or_404(JobRun, pk=run_id)
    approach = JobApproach.objects.filter(job_id=run.job_id, key=approach_key).first()
    if approach is None:
        return HttpResponse("Invalid approach key.", status=400)

    try:
        result = jobs_service.resolve_beat_1(session, run, approach)
    except jobs_service.JobRulesError as exc:
        return HttpResponse(str(exc), status=403)

    outcome = "success" if result['roll'].success else "failure"
    flush_event_log(session, [f"Beat 1 ({approach.label}): {outcome}."])
    return _render_current_scene(request, session, extra_context={'job_beat_1': result})


@require_game_session
def job_run_beat_2(request, run_id, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    action_key = (request.POST.get('action') or '').strip()
    if not action_key:
        return HttpResponse("Missing beat 2 action key.", status=400)

    session, *_ = session_context
    run = get_object_or_404(JobRun, pk=run_id)

    try:
        result = jobs_service.resolve_beat_2(session, run, action_key)
    except jobs_service.JobRulesError as exc:
        return HttpResponse(str(exc), status=403)

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
        return HttpResponse(str(exc), status=403)

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
        return HttpResponse(str(exc), status=403)

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

    session, stats, inventory, effective_stats, completed_map = session_context

    try:
        combat_state = session.combat_state
    except CombatState.DoesNotExist:
        return HttpResponse("No active combat.", status=400)

    if not combat_state.is_active:
        return HttpResponse("Combat is not active.", status=400)

    enemy     = combat_state.enemy
    encounter = CombatEncounter.objects.get(scene=session.current_scene)

    p = resolve_player_attack_util(effective_stats, enemy)
    str_mod = stat_modifier(effective_stats.strength)
    mod_str = f"+{str_mod}" if str_mod >= 0 else str(str_mod)

    if p.hit:
        combat_state.enemy_hp = max(0, combat_state.enemy_hp - p.damage)
        combat_state.save()

    if combat_state.enemy_hp <= 0:
        if p.hit:
            log_event(session,
                f"You move on him — roll {p.roll} ({mod_str}) = {p.total} "
                f"vs {enemy.defense} — Hit! {p.damage} damage."
            )
        log_event(session, f"{enemy.name} goes down.")
        combat_state.pending_victory = True
        combat_state.save()
        str_mod = stat_modifier(effective_stats.strength)
        roll_result = RollResult(
            roll=p.roll, modifier=str_mod, mod_display=mod_str,
            total=p.total, dc=enemy.defense, stat='strength', success=p.hit,
        )
        dmg_mod = max(0, str_mod)
        damage_result = DamageResult(
            die_roll=p.damage_die, die_label='d6',
            modifier=dmg_mod, mod_display=f"+{dmg_mod}" if dmg_mod >= 0 else str(dmg_mod),
            total=p.damage,
        )
        context = build_render_context(
            session, session.current_scene, stats, effective_stats, inventory, completed_map,
            combat_state=combat_state,
            roll_result=roll_result,
            damage_result=damage_result,
        )
        context['choices'] = []
        return _htmx_response(request, context)

    e = resolve_enemy_attack_util(enemy, effective_stats)

    if p.hit:
        log_event(session,
            f"You move on him — roll {p.roll} ({mod_str}) = {p.total} "
            f"vs {enemy.defense} — Hit! {p.damage} damage."
        )
    else:
        log_event(session,
            f"You move on him — roll {p.roll} ({mod_str}) = {p.total} "
            f"vs {enemy.defense} — Missed."
        )

    combat_state.pending_e_roll  = e.roll
    combat_state.pending_e_total = e.total
    combat_state.pending_e_hit   = e.hit
    combat_state.pending_e_dmg   = e.damage
    combat_state.save()

    effective_stats = get_effective_stats(stats, inventory)
    roll_result = RollResult(
        roll        = p.roll,
        modifier    = str_mod,
        mod_display = mod_str,
        total       = p.total,
        dc          = enemy.defense,
        stat        = 'strength',
        success     = p.hit,
    )
    damage_result = None
    if p.hit:
        dmg_mod     = max(0, str_mod)
        dmg_mod_str = f"+{dmg_mod}" if dmg_mod >= 0 else str(dmg_mod)
        damage_result = DamageResult(
            die_roll    = p.damage_die,
            die_label   = 'd6',
            modifier    = dmg_mod,
            mod_display = dmg_mod_str,
            total       = p.damage,
        )
    context = build_render_context(
        session, session.current_scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state,
        roll_result=roll_result,
        damage_result=damage_result,
    )
    context['choices'] = []
    return _htmx_response(request, context)


@require_game_session
def combat_resolve_enemy(request, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, stats, inventory, effective_stats, completed_map = session_context

    try:
        combat_state = session.combat_state
    except CombatState.DoesNotExist:
        return HttpResponse("No active combat.", status=400)

    if not combat_state.is_active or not combat_state.enemy_attack_pending:
        return HttpResponse("No pending enemy attack.", status=400)

    enemy          = combat_state.enemy
    encounter      = CombatEncounter.objects.get(scene=session.current_scene)
    player_defense = 10 + stat_modifier(effective_stats.agility)
    e_mod_str      = f"+{enemy.attack_modifier}" if enemy.attack_modifier >= 0 else str(enemy.attack_modifier)

    e_roll  = combat_state.pending_e_roll
    e_total = combat_state.pending_e_total
    e_hit   = combat_state.pending_e_hit
    e_dmg   = combat_state.pending_e_dmg

    if e_hit:
        stats.hp = max(0, stats.hp - e_dmg)
        log_event(session,
            f"{enemy.name} comes at you — roll {e_roll} ({e_mod_str}) = {e_total} "
            f"vs {player_defense} — Hit! {e_dmg} damage."
        )
    else:
        log_event(session,
            f"{enemy.name} comes at you — roll {e_roll} ({e_mod_str}) = {e_total} "
            f"vs {player_defense} — Missed."
        )

    combat_state.pending_e_roll  = None
    combat_state.pending_e_total = None
    combat_state.pending_e_hit   = None
    combat_state.pending_e_dmg   = None
    combat_state.turn_number    += 1
    combat_state.save()
    stats.save()

    if stats.hp <= 0:
        log_event(session, "You're down. You lose consciousness.")
        context = resolve_combat_end(
            session, stats, inventory, completed_map,
            encounter.defeat_scene, combat_state,
            ending_type='defeat',
        )
        return _htmx_response(request, context)

    effective_stats = get_effective_stats(stats, inventory)
    roll_result = RollResult(
        roll        = e_roll,
        modifier    = enemy.attack_modifier,
        mod_display = e_mod_str,
        total       = e_total,
        dc          = player_defense,
        stat        = enemy.name,
        success     = e_hit,
    )
    damage_result = None
    if e_hit:
        dmg_label = f'd({enemy.damage_min}–{enemy.damage_max})'
        damage_result = DamageResult(
            die_roll    = e_dmg,
            die_label   = dmg_label,
            modifier    = 0,
            mod_display = '+0',
            total       = e_dmg,
        )
    context = build_render_context(
        session, session.current_scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state,
        roll_result=roll_result,
        damage_result=damage_result,
    )
    context['choices'] = []
    return _htmx_response(request, context)


@require_game_session
def combat_continue(request, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, stats, inventory, effective_stats, completed_map = session_context

    try:
        combat_state = session.combat_state
    except CombatState.DoesNotExist:
        return HttpResponse("No combat state.", status=400)

    if not combat_state.pending_victory:
        return HttpResponse("No pending victory.", status=400)

    encounter = CombatEncounter.objects.get(scene=session.current_scene)
    context = resolve_combat_end(
        session, stats, inventory, completed_map,
        encounter.victory_scene, combat_state,
        xp_award=XP_AWARDS['combat_victory'],
        ending_type='victory',
    )
    return _htmx_response(request, context)


@require_game_session
def level_up(request, *, session_context):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session, stats, inventory, effective_stats, completed_map = session_context

    stat_name = request.POST.get('stat', '')
    try:
        public_name, _field, new_value = spend_stat_point(stats, stat_name, STAT_FIELD_MAP)
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)

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

    session, stats, inventory, effective_stats, completed_map = session_context
    item = get_object_or_404(Item, pk=item_id)

    if item.id not in inventory:
        return HttpResponse("Item not in stash.", status=400)
    if not item.effect_type:
        return HttpResponse("Item has no usable effect.", status=400)

    if item.effect_type == 'heal_hp':
        healed = min(item.effect_value, stats.max_hp - stats.hp)
        stats.hp = min(stats.max_hp, stats.hp + item.effect_value)
        stats.save()
        log_event(session, f"{USE_ITEM_FLAVOR['heal_hp']} (+{healed} HP)")

    elif item.effect_type == 'add_stat':
        if item.effect_stat:
            current = getattr(stats, item.effect_stat, 0)
            setattr(stats, item.effect_stat, current + item.effect_value)
            stats.save()
        log_event(session, USE_ITEM_FLAVOR['add_stat'])

    if item.is_consumable:
        consume_item_util(session, item, inventory)

    scene           = session.current_scene
    effective_stats = get_effective_stats(stats, inventory)
    combat_state    = get_active_combat_state(session)

    context = build_render_context(
        session, scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state,
    )
    return _htmx_response(request, context)
