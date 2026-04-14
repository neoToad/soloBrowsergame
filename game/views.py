from django.shortcuts import render, redirect, get_object_or_404
import json

from django.http import HttpResponse, HttpResponseNotAllowed
from django.template.loader import render_to_string
from .models import (
    GameSession, PlayerStats, Quest, Scene, Choice, EventLog,
    CompletedQuest, CombatState, PlayerContext,
)
from .models.events import log_event
from .services.session     import load_session_context, create_session, get_completed_map, build_render_context
from .services.scene       import get_available_choices, complete_scene, get_notice_board, resolve_roll
from .services.combat      import get_or_create_combat_state, get_active_combat_state, resolve_combat_end, resolve_player_attack as resolve_player_attack_util, resolve_enemy_attack as resolve_enemy_attack_util
from .services.inventory   import get_player_inventory, award_scene_items, consume_item as consume_item_util
from .services.progression import award_xp, maybe_complete_quest, XP_AWARDS, LEVEL_UP_FLAVOR
from .services.quest_builder import (
    get_canvas_data,
    create_scene as create_scene_service,
    update_scene as update_scene_service,
    delete_scene as delete_scene_service,
)
from .utils import (
    roll_d20, stat_modifier,
    get_effective_stats,
)
from .constants import (
    HUB_START_SCENE_KEY, NOTICE_BOARD_SCENE_KEY,
    STAT_FIELD_MAP, USE_ITEM_FLAVOR,
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

def game_hub(request):
    session_pk = request.session.get('game_session_id')

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
    session_pk = request.session.get('game_session_id')
    if not session_pk:
        return redirect('/game/')

    game_session, stats, inventory, effective_stats, completed_map = load_session_context(session_pk)
    scene        = get_object_or_404(Scene, key=scene_key)
    combat_state = get_or_create_combat_state(game_session, scene)

    choices = get_available_choices(scene, effective_stats, inventory, completed_map, flags=game_session.flags)
    logs    = game_session.log.all()[:10]

    notice_board = None
    if scene.key == NOTICE_BOARD_SCENE_KEY:
        notice_board = get_notice_board(inventory, completed_map, effective_stats, flags=game_session.flags)

    from .models.property import PlayerProperty
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

    session_pk = request.session.get('game_session_id')
    if not session_pk:
        return redirect('game_hub')

    session, stats, inventory, effective_stats, completed_map = load_session_context(session_pk)
    choice    = get_object_or_404(Choice, pk=choice_id)

    scene      = choice.scene
    next_scene = None

    # ROLL LOGIC — use effective_stats so passive bonuses apply
    if scene.requires_roll:
        next_scene, roll_log = resolve_roll(scene, choice, effective_stats)
        log_event(session, roll_log)
    else:
        next_scene = choice.target_scene

    # ARRIVAL FLAVOR
    if choice.arrival_flavor:
        log_event(session, choice.arrival_flavor)

    # CONSUME ITEM (before advancing so inventory is still current)
    if choice.consume_item and choice.consume_item_id in inventory:
        consume_item_util(session, choice.consume_item, inventory)
        log_event(session, f"You used your {choice.consume_item.name}.")

    # FLAG EFFECTS
    from .services.flags import set_flag, clear_flag
    if choice.set_flag_name:
        set_flag(session, choice.set_flag_name)
    if choice.clear_flag_name:
        clear_flag(session, choice.clear_flag_name)

    # ADVANCE SESSION
    session.current_scene = next_scene
    session.save()

    # SCENE UNLOCK
    unlock_logs = complete_scene(session, scene, choice, inventory)
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
        from .services.property_service import (
            process_turn_income, check_rival_contests, resolve_contest, get_turn_summary
        )
        from .models.property import RivalClaim

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
        )
        return _htmx_response(request, context)

    return redirect('scene_detail', scene_key=next_scene.key)


