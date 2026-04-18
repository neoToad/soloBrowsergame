import json
from collections import defaultdict

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseNotAllowed
from django.template.loader import render_to_string
from django.urls import reverse
from .models import (
    Arc, Choice, CombatEncounter, CombatState, CompletedQuest, EventLog,
    GameSession, Item, PlayerContext, PlayerProperty, Quest, Requirement,
    RivalClaim, Scene, Property,
)
from .models.events import log_event
from .models.combat import Enemy as EnemyModel
from .services.session     import load_session_context, create_session, get_completed_map, build_render_context
from .services.scene       import get_available_choices, complete_scene, get_notice_board, resolve_roll
from .services.combat      import get_or_create_combat_state, get_active_combat_state, resolve_combat_end, resolve_player_attack as resolve_player_attack_util, resolve_enemy_attack as resolve_enemy_attack_util
from .services.inventory   import get_player_inventory, award_scene_items, consume_item as consume_item_util
from .services.flags import set_flag, clear_flag
from .services.property_service import (
    check_rival_contests,
    get_turn_summary,
    process_turn_income,
    resolve_contest,
    apply_property_rewards,
)
from .services.progression import award_xp, maybe_complete_quest, apply_stat_rewards, XP_AWARDS, LEVEL_UP_FLAVOR
from .services.quest_builder import (
    get_canvas_data,
    validate_quest as validate_quest_service,
    create_scene as create_scene_service,
    update_scene as update_scene_service,
    delete_scene as delete_scene_service,
    get_delete_scene_consequences as get_delete_scene_consequences_service,
    create_choice as create_choice_service,
    update_choice as update_choice_service,
    delete_choice as delete_choice_service,
    save_scene_position as save_scene_position_service,
    update_scene_items as update_scene_items_service,
    update_combat_encounter as update_combat_encounter_service,
    build_requirement_groups_from_post as build_requirement_groups_from_post_service,
)
from .utils import (
    roll_d20, stat_modifier,
    get_effective_stats,
)
from .constants import (
    HUB_START_SCENE_KEY,
    SESSION_KEY,
    STAT_FIELD_MAP,
    USE_ITEM_FLAVOR,
)

def _htmx_response(request, context):
    """
    Renders the five core game partials and returns them as a single HttpResponse.
    Used for HTMX-based partial updates.
    """
    scene_html     = render_to_string('game/partials/scene_panel.html',      context, request)
    stats_html     = render_to_string('game/partials/stats_bar.html',        context, request)
    log_html       = render_to_string('game/partials/event_log.html',        context, request)
    inventory_html = render_to_string('game/partials/inventory.html',        context, request)
    mobile_html    = render_to_string('game/partials/mobile_stats_bar.html', context, request)
    return HttpResponse(scene_html + stats_html + log_html + inventory_html + mobile_html)


def _choice_context(*, quest, quest_id, choice=None, source_scene_id=None, routing_type='direct'):
    scenes = list(
        quest.scenes
        .only('id', 'key', 'title', 'scene_type')
        .order_by('order')
    )
    quest_scene_ids = {s.id for s in scenes}
    hub_scenes = list(
        Scene.objects.filter(scene_type='hub')
        .exclude(pk__in=quest_scene_ids)
        .only('id', 'key', 'title')
        .order_by('title')
    )
    source_scene = (
        Scene.objects.filter(pk=source_scene_id).only('id', 'scene_type').first()
        if source_scene_id else None
    )
    requirement_groups = (
        list(choice.requirements.prefetch_related('requirements').all())
        if choice else []
    )
    req_save_url = (
        reverse('admin:quest_builder_choice_requirements_save', args=[quest_id, choice.id])
        if choice else ''
    )
    return {
        'quest_id': quest_id,
        'source_scene_id': source_scene_id,
        'source_scene': source_scene,
        'choice': choice,
        'scenes': scenes,
        'hub_scenes': hub_scenes,
        'routing_type': routing_type,
        'requirement_groups': requirement_groups,
        'req_save_url': req_save_url,
        'all_quests': list(Quest.objects.order_by('title')),
        'all_items': list(Item.objects.order_by('name')),
        'stat_choices': [(v, k) for k, v in STAT_FIELD_MAP.items()],
        'requirement_types': Requirement.CONDITION_TYPES,
    }

