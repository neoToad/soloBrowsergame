from django.db import transaction
from django.utils.text import slugify

from ..models.world import Quest, Scene, Choice
from ..models.combat import CombatEncounter


CARD_WIDTH = 220
CARD_HEIGHT = 100
GRID_START_X = 60
GRID_START_Y = 60
GRID_X_GAP = 280
GRID_Y_GAP = 200
CANVAS_PADDING = 120

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

        def append_arrow(target_scene_id, kind):
            if not target_scene_id:
                return

            target_scene = scene_lookup.get(target_scene_id)
            if not target_scene:
                return

            target_x = target_scene['canvas_x']
            target_y = target_scene['canvas_y'] + (CARD_HEIGHT // 2)

            arrows.append({
                'id': f"choice-{c.id}-{kind}",
                'kind': kind,
                'label': c.label,
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
                'kind': kind,
                'label': label,
                'x1': source_x,
                'y1': source_y,
                'x2': target_x,
                'y2': target_y,
                'label_x': (source_x + target_x) // 2,
                'label_y': ((source_y + target_y) // 2) - 6,
            })

        append_combat_arrow(encounter.enemy.victory_scene_id, 'success', 'WIN')
        append_combat_arrow(encounter.enemy.defeat_scene_id, 'failure', 'LOSE')

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

    raw_x = data.get('canvas_x')
    raw_y = data.get('canvas_y')
    canvas_x = int(raw_x) if str(raw_x).strip() else 60
    canvas_y = int(raw_y) if str(raw_y).strip() else 60

    requires_roll = str(data.get('requires_roll', '')).lower() in ('1', 'true', 'on', 'yes')
    roll_stat = (data.get('roll_stat') or '').strip()
    raw_dc = data.get('roll_difficulty')
    roll_difficulty = int(raw_dc) if str(raw_dc).strip() else 12

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
        raw_dc = data.get('roll_difficulty')
        scene.roll_difficulty = int(raw_dc) if str(raw_dc).strip() else 12

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
    """Stub only"""
    pass

def update_choice(choice_id, data):
    """Stub only"""
    pass

def delete_choice(choice_id):
    """Stub only"""
    pass

def save_scene_position(scene_id, x, y):
    """Updates canvas_x and canvas_y on the scene and saves"""
    Scene.objects.filter(pk=scene_id).update(canvas_x=x, canvas_y=y)

def build_requirement_groups_from_post(obj, post_data):
    """Stub only"""
    pass
