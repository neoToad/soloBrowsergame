from ..utils import roll_d20, stat_modifier

def resolve_roll(scene, choice, effective_stats) -> tuple[object, str]:
    """
    Rolls d20 + stat modifier vs scene.roll_difficulty.
    Returns (next_scene, log_text). Does NOT write to the DB.
    """

    stat_value = getattr(effective_stats, scene.roll_stat, 10)
    modifier   = stat_modifier(stat_value)
    roll       = roll_d20()
    total      = roll + modifier
    dc         = scene.roll_difficulty
    success    = total >= dc

    mod_str = f"+ {modifier}" if modifier >= 0 else f"- {abs(modifier)}"
    res_str = "Success!" if success else "Failure."
    log_text = f"You rolled a {roll} ({mod_str} modifier) = {total} vs DC {dc} — {res_str}"

    next_scene = choice.success_scene if success else choice.failure_scene
    return (next_scene, log_text)


def get_available_choices(scene, effective_stats, inventory, completed_map):
    from ..models import PlayerContext
    ctx = PlayerContext(
        stats=effective_stats,
        inventory=inventory,
        completed_map=completed_map,
    )
    choices = []
    for choice in scene.choices.select_related('quest').all():
        # Gate 1: RequirementGroup check
        if choice.requirements.exists():
            passed = all(
                rg.evaluate(ctx)
                for rg in choice.requirements.all()
            )
            if not passed:
                continue

        # Gate 2: Quest-entry — hide once completed if not repeatable
        if choice.quest_id is not None and choice.quest_id in completed_map:
            if not choice.quest.is_repeatable:
                continue

        choices.append(choice)
    return choices


def unlock_scene(session, scene) -> None:
    from ..models import PlayerSceneState
    state_obj, created = PlayerSceneState.objects.get_or_create(
        session=session,
        scene=scene,
        defaults={'state': 'available'}
    )
    if not created and state_obj.state == 'locked':
        state_obj.state = 'available'
        state_obj.save()


def complete_scene(session, scene, choice, inventory) -> list[str]:
    from ..models import PlayerSceneState, SceneUnlock
    state_obj, created = PlayerSceneState.objects.update_or_create(
        session=session,
        scene=scene,
        defaults={'state': 'completed'}
    )

    unlocks = SceneUnlock.objects.filter(from_scene=scene).select_related('unlocks_scene', 'requires_item')
    logs = []

    for unlock in unlocks:
        # Check choice requirement
        if unlock.requires_choice_id and unlock.requires_choice_id != choice.id:
            continue

        # Check item requirement
        if unlock.requires_item_id and unlock.requires_item_id not in inventory:
            continue

        unlock_scene(session, unlock.unlocks_scene)
        logs.append(f"New area unlocked: {unlock.unlocks_scene.title}.")

    return logs


def get_available_scenes(session):
    from ..models import Scene
    return Scene.objects.filter(player_states__session=session, player_states__state='available')


def get_notice_board(inventory, completed_map, effective_stats):
    """
    Returns a dict of three lists — available, locked, completed — for all
    is_unlocked quests. Called only when rendering the notice board scene.
    """
    from ..models import Quest, PlayerContext
    ctx = PlayerContext(
        stats=effective_stats,
        inventory=inventory,
        completed_map=completed_map,
    )
    available, locked, completed = [], [], []
    for quest in Quest.objects.filter(is_unlocked=True).prefetch_related(
        'requirements__requirements'
    ):
        if quest.id in completed_map:
            completed.append({
                'quest': quest,
                'ending_type': completed_map[quest.id],
            })
            continue
        if quest.requirements.exists():
            failing = [
                rg for rg in quest.requirements.all() if not rg.evaluate(ctx)
            ]
            if failing:
                locked.append({
                    'quest': quest,
                    'reasons': [rg.label for rg in failing],
                })
                continue
        available.append({'quest': quest})
    return {'available': available, 'locked': locked, 'completed': completed}
