from django.db import transaction
from django.utils.text import slugify

from ..models.world import Quest, Scene, Choice, SceneItem
from ..models.items import Item
from ..models.combat import CombatEncounter, Enemy


CARD_WIDTH = 220
CARD_HEIGHT = 100
GRID_START_X = 60
GRID_START_Y = 60
GRID_X_GAP = 280
GRID_Y_GAP = 200
CANVAS_PADDING = 120
PARALLEL_ARROW_SPACING = 12

def get_canvas_data(quest_id):
    """
    Returns a dict with the quest object, a list of all scenes for this quest,
    and a list of all choices across those scenes.
    """
    quest = Quest.objects.get(pk=quest_id)
    scenes_qs = quest.scenes.only(
        'id', 'canvas_x', 'canvas_y', 'scene_type', 'key', 'title', 'requires_roll'
    )
    
    scenes = []
    scene_ids = []
    scene_roll_lookup = {}
    scene_lookup = {}
    for index, s in enumerate(scenes_qs):
        # Display-only fallback position for scenes not yet placed by drag.
        display_x = s.canvas_x
        display_y = s.canvas_y
        if s.canvas_x == 0 and s.canvas_y == 0:
            display_x = GRID_START_X + (index % 4) * GRID_X_GAP
            display_y = GRID_START_Y + (index // 4) * GRID_Y_GAP

        scene_data = {
            'id': s.id,
            'canvas_x': display_x,
            'canvas_y': display_y,
            'scene_type': s.scene_type,
            'key': s.key,
            'title': s.title,
            'requires_roll': s.requires_roll,
        }
        scenes.append(scene_data)
        scene_ids.append(s.id)
        scene_roll_lookup[s.id] = s.requires_roll
        scene_lookup[s.id] = scene_data
    
    choices_qs = Choice.objects.filter(scene_id__in=scene_ids).only(
        'id', 'scene_id', 'label', 'target_scene_id', 'success_scene_id', 'failure_scene_id'
    )
    encounters_qs = CombatEncounter.objects.filter(scene_id__in=scene_ids).select_related('enemy','victory_scene','defeat_scene').only(
        'id', 'scene_id', 'enemy_id', 'victory_scene_id', 'defeat_scene_id'
    )
    
    choices = []
    arrows = []
    for c in choices_qs:
        choice_data = {
            'id': c.id,
            'source_scene_id': c.scene_id,
            'source_requires_roll': scene_roll_lookup.get(c.scene_id, False),
            'label': c.label,
            'target_scene_id': c.target_scene_id,
            'success_scene_id': c.success_scene_id,
            'failure_scene_id': c.failure_scene_id,
        }
        choices.append(choice_data)

        source_scene = scene_lookup.get(c.scene_id)
        if not source_scene:
            continue

        source_x = source_scene['canvas_x'] + CARD_WIDTH
        source_y = source_scene['canvas_y'] + (CARD_HEIGHT // 2)

        def append_arrow(target_scene_id, kind, choice_id=c.id):
            if not target_scene_id:
                return

            target_scene = scene_lookup.get(target_scene_id)
            if not target_scene:
                return

            target_x = target_scene['canvas_x']
            target_y = target_scene['canvas_y'] + (CARD_HEIGHT // 2)

            arrows.append({
                'id': f"choice-{choice_id}-{kind}",
                'choice_id': choice_id,
                'kind': kind,
                'label': c.label,
                'source_scene_id': c.scene_id,
                'target_scene_id': target_scene_id,
                'success_scene_id': target_scene_id if kind == 'success' else None,
                'failure_scene_id': target_scene_id if kind == 'failure' else None,
                'x1': source_x,
                'y1': source_y,
                'x2': target_x,
                'y2': target_y,
                'label_x': (source_x + target_x) // 2,
                'label_y': ((source_y + target_y) // 2) - 6,
            })

        if choice_data['source_requires_roll']:
            append_arrow(c.success_scene_id, 'success')
            append_arrow(c.failure_scene_id, 'failure')
        else:
            append_arrow(c.target_scene_id, 'direct')

    for encounter in encounters_qs:
        source_scene = scene_lookup.get(encounter.scene_id)
        if not source_scene:
            continue

        source_x = source_scene['canvas_x'] + CARD_WIDTH
        source_y = source_scene['canvas_y'] + (CARD_HEIGHT // 2)

        def append_combat_arrow(target_scene_id, kind, label):
            if not target_scene_id:
                return

            target_scene = scene_lookup.get(target_scene_id)
            if not target_scene:
                return

            target_x = target_scene['canvas_x']
            target_y = target_scene['canvas_y'] + (CARD_HEIGHT // 2)

            arrows.append({
                'id': f"combat-{encounter.id}-{kind}",
                'choice_id': None,
                'kind': kind,
                'label': label,
                'source_scene_id': encounter.scene_id,
                'target_scene_id': target_scene_id,
                'success_scene_id': target_scene_id if kind == 'success' else None,
                'failure_scene_id': target_scene_id if kind == 'failure' else None,
                'x1': source_x,
                'y1': source_y,
                'x2': target_x,
                'y2': target_y,
                'label_x': (source_x + target_x) // 2,
                'label_y': ((source_y + target_y) // 2) - 6,
            })

        append_combat_arrow(encounter.victory_scene_id, 'success', 'WIN')
        append_combat_arrow(encounter.defeat_scene_id, 'failure', 'LOSE')

    # Spread arrows that share the same source and target so they do not overlap.
    arrows_by_edge = {}
    for arrow in arrows:
        edge_key = (arrow.get('source_scene_id'), arrow.get('target_scene_id'))
        arrows_by_edge.setdefault(edge_key, []).append(arrow)

    for grouped_arrows in arrows_by_edge.values():
        total = len(grouped_arrows)
        center_index = (total - 1) / 2
        for index, arrow in enumerate(grouped_arrows):
            lane = index - center_index
            offset = int(lane * PARALLEL_ARROW_SPACING)

            arrow['offset_index'] = index
            arrow['offset_total'] = total
            arrow['offset_px'] = offset

            arrow['y1'] += offset
            arrow['y2'] += offset
            arrow['label_y'] += offset

    # Annotate ending scenes with hub-exit info for cards that route outside this quest.
    external_ending_targets: dict[int, list[tuple[int, str]]] = {}
    for c_data in choices:
        source = scene_lookup.get(c_data['source_scene_id'])
        tid = c_data['target_scene_id']
        if source and source['scene_type'] == 'ending' and tid and tid not in scene_lookup:
            external_ending_targets.setdefault(tid, []).append(
                (c_data['source_scene_id'], c_data['label'])
            )

    if external_ending_targets:
        hub_map = {
            s.id: s
            for s in Scene.objects.filter(
                pk__in=external_ending_targets.keys(), scene_type='hub'
            ).only('id', 'key', 'title')
        }
        for target_id, source_list in external_ending_targets.items():
            if target_id not in hub_map:
                continue
            hub = hub_map[target_id]
            for source_scene_id, label in source_list:
                source = scene_lookup.get(source_scene_id)
                if not source:
                    continue
                source.setdefault('hub_exits', []).append({
                    'hub_key': hub.key,
                    'hub_title': hub.title,
                    'choice_label': label,
                })

    if scenes:
        max_scene_x = max(scene['canvas_x'] for scene in scenes)
        max_scene_y = max(scene['canvas_y'] for scene in scenes)
        canvas_width = max_scene_x + CARD_WIDTH + CANVAS_PADDING
        canvas_height = max_scene_y + CARD_HEIGHT + CANVAS_PADDING
    else:
        canvas_width = GRID_START_X + CARD_WIDTH + CANVAS_PADDING
        canvas_height = GRID_START_Y + CARD_HEIGHT + CANVAS_PADDING

    return {
        'quest': quest,
        'scenes': scenes,
        'choices': choices,
        'arrows': arrows,
        'canvas_width': canvas_width,
        'canvas_height': canvas_height,
    }

def validate_quest(quest_id):
    """
    Returns a list of warning dicts for the given quest.
    Each dict has: type, message, and optionally scene_id / choice_id.
    """
    quest = Quest.objects.get(pk=quest_id)
    scenes_qs = quest.scenes.only(
        'id', 'key', 'title', 'scene_type', 'requires_roll'
    )
    scenes = list(scenes_qs)
    scene_ids = [s.id for s in scenes]

    choices_qs = Choice.objects.filter(scene_id__in=scene_ids).only(
        'id', 'scene_id', 'label', 'target_scene_id', 'success_scene_id', 'failure_scene_id'
    )
    choices = list(choices_qs)

    # Fetch scene_type for any target scenes that live outside this quest (e.g. hub scenes).
    scene_id_set = set(scene_ids)
    external_target_ids = set()
    for c in choices:
        for tid in (c.target_scene_id, c.success_scene_id, c.failure_scene_id):
            if tid and tid not in scene_id_set:
                external_target_ids.add(tid)
    external_scene_types: dict[int, str] = {}
    if external_target_ids:
        external_scene_types = {
            s.id: s.scene_type
            for s in Scene.objects.filter(pk__in=external_target_ids).only('id', 'scene_type')
        }

    encounters_qs = CombatEncounter.objects.filter(scene_id__in=scene_ids).only(
        'id', 'scene_id'
    )
    encounter_scene_ids = set(encounters_qs.values_list('scene_id', flat=True))

    warnings = []

    # --- No hub scenes ---
    if quest.is_unlocked and not quest.hub_scenes.exists():
        warnings.append({
            'type': 'no_hub_scenes',
            'scene_id': None,
            'choice_id': None,
            'message': 'Quest is unlocked but has no hub scenes assigned — it will not appear on any notice board.',
        })

    # --- Duplicate keys ---
    seen_keys = {}
    for scene in scenes:
        if scene.key in seen_keys:
            warnings.append({
                'type': 'duplicate_key',
                'scene_id': scene.id,
                'choice_id': None,
                'message': f'Duplicate key "{scene.key}" — scene "{scene.title}" shares a key with scene ID {seen_keys[scene.key]}.',
            })
        else:
            seen_keys[scene.key] = scene.id

    # --- Build set of scenes that are pointed to by at least one choice ---
    pointed_to = set()
    for c in choices:
        if c.target_scene_id:
            pointed_to.add(c.target_scene_id)
        if c.success_scene_id:
            pointed_to.add(c.success_scene_id)
        if c.failure_scene_id:
            pointed_to.add(c.failure_scene_id)

    entry_scene_id = quest.entrance_scene_id

    # --- Orphan scenes ---
    for scene in scenes:
        if scene.id not in pointed_to and scene.id != entry_scene_id:
            warnings.append({
                'type': 'orphan_scene',
                'scene_id': scene.id,
                'choice_id': None,
                'message': f'Scene "{scene.title}" is not reachable — no choices point to it and it is not the entry scene.',
            })

    # --- Missing routing (completely unrouted choices) ---
    for c in choices:
        if not c.target_scene_id and not c.success_scene_id and not c.failure_scene_id:
            warnings.append({
                'type': 'missing_routing',
                'scene_id': c.scene_id,
                'choice_id': c.id,
                'message': f'Choice "{c.label}" has no routing target set.',
            })

    # --- Per-scene analysis ---
    choices_by_scene = {}
    for c in choices:
        choices_by_scene.setdefault(c.scene_id, []).append(c)

    for scene in scenes:
        scene_choices = choices_by_scene.get(scene.id, [])

        # Missing roll target: requires_roll=True but no choice with both success+failure
        if scene.requires_roll:
            has_full_roll = any(
                c.success_scene_id and c.failure_scene_id for c in scene_choices
            )
            if not has_full_roll:
                warnings.append({
                    'type': 'missing_roll_target',
                    'scene_id': scene.id,
                    'choice_id': None,
                    'message': f'Scene "{scene.title}" requires a roll but has no choice with both success and failure targets set.',
                })

            # Roll scene with direct choice
            for c in scene_choices:
                if c.target_scene_id:
                    warnings.append({
                        'type': 'roll_direct_choice',
                        'scene_id': scene.id,
                        'choice_id': c.id,
                        'message': f'Scene "{scene.title}" requires a roll but choice "{c.label}" uses a direct target — this is probably a mistake.',
                    })

        # Empty scenes (not ending or hub)
        if not scene_choices and scene.scene_type not in ('ending', 'hub'):
            warnings.append({
                'type': 'empty_scene',
                'scene_id': scene.id,
                'choice_id': None,
                'message': f'Scene "{scene.title}" has no choices.',
            })

        # Combat scene missing encounter
        if scene.scene_type == 'combat' and scene.id not in encounter_scene_ids:
            warnings.append({
                'type': 'combat_missing_encounter',
                'scene_id': scene.id,
                'choice_id': None,
                'message': f'Scene "{scene.title}" is a combat scene but has no combat encounter configured.',
            })

        # Ending scene with no return-to-hub choice
        if scene.scene_type == 'ending':
            has_hub_return = any(
                c.target_scene_id and external_scene_types.get(c.target_scene_id) == 'hub'
                for c in scene_choices
            )
            if not has_hub_return:
                warnings.append({
                    'type': 'ending_no_hub_return',
                    'scene_id': scene.id,
                    'choice_id': None,
                    'message': f'Ending scene "{scene.title}" has no "return to hub" choice — players will have no way to leave after the quest ends.',
                })

    return warnings


def create_scene(quest_id, data):
    quest = Quest.objects.get(pk=quest_id)

    title = (data.get('title') or '').strip()
    key = (data.get('key') or '').strip()
    description = (data.get('description') or '').strip()
    scene_type = (data.get('scene_type') or 'normal').strip() or 'normal'

    if not key and title:
        key = f"{quest.key}__{slugify(title)}"

    if key and quest.scenes.filter(key=key).exists():
        raise ValueError(f'A scene with key "{key}" already exists in this quest.')

    raw_x = str(data.get('canvas_x') or '').strip()
    raw_y = str(data.get('canvas_y') or '').strip()
    if raw_x and raw_y:
        canvas_x = int(raw_x)
        canvas_y = int(raw_y)
    else:
        # Place in the next grid slot so it doesn't overlap existing cards
        index = quest.scenes.count()
        canvas_x = GRID_START_X + (index % 4) * GRID_X_GAP
        canvas_y = GRID_START_Y + (index // 4) * GRID_Y_GAP

    requires_roll = str(data.get('requires_roll', '')).lower() in ('1', 'true', 'on', 'yes')
    roll_stat = (data.get('roll_stat') or '').strip()
    raw_dc = str(data.get('roll_difficulty') or '').strip()
    roll_difficulty = int(raw_dc) if raw_dc else 12
    raw_item = str(data.get('consume_item_id') or '').strip()
    consume_item_id = int(raw_item) if raw_item else None

    cash_reward = int(data.get('cash_reward') or 0)
    rep_reward  = int(data.get('rep_reward') or 0)
    heat_change = int(data.get('heat_change') or 0)
    receive_prop_id = int(data.get('receive_property_id') or 0) or None
    lose_prop_id    = int(data.get('lose_property_id') or 0) or None

    scene = Scene.objects.create(
        title=title,
        key=key,
        scene_type=scene_type,
        body=description,
        requires_roll=requires_roll,
        roll_stat=roll_stat,
        roll_difficulty=roll_difficulty,
        canvas_x=canvas_x,
        canvas_y=canvas_y,
        consume_item_id=consume_item_id,
        cash_reward=cash_reward,
        rep_reward=rep_reward,
        heat_change=heat_change,
        receive_property_id=receive_prop_id,
        lose_property_id=lose_prop_id,
    )
    quest.scenes.add(scene)
    return scene

def update_scene(scene_id, data):
    scene = Scene.objects.get(pk=scene_id)

    scene.title = (data.get('title') or scene.title).strip()
    incoming_key = (data.get('key') or '').strip()
    if incoming_key:
        scene_quest = scene.quests.first()
        if scene_quest and scene_quest.scenes.filter(key=incoming_key).exclude(pk=scene.pk).exists():
            raise ValueError(f'A scene with key "{incoming_key}" already exists in this quest.')
        scene.key = incoming_key
    scene.scene_type = (data.get('scene_type') or scene.scene_type).strip() or scene.scene_type
    scene.body = (data.get('description') or '').strip()
    scene.requires_roll = str(data.get('requires_roll', '')).lower() in ('1', 'true', 'on', 'yes')
    scene.roll_stat = (data.get('roll_stat') or '').strip()
    raw_dc = str(data.get('roll_difficulty') or '').strip()
    scene.roll_difficulty = int(raw_dc) if raw_dc else 12
    raw_item = str(data.get('consume_item_id') or '').strip()
    scene.consume_item_id = int(raw_item) if raw_item else None

    scene.cash_reward = int(data.get('cash_reward') or 0)
    scene.rep_reward  = int(data.get('rep_reward') or 0)
    scene.heat_change = int(data.get('heat_change') or 0)
    scene.receive_property_id = int(data.get('receive_property_id') or 0) or None
    scene.lose_property_id    = int(data.get('lose_property_id') or 0) or None

    scene.save()
    return scene

def get_delete_scene_consequences(scene_id):
    """
    Returns a dict describing what will happen if this scene is deleted,
    without actually deleting it. Used for the confirmation step.
    """
    target_qs = Choice.objects.filter(target_scene_id=scene_id).select_related('scene')
    success_qs = Choice.objects.filter(success_scene_id=scene_id).select_related('scene')
    failure_qs = Choice.objects.filter(failure_scene_id=scene_id).select_related('scene')

    affected_choices = list({
        c.id: c for c in list(target_qs) + list(success_qs) + list(failure_qs)
    }.values())

    victory_encounters = list(
        CombatEncounter.objects.filter(victory_scene_id=scene_id).select_related('scene', 'enemy')
    )
    defeat_encounters = list(
        CombatEncounter.objects.filter(defeat_scene_id=scene_id).select_related('scene', 'enemy')
    )

    return {
        'affected_choices': affected_choices,
        'victory_encounters': victory_encounters,
        'defeat_encounters': defeat_encounters,
    }


def delete_scene(scene_id):
    scene = Scene.objects.get(pk=scene_id)

    target_qs = Choice.objects.filter(target_scene_id=scene_id)
    success_qs = Choice.objects.filter(success_scene_id=scene_id)
    failure_qs = Choice.objects.filter(failure_scene_id=scene_id)

    affected_choice_ids = sorted({
        *target_qs.values_list('id', flat=True),
        *success_qs.values_list('id', flat=True),
        *failure_qs.values_list('id', flat=True),
    })

    with transaction.atomic():
        CombatEncounter.objects.filter(victory_scene_id=scene_id).update(victory_scene=None)
        CombatEncounter.objects.filter(defeat_scene_id=scene_id).update(defeat_scene=None)
        target_qs.update(target_scene=None)
        success_qs.update(success_scene=None)
        failure_qs.update(failure_scene=None)
        scene.delete()

    return affected_choice_ids

def create_choice(source_scene_id, data):
    scene = Scene.objects.get(pk=source_scene_id)
    label = (data.get('label') or '').strip()
    routing_type = (data.get('routing_type') or 'direct').strip()

    target_scene_id = None
    success_scene_id = None
    failure_scene_id = None

    if routing_type == 'roll':
        raw_success = str(data.get('success_scene') or '').strip()
        raw_failure = str(data.get('failure_scene') or '').strip()
        success_scene_id = int(raw_success) if raw_success else None
        failure_scene_id = int(raw_failure) if raw_failure else None
    else:
        raw_target = str(data.get('target_scene') or '').strip()
        target_scene_id = int(raw_target) if raw_target else None

    set_flag_name = (data.get('set_flag_name') or '').strip()
    clear_flag_name = (data.get('clear_flag_name') or '').strip()
    arrival_flavor = (data.get('arrival_flavor') or '').strip()
    failure_arrival_flavor = (data.get('failure_arrival_flavor') or '').strip()

    return Choice.objects.create(
        scene=scene,
        label=label,
        target_scene_id=target_scene_id,
        success_scene_id=success_scene_id,
        failure_scene_id=failure_scene_id,
        set_flag_name=set_flag_name,
        clear_flag_name=clear_flag_name,
        arrival_flavor=arrival_flavor,
        failure_arrival_flavor=failure_arrival_flavor,
    )

def update_choice(choice_id, data):
    choice = Choice.objects.get(pk=choice_id)
    label = (data.get('label') or '').strip()
    routing_type = (data.get('routing_type') or 'direct').strip()

    choice.label = label

    if routing_type == 'roll':
        raw_success = str(data.get('success_scene') or '').strip()
        raw_failure = str(data.get('failure_scene') or '').strip()
        choice.success_scene_id = int(raw_success) if raw_success else None
        choice.failure_scene_id = int(raw_failure) if raw_failure else None
        choice.target_scene_id = None
    else:
        raw_target = str(data.get('target_scene') or '').strip()
        choice.target_scene_id = int(raw_target) if raw_target else None
        choice.success_scene_id = None
        choice.failure_scene_id = None

    choice.set_flag_name = (data.get('set_flag_name') or '').strip()
    choice.clear_flag_name = (data.get('clear_flag_name') or '').strip()
    choice.arrival_flavor = (data.get('arrival_flavor') or '').strip()
    choice.failure_arrival_flavor = (data.get('failure_arrival_flavor') or '').strip()

    choice.save()
    return choice

def delete_choice(choice_id):
    choice = Choice.objects.get(pk=choice_id)
    source_scene_id = choice.scene_id
    choice.delete()
    return source_scene_id

def save_scene_position(scene_id, x, y):
    """Updates canvas_x and canvas_y on the scene and saves"""
    Scene.objects.filter(pk=scene_id).update(canvas_x=x, canvas_y=y)


def update_scene_items(scene_id, items_data):
    """
    Replaces all SceneItem records for this scene with the provided list.
    items_data: list of dicts with 'item_id' and 'quantity' keys.
    Skips entries where item_id is blank/None.
    Returns the updated list of SceneItem objects.
    """
    with transaction.atomic():
        SceneItem.objects.filter(scene_id=scene_id).delete()
        created = []
        for entry in items_data:
            raw_id = str(entry.get('item_id') or '').strip()
            if not raw_id:
                continue
            raw_qty = str(entry.get('quantity') or '').strip()
            quantity = int(raw_qty) if raw_qty else 1
            scene_item = SceneItem.objects.create(
                scene_id=scene_id,
                item_id=int(raw_id),
                quantity=quantity,
            )
            created.append(scene_item)
    return created


def update_combat_encounter(scene_id, data):
    """
    Creates or updates the CombatEncounter for this scene.
    If enemy_id is blank/null, deletes any existing encounter and returns None.
    Returns the encounter object or None.
    """
    raw_enemy = str(data.get('enemy_id') or '').strip()
    if not raw_enemy:
        CombatEncounter.objects.filter(scene_id=scene_id).delete()
        return None

    raw_victory = str(data.get('victory_scene_id') or '').strip()
    raw_defeat  = str(data.get('defeat_scene_id') or '').strip()
    victory_scene_id = int(raw_victory) if raw_victory else None
    defeat_scene_id  = int(raw_defeat)  if raw_defeat  else None

    victory_arrival_flavor = (data.get('victory_arrival_flavor') or '').strip()
    defeat_arrival_flavor  = (data.get('defeat_arrival_flavor') or '').strip()

    encounter, _ = CombatEncounter.objects.update_or_create(
        scene_id=scene_id,
        defaults={
            'enemy_id':               int(raw_enemy),
            'victory_scene_id':       victory_scene_id,
            'defeat_scene_id':        defeat_scene_id,
            'victory_arrival_flavor': victory_arrival_flavor,
            'defeat_arrival_flavor':  defeat_arrival_flavor,
        },
    )
    return encounter


def build_requirement_groups_from_post(obj, post_data):
    """
    Clears all RequirementGroup M2M relations on obj, then rebuilds from POST data.
    obj is a Scene or Choice (both have requirements M2M to RequirementGroup).
    Returns the list of created RequirementGroup objects.

    POST format:
      group_count = N
      group_0_logic = all|any
      group_0_req_count = M
      group_0_req_0_type = stat_gte
      group_0_req_0_param = strength:3       (stat: "name:value")
      group_0_req_0_param = met_informant    (flag: flag_name)
      group_0_req_0_param = <quest_id>       (quest types)
      group_0_req_0_param2 = victory         (quest_ending only: ending_type)
      group_0_req_0_param = <item_id>        (item types)
      group_0_req_0_param = <number>         (level_gte / xp_gte)
    """
    from ..models.requirements import Requirement, RequirementGroup

    with transaction.atomic():
        old_groups = list(obj.requirements.all())
        obj.requirements.clear()
        Requirement.objects.filter(groups__in=old_groups).delete()
        RequirementGroup.objects.filter(pk__in=[g.pk for g in old_groups]).delete()

        raw_count = str(post_data.get('group_count') or '').strip()
        try:
            group_count = int(raw_count)
        except (ValueError, TypeError):
            return []

        created_groups = []
        for gi in range(group_count):
            logic = (post_data.get(f'group_{gi}_logic') or 'all').strip()
            if logic not in ('all', 'any'):
                logic = 'all'

            raw_req_count = str(post_data.get(f'group_{gi}_req_count') or '').strip()
            try:
                req_count = int(raw_req_count)
            except (ValueError, TypeError):
                req_count = 0

            group = RequirementGroup.objects.create(
                label=f'Group {gi + 1}',
                logic=logic,
            )

            for ri in range(req_count):
                ctype = (post_data.get(f'group_{gi}_req_{ri}_type') or '').strip()
                if not ctype:
                    continue
                param  = (post_data.get(f'group_{gi}_req_{ri}_param')  or '').strip()
                param2 = (post_data.get(f'group_{gi}_req_{ri}_param2') or '').strip()

                req_kwargs = {'condition_type': ctype}

                if ctype in ('stat_gte', 'stat_lte'):
                    if ':' in param:
                        stat_name, _, raw_val = param.partition(':')
                        req_kwargs['stat_name'] = stat_name.strip()
                        try:
                            req_kwargs['stat_value'] = int(raw_val.strip())
                        except ValueError:
                            req_kwargs['stat_value'] = 0
                    else:
                        req_kwargs['stat_name'] = param
                        req_kwargs['stat_value'] = 0

                elif ctype in ('has_flag', 'missing_flag'):
                    req_kwargs['flag_name'] = param

                elif ctype in ('quest_completed', 'quest_not_done'):
                    if param:
                        try:
                            req_kwargs['required_quest_id'] = int(param)
                        except ValueError:
                            pass

                elif ctype == 'quest_ending':
                    if param:
                        try:
                            req_kwargs['required_quest_id'] = int(param)
                        except ValueError:
                            pass
                    if param2:
                        req_kwargs['required_ending_type'] = param2

                elif ctype in ('level_gte', 'xp_gte'):
                    try:
                        req_kwargs['stat_value'] = int(param)
                    except (ValueError, TypeError):
                        req_kwargs['stat_value'] = 0

                elif ctype in ('has_item', 'missing_item'):
                    if param:
                        try:
                            req_kwargs['required_item_id'] = int(param)
                        except ValueError:
                            pass

                req = Requirement.objects.create(**req_kwargs)
                group.requirements.add(req)

            obj.requirements.add(group)
            created_groups.append(group)

        return created_groups