def start_quest(request, quest_key):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    session_pk = request.session.get('game_session_id')
    if not session_pk:
        return redirect('game_hub')
    from .models import Quest, PlayerContext
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

    session_pk = request.session.get('game_session_id')
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

    # ── PLAYER ATTACKS ──────────────────────────────────────────────
    p_hit, p_dmg, p_roll, p_total = resolve_player_attack_util(effective_stats, enemy)
    str_mod = stat_modifier(effective_stats.strength)
    mod_str = f"+{str_mod}" if str_mod >= 0 else str(str_mod)

    if p_hit:
        combat_state.enemy_hp = max(0, combat_state.enemy_hp - p_dmg)
        combat_state.save()
        log_event(session,
            f"You move on him — roll {p_roll} ({mod_str}) = {p_total} "
            f"vs {enemy.defense} — Hit! {p_dmg} damage."
        )
    else:
        log_event(session,
            f"You move on him — roll {p_roll} ({mod_str}) = {p_total} "
            f"vs {enemy.defense} — Missed."
        )

    # ── CHECK: OPPONENT DOWN ─────────────────────────────────────────
    if combat_state.enemy_hp <= 0:
        log_event(session, f"{enemy.name} goes down. You walk away.")
        context = resolve_combat_end(
            session, stats, inventory, completed_map,
            enemy.victory_scene, combat_state,
            xp_award=XP_AWARDS['combat_victory'],
        )
        return _htmx_response(request, context)

    # ── ENEMY ATTACKS BACK ───────────────────────────────────────────
    e_hit, e_dmg, e_roll, e_total = resolve_enemy_attack_util(enemy, effective_stats)
    player_defense = 10 + stat_modifier(effective_stats.agility)
    e_mod_str = f"+{enemy.attack_modifier}" if enemy.attack_modifier >= 0 else str(enemy.attack_modifier)

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

    stats.save()

    # ── CHECK: PLAYER DOWN ───────────────────────────────────────────
    if stats.hp <= 0:
        log_event(session, "You're down. You lose consciousness.")
        context = resolve_combat_end(
            session, stats, inventory, completed_map,
            enemy.defeat_scene, combat_state,
        )
        return _htmx_response(request, context)

    effective_stats = get_effective_stats(stats, inventory)
    context = build_render_context(
        session, session.current_scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state
    )
    # Ensure choices is empty for combat
    context['choices'] = []
    return _htmx_response(request, context)


def level_up(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get('game_session_id')
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


def quest_builder_list(request):
    """
    Queries all Quest objects, ordered by arc then title.
    Renders game/templates/admin/quest_builder/list.html.
    Passes quests grouped by Arc to the template.
    """
    from .models import Quest, Arc
    quests = Quest.objects.select_related('arc').order_by('arc__order', 'arc_order', 'title')
    
    # Group by Arc
    from collections import defaultdict
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

    get_object_or_404(Quest, pk=quest_id)
    scene = None
    if scene_id is not None:
        scene = get_object_or_404(Scene, pk=scene_id, quest_id=quest_id)

    context = {
        'quest_id': quest_id,
        'scene': scene,
        'scene_types': Scene.SCENE_TYPES,
        'roll_stat_options': [
            ('strength', 'muscle'),
            ('agility', 'reflexes'),
            ('intellect', 'cunning'),
            ('charisma', 'nerve'),
        ],
        'default_roll_difficulty': 12,
    }
    return render(request, 'admin/quest_builder/partials/scene_panel.html', context)


def scene_save(request, quest_id, scene_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    get_object_or_404(Scene, pk=scene_id, quest_id=quest_id)
    scene = update_scene_service(scene_id, request.POST)

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
    scene = create_scene_service(quest_id, request.POST)

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

    scene = get_object_or_404(Scene, pk=scene_id, quest_id=quest_id)
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


def use_item(request, item_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get('game_session_id')
    if not session_pk:
        return redirect('game_hub')

    from .models import Item
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
