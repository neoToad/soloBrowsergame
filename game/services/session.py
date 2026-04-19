from django.shortcuts import get_object_or_404
from ..models import GameSession, PlayerStats, Scene, CompletedQuest
from ..models.property import PlayerProperty, Property
from ..constants import HUB_START_SCENE_KEY, SESSION_KEY
from .inventory import get_player_inventory
from ..utils import get_effective_stats

def load_session_context(session_pk):
    session = get_object_or_404(GameSession, pk=session_pk)
    stats   = session.stats
    inventory     = get_player_inventory(session)
    effective_stats = get_effective_stats(stats, inventory)
    completed_map   = get_completed_map(session)
    return session, stats, inventory, effective_stats, completed_map


def get_completed_map(session):
    return {
        cq.quest_id: cq.ending_type
        for cq in CompletedQuest.objects.filter(session=session)
    }


def create_session(request):
    """Creates a new GameSession + PlayerStats, stores the pk in the Django session."""
    if not request.session.session_key:
        request.session.create()
    game_session = GameSession.objects.create(
        session_key=request.session.session_key,
        current_scene=Scene.objects.get(key=HUB_START_SCENE_KEY),
    )
    PlayerStats.objects.create(session=game_session)
    request.session[SESSION_KEY] = game_session.pk
    return game_session


def build_render_context(session, scene, stats, effective_stats, inventory, completed_map, *, combat_state, turn_summary=None, roll_result=None, damage_result=None):
    from .scene import get_available_choices, get_notice_board
    notice_board = None
    if scene.is_hub:
        notice_board = get_notice_board(scene, inventory, completed_map, effective_stats, flags=session.flags)
    player_properties = PlayerProperty.objects.filter(session=session).select_related('property')
    all_territories   = Property.objects.filter(property_type='territory')
    owned_territory_ids = {
        pp.property_id for pp in player_properties if pp.property.property_type == 'territory'
    }
    return {
        'scene':                scene,
        'choices':              get_available_choices(scene, effective_stats, inventory, completed_map, flags=session.flags),
        'stats':                stats,
        'stat_bonuses':         effective_stats.bonuses,
        'inventory':            inventory,
        'logs':                 session.log.all()[:10],
        'oob':                  True,
        'combat_state':         combat_state,
        'notice_board':         notice_board,
        'turn_summary':         turn_summary,
        'roll_result':          roll_result,
        'damage_result':        damage_result,
        'player_properties':    player_properties,
        'all_territories':      all_territories,
        'owned_territory_ids':  owned_territory_ids,
    }
