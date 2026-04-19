from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseNotAllowed
from django.template.loader import render_to_string

from .models import (
    Choice, CombatEncounter, CombatState, GameSession, Item,
    PlayerContext, PlayerProperty, Quest, Scene,
)
from .models.property import Property
from .models.events import log_event, flush_event_log
from .services.session     import load_session_context, create_session, build_render_context
from .services.scene       import get_available_choices, get_notice_board, resolve_roll
from .services.combat      import (
    initialize_combat_state, get_active_combat_state, resolve_combat_end,
    resolve_player_attack as resolve_player_attack_util,
    resolve_enemy_attack as resolve_enemy_attack_util,
)
from .services.inventory   import get_player_inventory, consume_item as consume_item_util
from .services.flags       import set_flag, clear_flag
from .services.arrival     import process_arrival
from .services.progression import XP_AWARDS, LEVEL_UP_FLAVOR
from .utils import roll_d20, stat_modifier, get_effective_stats, RollResult
from .constants import HUB_START_SCENE_KEY, SESSION_KEY, STAT_FIELD_MAP, USE_ITEM_FLAVOR


def _htmx_response(request, context):
    scene_html       = render_to_string('game/partials/scene_panel.html',      context, request)
    stats_html       = render_to_string('game/partials/stats_bar.html',        context, request)
    log_html         = render_to_string('game/partials/event_log.html',        context, request)
    inventory_html   = render_to_string('game/partials/inventory.html',        context, request)
    mobile_html      = render_to_string('game/partials/mobile_stats_bar.html', context, request)
    territories_html = render_to_string('game/partials/territories.html',      context, request)
    response = HttpResponse(scene_html + stats_html + log_html + inventory_html + mobile_html + territories_html)
    scene = context.get('scene')
    if scene:
        from django.urls import reverse
        response['HX-Push-Url'] = reverse('scene_detail', kwargs={'scene_key': scene.key})
    return response


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


def scene_detail(request, scene_key):
    session_pk = request.session.get(SESSION_KEY)
    if not session_pk:
        return redirect('/game/')

    game_session, stats, inventory, effective_stats, completed_map = load_session_context(session_pk)
    scene        = get_object_or_404(Scene, key=scene_key)
    combat_state = initialize_combat_state(game_session, scene)

    choices = get_available_choices(scene, effective_stats, inventory, completed_map, flags=game_session.flags)
    logs    = game_session.log.all()[:10]

    notice_board = None
    if scene.is_hub:
        notice_board = get_notice_board(scene, inventory, completed_map, effective_stats, flags=game_session.flags)

    player_properties = PlayerProperty.objects.filter(session=game_session).select_related('property')
    all_territories   = Property.objects.filter(property_type='territory')
    owned_territory_ids = {
        pp.property_id for pp in player_properties if pp.property.property_type == 'territory'
    }
    context = {
        'session':              game_session,
        'scene':                scene,
        'stats':                stats,
        'stat_bonuses':         effective_stats.bonuses,
        'inventory':            inventory,
        'choices':              choices,
        'logs':                 logs,
        'combat_state':         combat_state,
        'notice_board':         notice_board,
        'player_properties':    player_properties,
        'all_territories':      all_territories,
        'owned_territory_ids':  owned_territory_ids,
    }
    return render(request, 'game/scene.html', context)


def choice_resolve(request, choice_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get(SESSION_KEY)
    if not session_pk:
        return redirect('game_hub')

    session, stats, inventory, effective_stats, completed_map = load_session_context(session_pk)
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
        next_scene, roll_result = choice.target_scene, None

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

    combat_state    = initialize_combat_state(session, next_scene)
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


def start_quest(request, quest_key):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get(SESSION_KEY)
    if not session_pk:
        return redirect('game_hub')

    session, stats, inventory, effective_stats, completed_map = load_session_context(session_pk)
    quest = get_object_or_404(Quest, key=quest_key, is_unlocked=True)

    ctx = PlayerContext(
        stats=effective_stats, inventory=inventory,
        completed_map=completed_map, flags=session.flags,
    )
    if quest.requirements.exists():
        if not all(rg.evaluate(ctx) for rg in quest.requirements.all()):
            return HttpResponse("Quest requirements not met.", status=403)

    next_scene = quest.entrance_scene
    session.current_scene = next_scene
    session.save()

    arrival_logs, _ = process_arrival(session, stats, inventory, completed_map, next_scene)
    flush_event_log(session, [f"You took the job: {quest.title}.", *arrival_logs])

    combat_state    = initialize_combat_state(session, next_scene)
    effective_stats = get_effective_stats(stats, inventory)

    is_htmx = request.headers.get('HX-Request') == 'true'
    if is_htmx:
        context = build_render_context(
            session, next_scene, stats, effective_stats, inventory, completed_map,
            combat_state=combat_state,
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
        log_event(session, f"{enemy.name} goes down. You walk away.")
        context = resolve_combat_end(
            session, stats, inventory, completed_map,
            encounter.victory_scene, combat_state,
            xp_award=XP_AWARDS['combat_victory'],
            ending_type='victory',
        )
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
    combat_state    = get_active_combat_state(session)

    context = build_render_context(
        session, scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state,
    )
    return _htmx_response(request, context)


def use_item(request, item_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get(SESSION_KEY)
    if not session_pk:
        return redirect('game_hub')

    session, stats, inventory, effective_stats, completed_map = load_session_context(session_pk)
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