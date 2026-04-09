from django.shortcuts import render, redirect, get_object_or_404
from .models import GameSession, PlayerStats, Scene, Choice, EventLog

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
    
    choices = get_available_choices(scene, stats)
    logs = game_session.log.all()[:10]
    
    context = {
        'session': game_session,
        'scene': scene,
        'stats': stats,
        'choices': choices,
        'logs': logs,
    }
    return render(request, 'game/scene.html', context)
