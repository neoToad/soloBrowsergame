from ..models.world import Quest, Scene, Choice


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
    """Stub only"""
    pass

def update_scene(scene_id, data):
    """Stub only"""
    pass

def delete_scene(scene_id):
    """Stub only"""
    pass

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
