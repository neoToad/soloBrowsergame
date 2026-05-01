from django.shortcuts import get_object_or_404
from ..models import GameSession, PlayerStats, Scene, CompletedQuest
from ..models.property import PlayerDiscoveredTerritory, PlayerProperty, PlayerTerritory, Territory
from ..constants import HUB_START_SCENE_KEY, SESSION_KEY
from .inventory import get_player_inventory
from . import jobs as jobs_service
from ..utils import get_effective_stats, compute_max_hp

def load_session_context(session_pk):
    """Load session and derived gameplay context used by game views."""
    session = get_object_or_404(GameSession, pk=session_pk)
    stats   = session.stats
    inventory     = get_player_inventory(session)
    effective_stats = get_effective_stats(stats, inventory)
    completed_map   = get_completed_map(session)
    return session, stats, inventory, effective_stats, completed_map


def advance_to_scene(session, scene):
    """Move the session to scene and persist."""
    session.current_scene = scene
    session.save()


def get_completed_map(session):
    """Return `{quest_id: ending_type}` for quests completed in this session."""
    return {
        cq.quest_id: cq.ending_type
        for cq in CompletedQuest.objects.filter(session=session)
    }


def build_player_context(effective_stats, inventory, completed_map, flags=None, contacts=None):
    """Construct a PlayerContext value object for requirement evaluation."""
    from ..models import PlayerContext
    return PlayerContext(
        stats=effective_stats,
        inventory=inventory,
        completed_map=completed_map,
        flags=flags or {},
        contacts=contacts or {},
    )


def create_session(request):
    """Creates a new GameSession + PlayerStats, stores the pk in the Django session."""
    if not request.session.session_key:
        request.session.create()
    game_session = GameSession.objects.create(
        session_key=request.session.session_key,
        current_scene=Scene.objects.get(key=HUB_START_SCENE_KEY),
    )
    initial_max_hp = compute_max_hp(5)  # default strength is 5
    PlayerStats.objects.create(session=game_session, max_hp=initial_max_hp, hp=initial_max_hp)
    request.session[SESSION_KEY] = game_session.pk
    return game_session


def _build_core_scene_context(
    session,
    scene,
    stats,
    effective_stats,
    inventory,
    completed_map,
    *,
    combat_state,
    turn_summary=None,
    roll_result=None,
    damage_result=None,
):
    from .scene import get_available_choices

    return {
        "session": session,
        "scene": scene,
        "choices": get_available_choices(
            scene,
            effective_stats,
            inventory,
            completed_map,
            flags=session.flags,
        ),
        "stats": stats,
        "effective_stats": effective_stats,
        "stat_bonuses": effective_stats.bonuses,
        "inventory": inventory,
        "logs": session.log.all()[:10],
        "oob": True,
        "combat_state": combat_state,
        "turn_summary": turn_summary,
        "roll_result": roll_result,
        "damage_result": damage_result,
    }


def _build_social_property_context(session):
    from ..models import PlayerContact, PlayerGangStanding

    player_properties = PlayerProperty.objects.filter(session=session).select_related("property")
    discovered_territory_ids = list(
        PlayerDiscoveredTerritory.objects.filter(session=session).values_list("territory_id", flat=True)
    )
    visible_territories = Territory.objects.filter(id__in=discovered_territory_ids)
    owned_territory_ids = set(
        PlayerTerritory.objects.filter(session=session).values_list("territory_id", flat=True)
    )
    player_contacts = PlayerContact.objects.filter(session=session).select_related("contact")
    player_gang_standings = PlayerGangStanding.objects.filter(session=session).select_related("gang")
    return {
        "player_properties": player_properties,
        "visible_territories": visible_territories,
        "owned_territory_ids": owned_territory_ids,
        "player_contacts": player_contacts,
        "player_gang_standings": player_gang_standings,
    }


def _build_hub_context(session, scene, effective_stats, inventory, completed_map):
    from .scene import get_notice_board

    notice_board = None
    if scene.is_hub:
        notice_board = get_notice_board(
            scene,
            inventory,
            completed_map,
            effective_stats,
            flags=session.flags,
        )
    jobs_hub_context = jobs_service.build_jobs_hub_context(
        session,
        scene,
        effective_stats,
        inventory,
        completed_map,
    )
    return {
        "notice_board": notice_board,
        **jobs_hub_context,
    }


def build_render_context(session, scene, stats, effective_stats, inventory, completed_map, *, combat_state, turn_summary=None, roll_result=None, damage_result=None):
    """Assemble canonical template context for scene rendering and HTMX partial updates."""
    context = _build_core_scene_context(
        session,
        scene,
        stats,
        effective_stats,
        inventory,
        completed_map,
        combat_state=combat_state,
        turn_summary=turn_summary,
        roll_result=roll_result,
        damage_result=damage_result,
    )
    context.update(_build_hub_context(session, scene, effective_stats, inventory, completed_map))
    context.update(_build_social_property_context(session))
    return context
