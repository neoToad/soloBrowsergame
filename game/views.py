from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseNotAllowed
from django.template.loader import render_to_string
from .models import (
    GameSession, PlayerStats, Scene, Choice, EventLog,
    CompletedQuest, Quest, CombatState,
)
from .utils import (
    roll_d20, stat_modifier, get_notice_board,
    get_player_inventory, award_scene_items,
    consume_item as consume_item_util,
    resolve_player_attack, resolve_enemy_attack,
    award_xp, XP_AWARDS, LEVEL_UP_FLAVOR,
    get_effective_stats,
)

NOTICE_BOARD_KEY = 'hub__notice_board'

def get_available_choices(scene, stats, inventory, completed_map):
    choices = []
    for choice in scene.choices.prefetch_related('requirements__requirements').all():
        # Legacy simple stat gate (kept for backwards compatibility)
        if choice.required_stat:
            player_value = getattr(stats, choice.required_stat, 0)
            if player_value < choice.required_minimum:
                continue
        # RequirementGroup gate — all groups must pass
        if choice.requirements.exists():
            passed = all(
                rg.evaluate(stats, inventory, completed_map)
                for rg in choice.requirements.all()
            )
            if not passed:
                continue
        choices.append(choice)
    return choices


def _get_completed_map(session):
    from .models import CompletedQuest
    return {
        cq.quest_id: cq.ending_type
        for cq in CompletedQuest.objects.filter(session=session)
    }

def _get_combat_state(session, scene):
    """
    For a combat scene: returns an active CombatState, creating one if needed.
    If an inactive state exists for a combat scene, deletes and recreates it.
    For a non-combat scene: deactivates any lingering active CombatState and returns None.
    """
    from .models import CombatEncounter, CombatState
    if not scene.is_combat:
        try:
            cs = session.combat_state
            if cs.is_active:
                cs.is_active = False
                cs.save()
        except CombatState.DoesNotExist:
            pass
        return None

    try:
        cs = session.combat_state
        if cs.is_active:
            return cs
        cs.delete()
    except CombatState.DoesNotExist:
        pass

    encounter = CombatEncounter.objects.select_related('enemy').get(scene=scene)
    cs = CombatState.objects.create(
        session=session,
        enemy=encounter.enemy,
        enemy_hp=encounter.enemy.max_hp,
        turn_number=1,
        is_active=True,
    )
    EventLog.objects.create(
        session=session,
        text=f"You square up against {encounter.enemy.name}."
    )
    return cs

def game_hub(request):
    session_pk = request.session.get('game_session_id')
    
    if not session_pk:
        # Create a new session and default stats
        # session_key in GameSession is NOT the same as request.session.session_key
        # The model uses session_key as a unique identifier.
        # Let's use request.session.session_key if it exists, or a random one.
        if not request.session.session_key:
            request.session.create()
        
        game_session = GameSession.objects.create(
            session_key=request.session.session_key,
            current_scene=Scene.objects.get(key='hub__main_square')
        )
        PlayerStats.objects.create(session=game_session)
        request.session['game_session_id'] = game_session.pk
    else:
        # Check if the session actually exists in DB
        try:
            game_session = GameSession.objects.get(pk=session_pk)
        except GameSession.DoesNotExist:
            # Fallback if session_id in request.session is invalid
            if not request.session.session_key:
                request.session.create()
            game_session = GameSession.objects.create(
                session_key=request.session.session_key,
                current_scene=Scene.objects.get(key='hub__main_square')
            )
            PlayerStats.objects.create(session=game_session)
            request.session['game_session_id'] = game_session.pk

    return redirect('scene_detail', scene_key='hub__main_square')

