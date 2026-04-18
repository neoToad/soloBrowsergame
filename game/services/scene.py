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


def get_available_choices(scene, effective_stats, inventory, completed_map, flags=None):
    from ..models import PlayerContext
    ctx = PlayerContext(
        stats=effective_stats,
        inventory=inventory,
        completed_map=completed_map,
        flags=flags or {},
    )
    choices = []
    for choice in scene.choices.prefetch_related('started_quests').all():
        # Gate 1: RequirementGroup check
        if choice.requirements.exists():
            passed = all(
                rg.evaluate(ctx)
                for rg in choice.requirements.all()
            )
            if not passed:
                continue

        # Gate 2: Quest-entry — hide once completed if not repeatable
        started_quest = choice.started_quests.first()
        if started_quest is not None and started_quest.id in completed_map:
            if not started_quest.is_repeatable:
                continue

        choices.append(choice)
    return choices


def complete_scene(session, scene, choice, inventory, next_scene=None) -> list[str]:
    from ..models import SceneUnlock
    from .inventory import consume_item as consume_item_util
    unlocks = SceneUnlock.objects.filter(from_scene=scene).select_related('unlocks_scene', 'requires_item')
    logs = []

    for unlock in unlocks:
        if unlock.requires_choice_id and unlock.requires_choice_id != choice.id:
            continue
        if unlock.requires_item_id and unlock.requires_item_id not in inventory:
            continue
        logs.append(f"New area unlocked: {unlock.unlocks_scene.title}.")

    # Consume item on arrival at destination scene
    if next_scene and next_scene.consume_item_id and next_scene.consume_item_id in inventory:
        consume_item_util(session, next_scene.consume_item, inventory)
        logs.append(f"You used your {next_scene.consume_item.name}.")

    return logs


def get_notice_board(scene, inventory, completed_map, effective_stats, flags=None):
    """
    Returns a dict of three lists — available, locked, completed — for quests
    assigned to the given hub scene.
    """
    from ..models import Quest, PlayerContext
    ctx = PlayerContext(
        stats=effective_stats,
        inventory=inventory,
        completed_map=completed_map,
        flags=flags or {},
    )
    available, locked, completed = [], [], []
    for quest in Quest.objects.filter(is_unlocked=True, hub_scenes=scene).prefetch_related(
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
