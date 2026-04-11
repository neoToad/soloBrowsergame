from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseNotAllowed
from django.template.loader import render_to_string
from .models import (
    GameSession, PlayerStats, Scene, Choice, EventLog,
    CompletedQuest, Quest, CombatState, PlayerContext,
)
from .utils import (
    roll_d20, stat_modifier, get_notice_board,
    get_player_inventory, award_scene_items,
    consume_item as consume_item_util,
    resolve_player_attack, resolve_enemy_attack,
    award_xp, XP_AWARDS, LEVEL_UP_FLAVOR,
    get_effective_stats, maybe_complete_quest,
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

def _build_context(session, scene, stats, effective_stats, inventory, completed_map, *, combat_state, notice_board=None):
    return {
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


def get_available_choices(scene, stats, inventory, completed_map):
    choices = []
    ctx = PlayerContext(stats=stats, inventory=inventory, completed_map=completed_map)
    for choice in scene.choices.prefetch_related('requirements__requirements').all():
        # RequirementGroup gate — all groups must pass
        if choice.requirements.exists():
            passed = all(
                rg.evaluate(ctx)
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

def _load_context(session_pk):
    session = get_object_or_404(GameSession, pk=session_pk)
    stats   = session.stats
    inventory     = get_player_inventory(session)
    effective_stats = get_effective_stats(stats, inventory)
    completed_map   = _get_completed_map(session)
    return session, stats, inventory, effective_stats, completed_map

def _get_active_combat_state(session):
    """
    Returns the session's active CombatState if one exists, else None.
    Read-only, does not modify database.
    """
    try:
        cs = session.combat_state
        if cs.is_active:
            return cs
    except CombatState.DoesNotExist:
        pass
    return None


def _get_notice_board_for_scene(session, stats, scene):
    if scene.key == NOTICE_BOARD_SCENE_KEY:
        return get_notice_board(session, stats)
    return None


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

def _create_session(request):
    """Creates a new GameSession + PlayerStats, stores the pk in the Django session."""
    if not request.session.session_key:
        request.session.create()
    game_session = GameSession.objects.create(
        session_key=request.session.session_key,
        current_scene=Scene.objects.get(key=HUB_START_SCENE_KEY),
    )
    PlayerStats.objects.create(session=game_session)
    request.session['game_session_id'] = game_session.pk
    return game_session


def game_hub(request):
    session_pk = request.session.get('game_session_id')

    if not session_pk:
        _create_session(request)
    else:
        # Check if the session actually exists in DB
        try:
            GameSession.objects.get(pk=session_pk)
        except GameSession.DoesNotExist:
            _create_session(request)

    return redirect('scene_detail', scene_key=HUB_START_SCENE_KEY)

def scene_detail(request, scene_key):
    session_pk = request.session.get('game_session_id')
    if not session_pk:
        return redirect('/game/')

    game_session, stats, inventory, effective_stats, completed_map = _load_context(session_pk)
    scene        = get_object_or_404(Scene, key=scene_key)
    combat_state = _get_combat_state(game_session, scene)

    notice_board = _get_notice_board_for_scene(game_session, stats, scene)

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

    session, stats, inventory, effective_stats, completed_map = _load_context(session_pk)
    choice    = get_object_or_404(Choice, pk=choice_id)

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
    quest_logs = maybe_complete_quest(session, stats, next_scene, completed_map)
    for log_text in quest_logs:
        EventLog.objects.create(session=session, text=log_text)

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
        notice_board = _get_notice_board_for_scene(session, stats, next_scene)

        context = _build_context(
            session, next_scene, stats, effective_stats, inventory, completed_map,
            combat_state=combat_state, notice_board=notice_board
        )
        return _htmx_response(request, context)

    return redirect('scene_detail', scene_key=next_scene.key)

def start_quest(request, quest_key):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get('game_session_id')
    if not session_pk:
        return redirect('game_hub')

    session, stats, inventory, effective_stats, completed_map = _load_context(session_pk)
    quest = get_object_or_404(Quest, key=quest_key)

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
        awarded = award_scene_items(session, next_scene, inventory)
        for item, qty in awarded:
            EventLog.objects.create(
                session=session,
                text=f"You picked up: {item.name} x{qty}."
            )

        combat_state    = _get_combat_state(session, next_scene)
        effective_stats = get_effective_stats(stats, inventory)

        context = _build_context(
            session, next_scene, stats, effective_stats, inventory, completed_map,
            combat_state=combat_state
        )
        return _htmx_response(request, context)

    return redirect('scene_detail', scene_key=next_scene.key)


def _resolve_combat_end(session, stats, inventory, completed_map, next_scene, combat_state, *, xp_award=0):
    """
    Shared teardown for combat victory and defeat:
    deactivates combat, advances the scene, runs quest/item/XP logic,
    and returns a ready-to-render HTMX context dict.
    """
    combat_state.is_active = False
    combat_state.save()

    session.current_scene = next_scene
    session.save()

    quest_logs = maybe_complete_quest(session, stats, next_scene, completed_map)
    for log_text in quest_logs:
        EventLog.objects.create(session=session, text=log_text)

    awarded = award_scene_items(session, next_scene, inventory)
    for item, qty in awarded:
        EventLog.objects.create(session=session, text=f"You picked up: {item.name} x{qty}.")

    if xp_award:
        combat_levels = award_xp(session, stats, xp_award)
        EventLog.objects.create(session=session, text=f"+{xp_award} XP.")
        for new_level in combat_levels:
            EventLog.objects.create(session=session, text=LEVEL_UP_FLAVOR[new_level - 2])

    effective_stats = get_effective_stats(stats, inventory)
    return _build_context(
        session, next_scene, stats, effective_stats, inventory, completed_map,
        combat_state=None,
    )


def combat_attack(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get('game_session_id')
    if not session_pk:
        return redirect('game_hub')

    session, stats, inventory, effective_stats, completed_map = _load_context(session_pk)

    try:
        combat_state = session.combat_state
    except CombatState.DoesNotExist:
        return HttpResponse("No active combat.", status=400)

    if not combat_state.is_active:
        return HttpResponse("Combat is not active.", status=400)

    enemy         = combat_state.enemy

    # ── PLAYER ATTACKS ──────────────────────────────────────────────
    p_hit, p_dmg, p_roll, p_total = resolve_player_attack(effective_stats, enemy)
    str_mod = stat_modifier(effective_stats.strength)
    mod_str = f"+{str_mod}" if str_mod >= 0 else str(str_mod)

    if p_hit:
        combat_state.enemy_hp = max(0, combat_state.enemy_hp - p_dmg)
        combat_state.save()
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
        EventLog.objects.create(session=session, text=f"{enemy.name} goes down. You walk away.")
        context = _resolve_combat_end(
            session, stats, inventory, completed_map,
            enemy.victory_scene, combat_state,
            xp_award=XP_AWARDS['combat_victory'],
        )
        return _htmx_response(request, context)

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
        EventLog.objects.create(session=session, text="You're down. You lose consciousness.")
        context = _resolve_combat_end(
            session, stats, inventory, completed_map,
            enemy.defeat_scene, combat_state,
        )
        return _htmx_response(request, context)

    effective_stats = get_effective_stats(stats, inventory)
    context = _build_context(
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

    session, stats, inventory, effective_stats, completed_map = _load_context(session_pk)

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
    effective_stats = get_effective_stats(stats, inventory)

    # Preserve active combat state if one exists
    combat_state = _get_active_combat_state(session)

    notice_board = _get_notice_board_for_scene(session, stats, scene)

    context = _build_context(
        session, scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state, notice_board=notice_board
    )

    return _htmx_response(request, context)


def use_item(request, item_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get('game_session_id')
    if not session_pk:
        return redirect('game_hub')

    from .models import Item
    session, stats, inventory, effective_stats, completed_map = _load_context(session_pk)
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

    combat_state = _get_active_combat_state(session)

    notice_board = _get_notice_board_for_scene(session, stats, scene)

    context = _build_context(
        session, scene, stats, effective_stats, inventory, completed_map,
        combat_state=combat_state, notice_board=notice_board
    )
    return _htmx_response(request, context)