def scene_detail(request, scene_key):
    session_pk = request.session.get('game_session_id')
    if not session_pk:
        return redirect('/game/')

    game_session  = get_object_or_404(GameSession, pk=session_pk)
    scene         = get_object_or_404(Scene, key=scene_key)
    stats         = game_session.stats
    inventory     = get_player_inventory(game_session)
    effective_stats = get_effective_stats(stats, inventory)
    completed_map = _get_completed_map(game_session)
    combat_state  = _get_combat_state(game_session, scene)

    if scene.key == NOTICE_BOARD_KEY:
        notice_board = get_notice_board(game_session, stats)
    else:
        notice_board = None

    choices = get_available_choices(scene, effective_stats, inventory, completed_map)
    logs    = game_session.log.all()[:10]

    context = {
        'session':      game_session,
        'scene':        scene,
        'stats':        stats,
        'stat_bonuses': effective_stats.bonuses,
        'inventory':    inventory,
        'choices':      choices,
        'logs':         logs,
        'notice_board': notice_board,
        'combat_state': combat_state,
    }
    return render(request, 'game/scene.html', context)

def choice_resolve(request, choice_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get('game_session_id')
    if not session_pk:
        return redirect('game_hub')

    session   = get_object_or_404(GameSession, pk=session_pk)
    choice    = get_object_or_404(Choice, pk=choice_id)
    stats     = session.stats
    inventory = get_player_inventory(session)
    effective_stats = get_effective_stats(stats, inventory)
    completed_map = _get_completed_map(session)

    scene      = choice.scene
    next_scene = None

    # ROLL LOGIC — use effective_stats so passive bonuses apply
    if scene.requires_roll:
        stat_value = getattr(effective_stats, scene.roll_stat, 10)
        modifier   = stat_modifier(stat_value)
        roll       = roll_d20()
        total      = roll + modifier
        dc         = scene.roll_difficulty
        success    = total >= dc

        mod_str = f"+ {modifier}" if modifier >= 0 else f"- {abs(modifier)}"
        res_str = "Success!" if success else "Failure."
        EventLog.objects.create(
            session=session,
            text=f"You rolled a {roll} ({mod_str} modifier) = {total} vs DC {dc} — {res_str}"
        )

        next_scene = choice.success_scene if success else choice.failure_scene
    else:
        next_scene = choice.target_scene

    # ARRIVAL FLAVOR
    if choice.arrival_flavor:
        EventLog.objects.create(session=session, text=choice.arrival_flavor)

    # CONSUME ITEM (before advancing so inventory is still current)
    if choice.consume_item and choice.consume_item_id in inventory:
        consume_item_util(session, choice.consume_item, inventory)
        EventLog.objects.create(
            session=session,
            text=f"You used your {choice.consume_item.name}."
        )

    # ADVANCE SESSION
    session.current_scene = next_scene
    session.save()

    # QUEST COMPLETION
    if next_scene.is_ending and next_scene.quest:
        if not CompletedQuest.objects.filter(session=session, quest=next_scene.quest).exists():
            CompletedQuest.objects.create(
                session=session,
                quest=next_scene.quest,
                ending_type=next_scene.ending_type
            )
            EventLog.objects.create(
                session=session,
                text=f"You have completed: {next_scene.quest.title} ({next_scene.get_ending_type_display()})"
            )
            completed_map[next_scene.quest_id] = next_scene.ending_type

            # AWARD XP
            xp_amount = XP_AWARDS.get(next_scene.ending_type, 0)
            if xp_amount:
                levels = award_xp(session, stats, xp_amount)
                EventLog.objects.create(session=session, text=f"+{xp_amount} XP.")
                for new_level in levels:
                    flavor = LEVEL_UP_FLAVOR[new_level - 2]
                    EventLog.objects.create(session=session, text=flavor)

    # AWARD SCENE ITEMS
    awarded = award_scene_items(session, next_scene, inventory)
    for item, qty in awarded:
        EventLog.objects.create(
            session=session,
            text=f"You picked up: {item.name} x{qty}."
        )

    combat_state    = _get_combat_state(session, next_scene)
    effective_stats = get_effective_stats(stats, inventory)   # recompute after item changes

    is_htmx = request.headers.get('HX-Request') == 'true'
    if is_htmx:
        if next_scene.key == NOTICE_BOARD_KEY:
            notice_board = get_notice_board(session, stats)
        else:
            notice_board = None

        context = {
            'scene':        next_scene,
            'choices':      get_available_choices(next_scene, effective_stats, inventory, completed_map),
            'stats':        stats,
            'stat_bonuses': effective_stats.bonuses,
            'inventory':    inventory,
            'logs':         session.log.all()[:10],
            'oob':          True,
            'notice_board': notice_board,
            'combat_state': combat_state,
        }
        scene_html     = render_to_string('game/partials/scene_panel.html',  context, request)
        stats_html     = render_to_string('game/partials/stats_bar.html',    context, request)
        log_html       = render_to_string('game/partials/event_log.html',    context, request)
        inventory_html = render_to_string('game/partials/inventory.html',    context, request)
        mobile_html    = render_to_string('game/partials/mobile_stats_bar.html', context, request)
        return HttpResponse(scene_html + stats_html + log_html + inventory_html + mobile_html)

    return redirect('scene_detail', scene_key=next_scene.key)

def start_quest(request, quest_key):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get('game_session_id')
    if not session_pk:
        return redirect('game_hub')

    session = get_object_or_404(GameSession, pk=session_pk)
    quest = get_object_or_404(Quest, key=quest_key)
    stats = session.stats

    # Check availability
    board = get_notice_board(session, stats)
    quest_entry = next((e for e in board if e['quest'].key == quest_key), None)

    if not quest_entry or quest_entry['status'] == 'locked':
        return HttpResponse("Quest is locked", status=403)

    next_scene = quest.entrance_scene
    if not next_scene:
        return HttpResponse("Quest has no entrance scene", status=500)

    # Log acceptance
    EventLog.objects.create(session=session, text=f"You accepted the quest: {quest.title}")

    # Advance session
    session.current_scene = next_scene
    session.save()

    is_htmx = request.headers.get('HX-Request') == 'true'
    if is_htmx:
        inventory       = get_player_inventory(session)
        completed_map   = _get_completed_map(session)

        awarded = award_scene_items(session, next_scene, inventory)
        for item, qty in awarded:
            EventLog.objects.create(
                session=session,
                text=f"You picked up: {item.name} x{qty}."
            )

        combat_state    = _get_combat_state(session, next_scene)
        effective_stats = get_effective_stats(stats, inventory)

        context = {
            'scene':        next_scene,
            'choices':      get_available_choices(next_scene, effective_stats, inventory, completed_map),
            'stats':        stats,
            'stat_bonuses': effective_stats.bonuses,
            'inventory':    inventory,
            'logs':         session.log.all()[:10],
            'oob':          True,
            'combat_state': combat_state,
        }
        scene_html     = render_to_string('game/partials/scene_panel.html', context, request)
        stats_html     = render_to_string('game/partials/stats_bar.html',   context, request)
        log_html       = render_to_string('game/partials/event_log.html',   context, request)
        inventory_html = render_to_string('game/partials/inventory.html',   context, request)
        mobile_html    = render_to_string('game/partials/mobile_stats_bar.html', context, request)
        return HttpResponse(scene_html + stats_html + log_html + inventory_html + mobile_html)

    return redirect('scene_detail', scene_key=next_scene.key)


def combat_attack(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get('game_session_id')
    if not session_pk:
        return redirect('game_hub')

    session = get_object_or_404(GameSession, pk=session_pk)
    stats   = session.stats

    try:
        combat_state = session.combat_state
    except CombatState.DoesNotExist:
        return HttpResponse("No active combat.", status=400)

    if not combat_state.is_active:
        return HttpResponse("Combat is not active.", status=400)

    enemy         = combat_state.enemy
    inventory     = get_player_inventory(session)
    completed_map = _get_completed_map(session)
    effective_stats = get_effective_stats(stats, inventory)

    # ── PLAYER ATTACKS ──────────────────────────────────────────────
    p_hit, p_dmg, p_roll, p_total = resolve_player_attack(effective_stats, enemy)
    str_mod = stat_modifier(effective_stats.strength)
    mod_str = f"+{str_mod}" if str_mod >= 0 else str(str_mod)

    if p_hit:
        combat_state.enemy_hp = max(0, combat_state.enemy_hp - p_dmg)
        EventLog.objects.create(
            session=session,
            text=(
                f"You move on him — roll {p_roll} ({mod_str}) = {p_total} "
                f"vs {enemy.defense} — Hit! {p_dmg} damage."
            ),
        )
    else:
        EventLog.objects.create(
            session=session,
            text=(
                f"You move on him — roll {p_roll} ({mod_str}) = {p_total} "
                f"vs {enemy.defense} — Missed."
            ),
        )

    # ── CHECK: OPPONENT DOWN ─────────────────────────────────────────
    if combat_state.enemy_hp <= 0:
        combat_state.is_active = False
        combat_state.save()
        EventLog.objects.create(
            session=session,
            text=f"{enemy.name} goes down. You walk away."
        )

        next_scene = enemy.victory_scene
        session.current_scene = next_scene
        session.save()

        if next_scene.is_ending and next_scene.quest:
            if not CompletedQuest.objects.filter(
                session=session, quest=next_scene.quest
            ).exists():
                CompletedQuest.objects.create(
                    session=session,
                    quest=next_scene.quest,
                    ending_type=next_scene.ending_type,
                )
                EventLog.objects.create(
                    session=session,
                    text=f"You have completed: {next_scene.quest.title} "
                         f"({next_scene.get_ending_type_display()})",
                )
                completed_map[next_scene.quest_id] = next_scene.ending_type

        awarded = award_scene_items(session, next_scene, inventory)
        for item, qty in awarded:
            EventLog.objects.create(
                session=session, text=f"You picked up: {item.name} x{qty}."
            )

        # AWARD XP for combat victory
        combat_levels = award_xp(session, stats, XP_AWARDS['combat_victory'])
        EventLog.objects.create(
            session=session,
            text=f"+{XP_AWARDS['combat_victory']} XP."
        )
        for new_level in combat_levels:
            flavor = LEVEL_UP_FLAVOR[new_level - 2]
            EventLog.objects.create(session=session, text=flavor)

        effective_stats = get_effective_stats(stats, inventory)
        context = {
            'scene':        next_scene,
            'choices':      get_available_choices(next_scene, effective_stats, inventory, completed_map),
            'stats':        stats,
            'stat_bonuses': effective_stats.bonuses,
            'inventory':    inventory,
            'logs':         session.log.all()[:10],
            'oob':          True,
            'combat_state': None,
        }
        scene_html     = render_to_string('game/partials/scene_panel.html',  context, request)
        stats_html     = render_to_string('game/partials/stats_bar.html',    context, request)
        log_html       = render_to_string('game/partials/event_log.html',    context, request)
        inventory_html = render_to_string('game/partials/inventory.html',    context, request)
        mobile_html    = render_to_string('game/partials/mobile_stats_bar.html', context, request)
        return HttpResponse(scene_html + stats_html + log_html + inventory_html + mobile_html)

    # ── ENEMY ATTACKS BACK ───────────────────────────────────────────
    e_hit, e_dmg, e_roll, e_total = resolve_enemy_attack(enemy, effective_stats)
    player_defense = 10 + stat_modifier(effective_stats.agility)
    e_mod_str = f"+{enemy.attack_modifier}" if enemy.attack_modifier >= 0 else str(enemy.attack_modifier)

    if e_hit:
        stats.hp = max(0, stats.hp - e_dmg)
        EventLog.objects.create(
            session=session,
            text=(
                f"{enemy.name} comes at you — roll {e_roll} ({e_mod_str}) = {e_total} "
                f"vs {player_defense} — Hit! {e_dmg} damage."
            ),
        )
    else:
        EventLog.objects.create(
            session=session,
            text=(
                f"{enemy.name} comes at you — roll {e_roll} ({e_mod_str}) = {e_total} "
                f"vs {player_defense} — Missed."
            ),
        )

    stats.save()

    # ── CHECK: PLAYER DOWN ───────────────────────────────────────────
    if stats.hp <= 0:
        combat_state.is_active = False
        combat_state.save()
        EventLog.objects.create(
            session=session, text="You're down. You lose consciousness."
        )

        next_scene = enemy.defeat_scene
        session.current_scene = next_scene
        session.save()

        if next_scene.is_ending and next_scene.quest:
            if not CompletedQuest.objects.filter(
                session=session, quest=next_scene.quest
            ).exists():
                CompletedQuest.objects.create(
                    session=session,
                    quest=next_scene.quest,
                    ending_type=next_scene.ending_type,
                )
                EventLog.objects.create(
                    session=session,
                    text=f"You have completed: {next_scene.quest.title} "
                         f"({next_scene.get_ending_type_display()})",
                )
                completed_map[next_scene.quest_id] = next_scene.ending_type

        awarded = award_scene_items(session, next_scene, inventory)
        for item, qty in awarded:
            EventLog.objects.create(
                session=session, text=f"You picked up: {item.name} x{qty}."
            )

        effective_stats = get_effective_stats(stats, inventory)
        context = {
            'scene':        next_scene,
            'choices':      get_available_choices(next_scene, effective_stats, inventory, completed_map),
            'stats':        stats,
            'stat_bonuses': effective_stats.bonuses,
            'inventory':    inventory,
            'logs':         session.log.all()[:10],
            'oob':          True,
            'combat_state': None,
        }
        scene_html     = render_to_string('game/partials/scene_panel.html',  context, request)
        stats_html     = render_to_string('game/partials/stats_bar.html',    context, request)
        log_html       = render_to_string('game/partials/event_log.html',    context, request)
        inventory_html = render_to_string('game/partials/inventory.html',    context, request)
        mobile_html    = render_to_string('game/partials/mobile_stats_bar.html', context, request)
        return HttpResponse(scene_html + stats_html + log_html + inventory_html + mobile_html)

    # ── COMBAT CONTINUES ─────────────────────────────────────────────
    combat_state.turn_number += 1
    combat_state.save()

    effective_stats = get_effective_stats(stats, inventory)
    context = {
        'scene':        session.current_scene,
        'choices':      [],
        'stats':        stats,
        'stat_bonuses': effective_stats.bonuses,
        'inventory':    inventory,
        'logs':         session.log.all()[:10],
        'oob':          True,
        'combat_state': combat_state,
    }
    scene_html     = render_to_string('game/partials/scene_panel.html',  context, request)
    stats_html     = render_to_string('game/partials/stats_bar.html',    context, request)
    log_html       = render_to_string('game/partials/event_log.html',    context, request)
    inventory_html = render_to_string('game/partials/inventory.html',    context, request)
    mobile_html    = render_to_string('game/partials/mobile_stats_bar.html', context, request)
    return HttpResponse(scene_html + stats_html + log_html + inventory_html + mobile_html)


STAT_FIELD_MAP = {
    'muscle':   'strength',
    'reflexes': 'agility',
    'cunning':  'intellect',
    'nerve':    'charisma',
}

def level_up(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get('game_session_id')
    if not session_pk:
        return redirect('game_hub')

    session = get_object_or_404(GameSession, pk=session_pk)
    stats   = session.stats

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

    EventLog.objects.create(
        session=session,
        text=f"{stat_name.upper()} increased to {current_val + 1}."
    )

    scene           = session.current_scene
    inventory       = get_player_inventory(session)
    effective_stats = get_effective_stats(stats, inventory)
    completed_map   = _get_completed_map(session)

    # Preserve active combat state if one exists
    combat_state = None
    try:
        cs = session.combat_state
        if cs.is_active:
            combat_state = cs
    except CombatState.DoesNotExist:
        pass

    if scene.key == NOTICE_BOARD_KEY:
        notice_board = get_notice_board(session, stats)
    else:
        notice_board = None

    context = {
        'scene':        scene,
        'choices':      get_available_choices(scene, effective_stats, inventory, completed_map),
        'stats':        stats,
        'stat_bonuses': effective_stats.bonuses,
        'inventory':    inventory,
        'logs':         session.log.all()[:10],
        'oob':          True,
        'combat_state': combat_state,
        'notice_board': notice_board,
    }

    scene_html     = render_to_string('game/partials/scene_panel.html',  context, request)
    stats_html     = render_to_string('game/partials/stats_bar.html',    context, request)
    log_html       = render_to_string('game/partials/event_log.html',    context, request)
    inventory_html = render_to_string('game/partials/inventory.html',    context, request)
    mobile_html    = render_to_string('game/partials/mobile_stats_bar.html', context, request)
    return HttpResponse(scene_html + stats_html + log_html + inventory_html + mobile_html)


USE_ITEM_FLAVOR = {
    'heal_hp':  "You take a pull from the flask. Steadier now.",
    'add_stat': "You feel sharper. More focused.",
}


def use_item(request, item_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get('game_session_id')
    if not session_pk:
        return redirect('game_hub')

    from .models import Item
    session = get_object_or_404(GameSession, pk=session_pk)
    item    = get_object_or_404(Item, pk=item_id)
    stats   = session.stats
    inventory = get_player_inventory(session)

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
        EventLog.objects.create(
            session=session,
            text=f"{USE_ITEM_FLAVOR['heal_hp']} (+{healed} HP)"
        )

    elif item.effect_type == 'add_stat':
        if item.effect_stat:
            current = getattr(stats, item.effect_stat, 0)
            setattr(stats, item.effect_stat, current + item.effect_value)
            stats.save()
        EventLog.objects.create(
            session=session,
            text=USE_ITEM_FLAVOR['add_stat']
        )

    # ── CONSUME IF CONSUMABLE ────────────────────────────────────────
    if item.is_consumable:
        consume_item_util(session, item, inventory)

    # ── BUILD RESPONSE ───────────────────────────────────────────────
    scene           = session.current_scene
    effective_stats = get_effective_stats(stats, inventory)
    completed_map   = _get_completed_map(session)

    combat_state = None
    try:
        cs = session.combat_state
        if cs.is_active:
            combat_state = cs
    except CombatState.DoesNotExist:
        pass

    if scene.key == NOTICE_BOARD_KEY:
        notice_board = get_notice_board(session, stats)
    else:
        notice_board = None

    context = {
        'scene':        scene,
        'choices':      get_available_choices(scene, effective_stats, inventory, completed_map),
        'stats':        stats,
        'stat_bonuses': effective_stats.bonuses,
        'inventory':    inventory,
        'logs':         session.log.all()[:10],
        'oob':          True,
        'combat_state': combat_state,
        'notice_board': notice_board,
    }
    scene_html     = render_to_string('game/partials/scene_panel.html',  context, request)
    stats_html     = render_to_string('game/partials/stats_bar.html',    context, request)
    log_html       = render_to_string('game/partials/event_log.html',    context, request)
    inventory_html = render_to_string('game/partials/inventory.html',    context, request)
    mobile_html    = render_to_string('game/partials/mobile_stats_bar.html', context, request)
    return HttpResponse(scene_html + stats_html + log_html + inventory_html + mobile_html)
