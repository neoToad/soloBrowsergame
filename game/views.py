from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseNotAllowed
from django.template.loader import render_to_string
from .models import GameSession, PlayerStats, Scene, Choice, EventLog, CompletedQuest, Quest
from .utils import roll_d20, stat_modifier, get_notice_board, get_player_inventory, award_scene_items, consume_item as consume_item_util

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

    game_session = get_object_or_404(GameSession, pk=session_pk)
    scene        = get_object_or_404(Scene, key=scene_key)
    stats        = game_session.stats
    inventory    = get_player_inventory(game_session)
    completed_map = _get_completed_map(game_session)

    if scene.key == NOTICE_BOARD_KEY:
        notice_board = get_notice_board(game_session, stats)
    else:
        notice_board = None

    choices = get_available_choices(scene, stats, inventory, completed_map)
    logs    = game_session.log.all()[:10]

    context = {
        'session':      game_session,
        'scene':        scene,
        'stats':        stats,
        'inventory':    inventory,
        'choices':      choices,
        'logs':         logs,
        'notice_board': notice_board,
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
    completed_map = _get_completed_map(session)

    scene      = choice.scene
    next_scene = None

    # ROLL LOGIC
    if scene.requires_roll:
        stat_value = getattr(stats, scene.roll_stat, 10)
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

    # AWARD SCENE ITEMS
    awarded = award_scene_items(session, next_scene, inventory)
    for item, qty in awarded:
        EventLog.objects.create(
            session=session,
            text=f"You picked up: {item.name} x{qty}."
        )

    is_htmx = request.headers.get('HX-Request') == 'true'
    if is_htmx:
        if next_scene.key == NOTICE_BOARD_KEY:
            notice_board = get_notice_board(session, stats)
        else:
            notice_board = None

        context = {
            'scene':        next_scene,
            'choices':      get_available_choices(next_scene, stats, inventory, completed_map),
            'stats':        stats,
            'inventory':    inventory,
            'logs':         session.log.all()[:10],
            'oob':          True,
            'notice_board': notice_board,
        }
        scene_html     = render_to_string('game/partials/scene_panel.html',  context, request)
        stats_html     = render_to_string('game/partials/stats_bar.html',    context, request)
        log_html       = render_to_string('game/partials/event_log.html',    context, request)
        inventory_html = render_to_string('game/partials/inventory.html',    context, request)
        return HttpResponse(scene_html + stats_html + log_html + inventory_html)

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
        inventory     = get_player_inventory(session)
        completed_map = _get_completed_map(session)

        awarded = award_scene_items(session, next_scene, inventory)
        for item, qty in awarded:
            EventLog.objects.create(
                session=session,
                text=f"You picked up: {item.name} x{qty}."
            )

        context = {
            'scene':     next_scene,
            'choices':   get_available_choices(next_scene, stats, inventory, completed_map),
            'stats':     stats,
            'inventory': inventory,
            'logs':      session.log.all()[:10],
            'oob':       True,
        }
        scene_html     = render_to_string('game/partials/scene_panel.html', context, request)
        stats_html     = render_to_string('game/partials/stats_bar.html',   context, request)
        log_html       = render_to_string('game/partials/event_log.html',   context, request)
        inventory_html = render_to_string('game/partials/inventory.html',   context, request)
        return HttpResponse(scene_html + stats_html + log_html + inventory_html)

    return redirect('scene_detail', scene_key=next_scene.key)