def game_hub(request):
    session_pk = request.session.get(SESSION_KEY)

    if not session_pk:
        create_session(request)
    else:
        # Check if the session actually exists in DB
        try:
            GameSession.objects.get(pk=session_pk)
        except GameSession.DoesNotExist:
            create_session(request)

    return redirect('scene_detail', scene_key=HUB_START_SCENE_KEY)

def scene_detail(request, scene_key):
    session_pk = request.session.get(SESSION_KEY)
    if not session_pk:
        return redirect('/game/')

    game_session, stats, inventory, effective_stats, completed_map = load_session_context(session_pk)
    scene        = get_object_or_404(Scene, key=scene_key)
    combat_state = get_or_create_combat_state(game_session, scene)

    choices = get_available_choices(scene, effective_stats, inventory, completed_map, flags=game_session.flags)
    logs    = game_session.log.all()[:10]

    notice_board = None
    if scene.is_hub:
        notice_board = get_notice_board(scene, inventory, completed_map, effective_stats, flags=game_session.flags)

    player_properties = PlayerProperty.objects.filter(session=game_session).select_related('property')
    context = {
        'session':           game_session,
        'scene':             scene,
        'stats':             stats,
        'stat_bonuses':      effective_stats.bonuses,
        'inventory':         inventory,
        'choices':           choices,
        'logs':              logs,
        'combat_state':      combat_state,
        'notice_board':      notice_board,
        'player_properties': player_properties,
    }
    return render(request, 'game/scene.html', context)

