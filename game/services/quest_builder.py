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
    scenes_qs = Scene.objects.filter(quest=quest).only(
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
    encounters_qs = CombatEncounter.objects.filter(scene_id__in=scene_ids).select_related('enemy').only(
        'id', 'scene_id', 'enemy_id', 'enemy__victory_scene_id', 'enemy__defeat_scene_id'
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

        append_combat_arrow(encounter.enemy.victory_scene_id, 'success', 'WIN')
        append_combat_arrow(encounter.enemy.defeat_scene_id, 'failure', 'LOSE')

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

def create_scene(quest_id, data):
    quest = Quest.objects.get(pk=quest_id)

    title = (data.get('title') or '').strip()
    key = (data.get('key') or '').strip()
    description = (data.get('description') or '').strip()
    scene_type = (data.get('scene_type') or 'normal').strip() or 'normal'

    if not key and title:
        key = f"{quest.key}__{slugify(title)}"

    raw_x = str(data.get('canvas_x') or '').strip()
    raw_y = str(data.get('canvas_y') or '').strip()
    if raw_x and raw_y:
        canvas_x = int(raw_x)
        canvas_y = int(raw_y)
    else:
        # Place in the next grid slot so it doesn't overlap existing cards
        index = Scene.objects.filter(quest=quest).count()
        canvas_x = GRID_START_X + (index % 4) * GRID_X_GAP
        canvas_y = GRID_START_Y + (index // 4) * GRID_Y_GAP

    requires_roll = str(data.get('requires_roll', '')).lower() in ('1', 'true', 'on', 'yes')
    roll_stat = (data.get('roll_stat') or '').strip()
    raw_dc = str(data.get('roll_difficulty') or '').strip()
    roll_difficulty = int(raw_dc) if raw_dc else 12

    return Scene.objects.create(
        quest=quest,
        title=title,
        key=key,
        scene_type=scene_type,
        body=description,
        requires_roll=requires_roll,
        roll_stat=roll_stat,
        roll_difficulty=roll_difficulty,
        canvas_x=canvas_x,
        canvas_y=canvas_y,
    )

def update_scene(scene_id, data):
    scene = Scene.objects.get(pk=scene_id)

    allowed_fields = {
        'title',
        'key',
        'scene_type',
        'description',
        'requires_roll',
        'roll_stat',
        'roll_difficulty',
    }

    if 'title' in allowed_fields:
        scene.title = (data.get('title') or scene.title).strip()
    if 'key' in allowed_fields:
        incoming_key = (data.get('key') or '').strip()
        if incoming_key:
            scene.key = incoming_key
    if 'scene_type' in allowed_fields:
        scene.scene_type = (data.get('scene_type') or scene.scene_type).strip() or scene.scene_type
    if 'description' in allowed_fields:
        scene.body = (data.get('description') or '').strip()
    if 'requires_roll' in allowed_fields:
        scene.requires_roll = str(data.get('requires_roll', '')).lower() in ('1', 'true', 'on', 'yes')
    if 'roll_stat' in allowed_fields:
        scene.roll_stat = (data.get('roll_stat') or '').strip()
    if 'roll_difficulty' in allowed_fields:
        raw_dc = str(data.get('roll_difficulty') or '').strip()
        scene.roll_difficulty = int(raw_dc) if raw_dc else 12

    scene.save()
    return scene

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

    return Choice.objects.create(
        scene=scene,
        label=label,
        target_scene_id=target_scene_id,
        success_scene_id=success_scene_id,
        failure_scene_id=failure_scene_id,
        set_flag_name=set_flag_name,
        clear_flag_name=clear_flag_name,
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

    encounter, _ = CombatEncounter.objects.update_or_create(
        scene_id=scene_id,
        defaults={
            'enemy_id':         int(raw_enemy),
            'victory_scene_id': victory_scene_id,
            'defeat_scene_id':  defeat_scene_id,
        },
    )
    return encounter


def build_requirement_groups_from_post(obj, post_data):
    """Stub only"""
    pass
