from ..combat import execute_player_attack, execute_enemy_attack, resolve_combat_end
from ...models.events import flush_event_log
from ...models.combat import CombatEncounter, CombatState
from ..types import GameplayError
from ..progression import XP_AWARDS


def run_player_attack(session_context) -> dict:
    session, stats, inventory, effective_stats, completed_map = session_context
    combat_state = _require_active_combat(session)
    logs, context = execute_player_attack(
        session, stats, inventory, completed_map, combat_state, effective_stats
    )
    flush_event_log(session, logs)
    context['choices'] = []
    return context


def run_enemy_attack(session_context) -> dict:
    session, stats, inventory, effective_stats, completed_map = session_context
    combat_state = _require_active_combat(session)
    if not combat_state.enemy_attack_pending:
        raise GameplayError("No pending enemy attack.", status=400)
    try:
        logs, context = execute_enemy_attack(
            session, stats, inventory, completed_map, combat_state, effective_stats
        )
    except CombatEncounter.DoesNotExist:
        raise GameplayError(
            "No combat encounter configured for this scene. Check quest content.", status=400
        )
    flush_event_log(session, logs)
    returned_combat_state = context.get('combat_state')
    if returned_combat_state and returned_combat_state.is_active:
        context['choices'] = []
    return context


def run_combat_continue(session_context) -> dict:
    session, stats, inventory, effective_stats, completed_map = session_context
    combat_state = _require_combat_state(session)
    if not combat_state.pending_victory:
        raise GameplayError("No pending victory.", status=400)
    try:
        encounter = CombatEncounter.objects.get(scene=session.current_scene)
    except CombatEncounter.DoesNotExist:
        raise GameplayError(
            "No combat encounter configured for this scene. Check quest content.", status=400
        )
    logs, context = resolve_combat_end(
        session, stats, inventory, completed_map,
        encounter.victory_scene, combat_state,
        xp_award=XP_AWARDS['combat_victory'],
        ending_type='victory',
    )
    flush_event_log(session, logs)
    returned_combat_state = context.get('combat_state')
    if returned_combat_state and returned_combat_state.is_active:
        context['choices'] = []
    return context


def _require_active_combat(session):
    try:
        combat_state = session.combat_state
    except CombatState.DoesNotExist:
        raise GameplayError("No active combat.", status=400)
    if not combat_state.is_active:
        raise GameplayError("Combat is not active.", status=400)
    return combat_state


def _require_combat_state(session):
    try:
        return session.combat_state
    except CombatState.DoesNotExist:
        raise GameplayError("No combat state.", status=400)