def choice_resolve(request, choice_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get(SESSION_KEY)
    if not session_pk:
        return redirect('game_hub')

    session, stats, inventory, effective_stats, completed_map = load_session_context(session_pk)
    choice    = get_object_or_404(Choice, pk=choice_id)
    if choice.scene_id != session.current_scene_id:
        return HttpResponse("Choice is not available from your current scene.", status=403)

    scene       = choice.scene
    next_scene  = None
    roll_result = None

    # ROLL LOGIC — use effective_stats so passive bonuses apply
    if scene.requires_roll:
        next_scene, roll_log, roll_result = resolve_roll(scene, choice, effective_stats)
        log_event(session, roll_log)
    else:
        next_scene = choice.target_scene

    # ARRIVAL FLAVOR
    if scene.requires_roll and not roll_result['success'] and choice.failure_arrival_flavor:
        log_event(session, choice.failure_arrival_flavor)
    elif choice.arrival_flavor:
        log_event(session, choice.arrival_flavor)

    # FLAG EFFECTS
    if choice.set_flag_name:
        set_flag(session, choice.set_flag_name)
    if choice.clear_flag_name:
        clear_flag(session, choice.clear_flag_name)

    # ADVANCE SESSION
    session.current_scene = next_scene
    session.save()

    # SCENE REWARDS (on arrival at next_scene)
    scene_reward_logs = apply_stat_rewards(session, stats, next_scene)
    for log_text in scene_reward_logs:
        log_event(session, log_text)

    # PROPERTY REWARDS
    property_logs = apply_property_rewards(session, next_scene)
    for log_text in property_logs:
        log_event(session, log_text)

    # SCENE UNLOCK + SCENE ARRIVAL (consume_item fires here via complete_scene)
    unlock_logs = complete_scene(session, scene, choice, inventory, next_scene=next_scene)
    for log_text in unlock_logs:
        log_event(session, log_text)

    # QUEST COMPLETION
    quest_logs = maybe_complete_quest(session, stats, next_scene, completed_map)
    for log_text in quest_logs:
        log_event(session, log_text)

    # AWARD SCENE ITEMS
    awarded = award_scene_items(session, next_scene, inventory)
    for item, qty in awarded:
        log_event(session, f"You picked up: {item.name} x{qty}.")

    # PROPERTY TURN (fires once per quest completion)
    turn_summary = None
    if quest_logs:
        # Resolve an active contest if this scene was its resolution
        active_claim = RivalClaim.objects.filter(
            player_property__session=session,
            resolution_scene=next_scene,
        ).first()
        if active_claim:
            contest_log = resolve_contest(session, active_claim, next_scene.ending_type)
            log_event(session, contest_log)

        # Apply passive property income
        income_logs, income_totals = process_turn_income(session)
        for log in income_logs:
            log_event(session, log)

        # Roll for new rival contests
        contest_warning, unlocked_scene = check_rival_contests(session)
        newly_unlocked_scenes = [unlocked_scene] if unlocked_scene else []
        if contest_warning:
            log_event(session, contest_warning)

        turn_summary = get_turn_summary(session, income_totals, newly_unlocked_scenes)

    combat_state    = get_or_create_combat_state(session, next_scene)
    effective_stats = get_effective_stats(stats, inventory)   # recompute after item changes

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


def start_quest(request, quest_key):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    session_pk = request.session.get(SESSION_KEY)
    if not session_pk:
        return redirect('game_hub')
    session, stats, inventory, effective_stats, completed_map = \
        load_session_context(session_pk)
    quest = get_object_or_404(Quest, key=quest_key, is_unlocked=True)
    # Gate: evaluate quest requirements
    ctx = PlayerContext(stats=effective_stats, inventory=inventory,
                        completed_map=completed_map, flags=session.flags)
    if quest.requirements.exists():
        if not all(rg.evaluate(ctx) for rg in quest.requirements.all()):
            return HttpResponse("Quest requirements not met.", status=403)
    next_scene = quest.entrance_scene
    session.current_scene = next_scene
    session.save()
    log_event(session, f"You took the job: {quest.title}.")

    # SCENE REWARDS (on arrival at next_scene)
    scene_reward_logs = apply_stat_rewards(session, stats, next_scene)
    for log_text in scene_reward_logs:
        log_event(session, log_text)

    # PROPERTY REWARDS
    property_logs = apply_property_rewards(session, next_scene)
    for log_text in property_logs:
        log_event(session, log_text)

    awarded = award_scene_items(session, next_scene, inventory)
    for item, qty in awarded:
        log_event(session, f"You picked up: {item.name} x{qty}.")
    combat_state    = get_or_create_combat_state(session, next_scene)
    effective_stats = get_effective_stats(stats, inventory)
    is_htmx = request.headers.get('HX-Request') == 'true'
    if is_htmx:
        context = build_render_context(
            session, next_scene, stats, effective_stats, inventory,
            completed_map, combat_state=combat_state,
        )
        return _htmx_response(request, context)
    return redirect('scene_detail', scene_key=next_scene.key)

def combat_attack(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get(SESSION_KEY)
    if not session_pk:
        return redirect('game_hub')

    session, stats, inventory, effective_stats, completed_map = load_session_context(session_pk)

    try:
        combat_state = session.combat_state
    except CombatState.DoesNotExist:
        return HttpResponse("No active combat.", status=400)

    if not combat_state.is_active:
        return HttpResponse("Combat is not active.", status=400)

    enemy         = combat_state.enemy
    encounter = CombatEncounter.objects.get(scene=session.current_scene)

    # ── PLAYER ATTACKS ──────────────────────────────────────────────
    p_hit, p_dmg, p_roll, p_total = resolve_player_attack_util(effective_stats, enemy)
    str_mod = stat_modifier(effective_stats.strength)
    mod_str = f"+{str_mod}" if str_mod >= 0 else str(str_mod)

    if p_hit:
        combat_state.enemy_hp = max(0, combat_state.enemy_hp - p_dmg)
        combat_state.save()

    # ── CHECK: OPPONENT DOWN ─────────────────────────────────────────
    if combat_state.enemy_hp <= 0:
        if p_hit:
            log_event(session,
                f"You move on him — roll {p_roll} ({mod_str}) = {p_total} "
                f"vs {enemy.defense} — Hit! {p_dmg} damage."
            )
        log_event(session, f"{enemy.name} goes down. You walk away.")
        context = resolve_combat_end(
            session, stats, inventory, completed_map,
            encounter.victory_scene, combat_state,
            xp_award=XP_AWARDS['combat_victory'],
            ending_type='victory',
        )
        return _htmx_response(request, context)

    # ── PRE-ROLL ENEMY ATTACK AND WAIT FOR PLAYER TO RESOLVE ────────
    e_hit, e_dmg, e_roll, e_total = resolve_enemy_attack_util(enemy, effective_stats)

    if p_hit:
        log_event(session,
            f"You move on him — roll {p_roll} ({mod_str}) = {p_total} "
            f"vs {enemy.defense} — Hit! {p_dmg} damage."
        )
    else:
        log_event(session,
            f"You move on him — roll {p_roll} ({mod_str}) = {p_total} "
            f"vs {enemy.defense} — Missed."
        )

    combat_state.pending_e_roll  = e_roll
    combat_state.pending_e_total = e_total
    combat_state.pending_e_hit   = e_hit
    combat_state.pending_e_dmg   = e_dmg
    combat_state.save()

    effective_stats = get_effective_stats(stats, inventory)
    roll_result = {
        'roll':        p_roll,
        'modifier':    str_mod,
        'mod_display': mod_str,
        'total':       p_total,
        'dc':          enemy.defense,
        'stat':        'strength',
        'success':     p_hit,
    }
    context = build_render_context(
        session, session.current_scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state,
        roll_result=roll_result,
    )
    context['choices'] = []
    return _htmx_response(request, context)


def combat_resolve_enemy(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get(SESSION_KEY)
    if not session_pk:
        return redirect('game_hub')

    session, stats, inventory, effective_stats, completed_map = load_session_context(session_pk)

    try:
        combat_state = session.combat_state
    except CombatState.DoesNotExist:
        return HttpResponse("No active combat.", status=400)

    if not combat_state.is_active or not combat_state.enemy_attack_pending:
        return HttpResponse("No pending enemy attack.", status=400)

    enemy         = combat_state.enemy
    encounter     = CombatEncounter.objects.get(scene=session.current_scene)
    player_defense = 10 + stat_modifier(effective_stats.agility)
    e_mod_str = f"+{enemy.attack_modifier}" if enemy.attack_modifier >= 0 else str(enemy.attack_modifier)

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
    e_mod_display = f"+{enemy.attack_modifier}" if enemy.attack_modifier >= 0 else str(enemy.attack_modifier)
    roll_result = {
        'roll':        e_roll,
        'modifier':    enemy.attack_modifier,
        'mod_display': e_mod_display,
        'total':       e_total,
        'dc':          player_defense,
        'stat':        enemy.name,
        'success':     e_hit,
    }
    context = build_render_context(
        session, session.current_scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state,
        roll_result=roll_result,
    )
    context['choices'] = []
    return _htmx_response(request, context)


def level_up(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get(SESSION_KEY)
    if not session_pk:
        return redirect('game_hub')

    session, stats, inventory, effective_stats, completed_map = load_session_context(session_pk)

    if stats.stat_points <= 0:
        return HttpResponse("No stat points available.", status=400)

    stat_name = request.POST.get('stat', '').lower()
    field = STAT_FIELD_MAP.get(stat_name)
    if not field:
        return HttpResponse("Invalid stat.", status=400)

    current_val = getattr(stats, field)
    setattr(stats, field, current_val + 1)
    stats.stat_points -= 1
    stats.save()

    log_event(session, f"{stat_name.upper()} increased to {current_val + 1}.")

    scene           = session.current_scene
    effective_stats = get_effective_stats(stats, inventory)

    # Preserve active combat state if one exists
    combat_state = get_active_combat_state(session)

    context = build_render_context(
        session, scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state,
    )

    return _htmx_response(request, context)


def quest_validate(request, quest_id):
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    get_object_or_404(Quest, pk=quest_id)
    warnings = validate_quest_service(quest_id)

    html = render_to_string(
        'admin/quest_builder/partials/validation_panel.html',
        {'warnings': warnings},
        request=request,
    )
    return HttpResponse(html)


def quest_builder_list(request):
    """
    Queries all Quest objects, ordered by arc then title.
    Renders game/templates/admin/quest_builder/list.html.
    Passes quests grouped by Arc to the template.
    """
    quests = Quest.objects.select_related('arc').order_by('arc__order', 'arc_order', 'title')
    
    # Group by Arc
    quests_by_arc = defaultdict(list)
    for q in quests:
        arc_title = q.arc.title if q.arc else "No Arc"
        quests_by_arc[arc_title].append(q)
    
    context = {
        'quests_by_arc': dict(quests_by_arc),
        'title': 'Quest Builder',
    }
    return render(request, 'admin/quest_builder/list.html', context)


def quest_builder_canvas(request, quest_id):
    """
    Calls get_canvas_data(quest_id).
    Renders game/templates/admin/quest_builder/canvas.html.
    Passes the canvas data to the template.
    """
    canvas_data = get_canvas_data(quest_id)
    context = {
        **canvas_data,
        'title': f"Quest Builder - {canvas_data['quest'].title}",
    }
    return render(request, 'admin/quest_builder/canvas.html', context)


def scene_panel(request, quest_id, scene_id=None):
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    quest = get_object_or_404(Quest, pk=quest_id)
    scene = None
    scene_choices = []
    scene_items = []
    combat_encounter = None
    if scene_id is not None:
        scene = get_object_or_404(quest.scenes.all(), pk=scene_id)
        scene_choices = list(
            Choice.objects.filter(scene=scene)
            .select_related('target_scene', 'success_scene', 'failure_scene')
            .order_by('order')
        )
        scene_items = list(
            scene.scene_items.select_related('item').order_by('id')
        )
        try:
            combat_encounter = scene.combat_encounter
        except Exception:
            combat_encounter = None

    all_items = list(Item.objects.order_by('name'))
    all_enemies = list(EnemyModel.objects.order_by('name'))
    all_quests = list(Quest.objects.order_by('title'))
    all_properties = list(Property.objects.order_by('name'))
    quest_scenes = list(
        quest.scenes.only('id', 'key', 'title').order_by('order')
    )

    context = {
        'quest_id': quest_id,
        'scene': scene,
        'scene_choices': scene_choices,
        'scene_types': Scene.SCENE_TYPES,
        'roll_stat_options': [
            ('strength', 'muscle'),
            ('agility', 'reflexes'),
            ('intellect', 'cunning'),
            ('charisma', 'nerve'),
        ],
        'default_roll_difficulty': 12,
        'scene_items': scene_items,
        'all_items': all_items,
        'all_enemies': all_enemies,
        'all_properties': all_properties,
        'quest_scenes': quest_scenes,
        'combat_encounter': combat_encounter,
        'all_quests': all_quests,
        'stat_choices': [(v, k) for k, v in STAT_FIELD_MAP.items()],
        'requirement_types': Requirement.CONDITION_TYPES,
    }
    return render(request, 'admin/quest_builder/partials/scene_panel.html', context)


def scene_save(request, quest_id, scene_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    get_object_or_404(quest.scenes.all(), pk=scene_id)
    try:
        scene = update_scene_service(scene_id, request.POST)
    except ValueError as exc:
        html = render_to_string(
            'admin/quest_builder/partials/inline_error.html',
            {'error_message': str(exc)},
            request=request,
        )
        return HttpResponse(html, status=400)

    html = render_to_string(
        'admin/quest_builder/partials/scene_save_response.html',
        {
            'scene': scene,
            'quest_id': quest_id,
            'toast_message': f'Scene "{scene.title}" saved.',
        },
        request=request,
    )
    response = HttpResponse(html)
    response['HX-Trigger'] = json.dumps({'sceneUpdated': {'sceneId': scene.id}})
    return response


def scene_create(request, quest_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    get_object_or_404(Quest, pk=quest_id)
    try:
        scene = create_scene_service(quest_id, request.POST)
    except ValueError as exc:
        html = render_to_string(
            'admin/quest_builder/partials/inline_error.html',
            {'error_message': str(exc)},
            request=request,
        )
        return HttpResponse(html, status=400)

    html = render_to_string(
        'admin/quest_builder/partials/scene_create_response.html',
        {
            'scene': scene,
            'quest_id': quest_id,
            'toast_message': f'Scene "{scene.title}" created.',
        },
        request=request,
    )
    response = HttpResponse(html)
    response['HX-Trigger'] = json.dumps({'sceneUpdated': {'sceneId': scene.id}})
    return response


def scene_delete(request, quest_id, scene_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    scene = get_object_or_404(quest.scenes.all(), pk=scene_id)

    # Two-step delete: first POST shows confirmation; second POST with confirmed=1 does the delete.
    if request.POST.get('confirmed') != '1':
        consequences = get_delete_scene_consequences_service(scene_id)
        html = render_to_string(
            'admin/quest_builder/partials/scene_delete_confirm.html',
            {
                'scene': scene,
                'quest_id': quest_id,
                'affected_choices': consequences['affected_choices'],
                'victory_encounters': consequences['victory_encounters'],
                'defeat_encounters': consequences['defeat_encounters'],
            },
            request=request,
        )
        return HttpResponse(html)

    affected_choice_ids = delete_scene_service(scene_id)

    html = render_to_string(
        'admin/quest_builder/partials/scene_delete_response.html',
        {
            'scene_id': scene_id,
            'scene_title': scene.title,
            'affected_choice_ids': affected_choice_ids,
        },
        request=request,
    )
    response = HttpResponse(html)
    response['HX-Trigger'] = json.dumps({'sceneUpdated': {'sceneId': scene_id}})
    return response


def scene_move(request, quest_id, scene_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    get_object_or_404(quest.scenes.all(), pk=scene_id)

    try:
        x = int((request.POST.get('x') or '').strip())
        y = int((request.POST.get('y') or '').strip())
    except (TypeError, ValueError):
        return HttpResponse("x and y must be integers", status=400)

    save_scene_position_service(scene_id, x, y)
    return HttpResponse(status=204)


def scene_items_save(request, quest_id, scene_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    scene = get_object_or_404(quest.scenes.all(), pk=scene_id)

    # Parse indexed POST fields: item_id_0, quantity_0, item_id_1, quantity_1, ...
    items_data = []
    index = 0
    while True:
        item_id_key = f'item_id_{index}'
        qty_key = f'quantity_{index}'
        if item_id_key not in request.POST and qty_key not in request.POST:
            break
        items_data.append({
            'item_id':  request.POST.get(item_id_key, ''),
            'quantity': request.POST.get(qty_key, '1'),
        })
        index += 1

    scene_items = update_scene_items_service(scene.id, items_data)
    all_items = list(Item.objects.order_by('name'))

    html = render_to_string(
        'admin/quest_builder/partials/items_section.html',
        {
            'quest_id': quest_id,
            'scene': scene,
            'scene_items': scene_items,
            'all_items': all_items,
            'toast_message': 'Items saved.',
        },
        request=request,
    )
    return HttpResponse(html)


def scene_combat_save(request, quest_id, scene_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    scene = get_object_or_404(quest.scenes.all(), pk=scene_id)

    encounter = update_combat_encounter_service(scene.id, request.POST)
    all_enemies = list(EnemyModel.objects.order_by('name'))
    quest_scenes = list(
        quest.scenes.only('id', 'key', 'title').order_by('order')
    )

    html = render_to_string(
        'admin/quest_builder/partials/combat_section.html',
        {
            'quest_id': quest_id,
            'scene': scene,
            'combat_encounter': encounter,
            'all_enemies': all_enemies,
            'quest_scenes': quest_scenes,
            'toast_message': 'Combat encounter saved.',
        },
        request=request,
    )
    return HttpResponse(html)


def choice_panel(request, quest_id, source_scene_id=None, choice_id=None):
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    quest = get_object_or_404(Quest, pk=quest_id)
    choice = None
    routing_type = 'direct'

    if choice_id is not None:
        choice = get_object_or_404(Choice, pk=choice_id)
        source_scene_id = choice.scene_id
        if choice.success_scene_id or choice.failure_scene_id:
            routing_type = 'roll'

    context = _choice_context(
        quest=quest,
        quest_id=quest_id,
        choice=choice,
        source_scene_id=source_scene_id,
        routing_type=routing_type,
    )
    return render(request, 'admin/quest_builder/partials/choice_panel.html', context)


def choice_create(request, quest_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    raw_source = (request.POST.get('source_scene_id') or '').strip()
    if not raw_source:
        return HttpResponse("source_scene_id required", status=400)

    choice = create_choice_service(int(raw_source), request.POST)
    routing_type = 'roll' if (choice.success_scene_id or choice.failure_scene_id) else 'direct'

    context = _choice_context(
        quest=quest,
        quest_id=quest_id,
        choice=choice,
        source_scene_id=choice.scene_id,
        routing_type=routing_type,
    )
    html = render_to_string(
        'admin/quest_builder/partials/choice_panel.html',
        context,
        request=request,
    )
    response = HttpResponse(html)
    response['HX-Trigger'] = json.dumps({
        'choiceCreated': {
            'id': choice.id,
            'quest_id': quest_id,
            'source_scene_id': choice.scene_id,
            'routing_type': routing_type,
            'target_scene_id': choice.target_scene_id,
            'success_scene_id': choice.success_scene_id,
            'failure_scene_id': choice.failure_scene_id,
            'label': choice.label,
        }
    })
    return response


def choice_save(request, quest_id, choice_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    get_object_or_404(Choice, pk=choice_id)
    choice = update_choice_service(choice_id, request.POST)
    build_requirement_groups_from_post_service(choice, request.POST)
    routing_type = 'roll' if (choice.success_scene_id or choice.failure_scene_id) else 'direct'

    response = HttpResponse('')
    response['HX-Trigger'] = json.dumps({
        'choiceUpdated': {
            'id': choice.id,
            'source_scene_id': choice.scene_id,
            'routing_type': routing_type,
            'target_scene_id': choice.target_scene_id,
            'success_scene_id': choice.success_scene_id,
            'failure_scene_id': choice.failure_scene_id,
            'label': choice.label,
        }
    })
    return response


def choice_delete(request, quest_id, choice_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    get_object_or_404(Choice, pk=choice_id)
    source_scene_id = delete_choice_service(choice_id)

    response = HttpResponse('')
    response['HX-Trigger'] = json.dumps({
        'choiceDeleted': {
            'id': choice_id,
            'source_scene_id': source_scene_id,
        }
    })
    return response


def choice_requirements_save(request, quest_id, choice_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    choice = get_object_or_404(Choice, pk=choice_id)
    build_requirement_groups_from_post_service(choice, request.POST)

    html = render_to_string(
        'admin/quest_builder/partials/requirements_section.html',
        {
            'quest_id': quest_id,
            'requirement_groups': list(choice.requirements.prefetch_related('requirements').all()),
            'save_url': reverse('admin:quest_builder_choice_requirements_save', args=[quest_id, choice_id]),
            'all_quests': list(Quest.objects.order_by('title')),
            'all_items': list(Item.objects.order_by('name')),
            'stat_choices': [(v, k) for k, v in STAT_FIELD_MAP.items()],
            'requirement_types': Requirement.CONDITION_TYPES,
            'toast_message': 'Requirements saved.',
        },
        request=request,
    )
    return HttpResponse(html)


def use_item(request, item_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get(SESSION_KEY)
    if not session_pk:
        return redirect('game_hub')

    session, stats, inventory, effective_stats, completed_map = load_session_context(session_pk)
    item    = get_object_or_404(Item, pk=item_id)

    # Guard: player must actually hold the item
    if item.id not in inventory:
        return HttpResponse("Item not in stash.", status=400)

    # Guard: item must have an active effect
    if not item.effect_type:
        return HttpResponse("Item has no usable effect.", status=400)

    # ── APPLY EFFECT ────────────────────────────────────────────────
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

    # ── CONSUME IF CONSUMABLE ────────────────────────────────────────
    if item.is_consumable:
        consume_item_util(session, item, inventory)

    # ── BUILD RESPONSE ───────────────────────────────────────────────
    scene           = session.current_scene
    effective_stats = get_effective_stats(stats, inventory)

    combat_state = get_active_combat_state(session)

    context = build_render_context(
        session, scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state,
    )
    return _htmx_response(request, context)
