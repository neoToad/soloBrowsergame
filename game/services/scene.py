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
