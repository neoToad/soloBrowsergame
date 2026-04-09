from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseNotAllowed
from django.template.loader import render_to_string
from .models import GameSession, PlayerStats, Scene, Choice, EventLog, CompletedQuest, Quest
from .utils import roll_d20, stat_modifier, get_notice_board

NOTICE_BOARD_KEY = 'hub__notice_board'

def get_available_choices(scene, stats):
    choices = []
    for choice in scene.choices.all():
        if choice.required_stat:
            player_value = getattr(stats, choice.required_stat, 0)
            if player_value < choice.required_minimum:
                continue
        choices.append(choice)
    return choices

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
    scene = get_object_or_404(Scene, key=scene_key)
    stats = game_session.stats

    if scene.key == NOTICE_BOARD_KEY:
        notice_board = get_notice_board(game_session, stats)
    else:
        notice_board = None
    
    choices = get_available_choices(scene, stats)
    logs = game_session.log.all()[:10]
    
    context = {
        'session': game_session,
        'scene': scene,
        'stats': stats,
        'choices': choices,
        'logs': logs,
        'notice_board': notice_board,
    }
    return render(request, 'game/scene.html', context)

def choice_resolve(request, choice_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    session_pk = request.session.get('game_session_id')
    if not session_pk:
        return redirect('game_hub')

    session = get_object_or_404(GameSession, pk=session_pk)
    choice = get_object_or_404(Choice, pk=choice_id)
    stats = session.stats

    scene = choice.scene
    next_scene = None

    # 5. ROLL LOGIC
    if scene.requires_roll:
        stat_value = getattr(stats, scene.roll_stat, 10)
        modifier = stat_modifier(stat_value)
        roll = roll_d20()
        total = roll + modifier
        dc = scene.roll_difficulty
        success = total >= dc

        mod_str = f"+ {modifier}" if modifier >= 0 else f"- {abs(modifier)}"
        res_str = "Success!" if success else "Failure."
        log_text = f"You rolled a {roll} ({mod_str} modifier) = {total} vs DC {dc} — {res_str}"
        
        EventLog.objects.create(session=session, text=log_text)
        
        if success:
            next_scene = choice.success_scene
        else:
            next_scene = choice.failure_scene
    else:
        next_scene = choice.target_scene

    # 6. ARRIVAL FLAVOR
    if choice.arrival_flavor:
        EventLog.objects.create(session=session, text=choice.arrival_flavor)

    # 7. ADVANCE SESSION
    session.current_scene = next_scene
    session.save()

    # 8. QUEST COMPLETION
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

    is_htmx = request.headers.get('HX-Request') == 'true'
    if is_htmx:
        if next_scene.key == NOTICE_BOARD_KEY:
            notice_board = get_notice_board(session, stats)
        else:
            notice_board = None

        context = {
            'scene': next_scene,
            'choices': get_available_choices(next_scene, stats),
            'stats': stats,
            'logs': session.log.all()[:10],
            'oob': True,
            'notice_board': notice_board,
        }
        scene_html = render_to_string('game/partials/scene_panel.html', context, request)
        stats_html = render_to_string('game/partials/stats_bar.html', context, request)
        log_html = render_to_string('game/partials/event_log.html', context, request)
        return HttpResponse(scene_html + stats_html + log_html)

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
        context = {
            'scene': next_scene,
            'choices': get_available_choices(next_scene, stats),
            'stats': stats,
            'logs': session.log.all()[:10],
            'oob': True,
        }
        scene_html = render_to_string('game/partials/scene_panel.html', context, request)
        stats_html = render_to_string('game/partials/stats_bar.html', context, request)
        log_html = render_to_string('game/partials/event_log.html', context, request)
        return HttpResponse(scene_html + stats_html + log_html)

    return redirect('scene_detail', scene_key=next_scene.key)
