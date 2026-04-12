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
