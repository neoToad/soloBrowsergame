from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from ...models.combat import CombatEncounter
from ...models.world import Choice, Quest, Scene, SceneContact, SceneItem
from .parsing import parse_choice_form, parse_combat_form, parse_scene_form
from .shared import GRID_START_X, GRID_START_Y, GRID_X_GAP, GRID_Y_GAP, raise_authoring_validation_error


def create_scene(quest_id, data):
    quest = Quest.objects.get(pk=quest_id)
    parsed = parse_scene_form(data)

    key = parsed["key"]
    if not key and parsed["title"]:
        key = f"{quest.key}__{slugify(parsed['title'])}"
    if key and quest.scenes.filter(key=key).exists():
        raise ValueError(f'A scene with key "{key}" already exists in this quest.')

    raw_x = str(data.get("canvas_x") or "").strip()
    raw_y = str(data.get("canvas_y") or "").strip()
    if raw_x and raw_y:
        canvas_x = int(raw_x)
        canvas_y = int(raw_y)
    else:
        index = quest.scenes.count()
        canvas_x = GRID_START_X + (index % 4) * GRID_X_GAP
        canvas_y = GRID_START_Y + (index // 4) * GRID_Y_GAP

    scene = Scene(
        quest=quest,
        title=parsed["title"],
        key=key,
        scene_type=parsed["scene_type"],
        ending_type=parsed["ending_type"],
        body=parsed["description"],
        requires_roll=parsed["requires_roll"],
        roll_stat=parsed["roll_stat"],
        roll_difficulty=parsed["roll_difficulty"],
        canvas_x=canvas_x,
        canvas_y=canvas_y,
        consume_item_id=parsed["consume_item_id"],
        cash_change=parsed["cash_change"],
        rep_change=parsed["rep_change"],
        heat_change=parsed["heat_change"],
        receive_property_id=parsed["receive_property_id"],
        lose_property_id=parsed["lose_property_id"],
        receive_territory_id=parsed["receive_territory_id"],
        lose_territory_id=parsed["lose_territory_id"],
    )
    try:
        scene.clean()
    except ValidationError as exc:
        raise_authoring_validation_error(exc)
    scene.save()
    return scene


def update_scene(scene_id, data):
    scene = Scene.objects.get(pk=scene_id)
    parsed = parse_scene_form(data)

    scene.title = parsed["title"] or scene.title
    incoming_key = parsed["key"]
    if incoming_key:
        scene_quest = scene.quest
        if scene_quest and scene_quest.scenes.filter(key=incoming_key).exclude(pk=scene.pk).exists():
            raise ValueError(f'A scene with key "{incoming_key}" already exists in this quest.')
        scene.key = incoming_key
    scene.scene_type = parsed["scene_type"] or scene.scene_type
    scene.ending_type = parsed["ending_type"]
    scene.body = parsed["description"]
    scene.requires_roll = parsed["requires_roll"]
    scene.roll_stat = parsed["roll_stat"]
    scene.roll_difficulty = parsed["roll_difficulty"]
    scene.consume_item_id = parsed["consume_item_id"]
    scene.cash_change = parsed["cash_change"]
    scene.rep_change = parsed["rep_change"]
    scene.heat_change = parsed["heat_change"]
    scene.receive_property_id = parsed["receive_property_id"]
    scene.lose_property_id = parsed["lose_property_id"]
    scene.receive_territory_id = parsed["receive_territory_id"]
    scene.lose_territory_id = parsed["lose_territory_id"]

    try:
        scene.clean()
    except ValidationError as exc:
        raise_authoring_validation_error(exc)
    scene.save()
    return scene


def get_delete_scene_consequences(scene_id):
    target_qs = Choice.objects.filter(target_scene_id=scene_id).select_related("scene")
    success_qs = Choice.objects.filter(success_scene_id=scene_id).select_related("scene")
    failure_qs = Choice.objects.filter(failure_scene_id=scene_id).select_related("scene")
    affected_choices = list({c.id: c for c in list(target_qs) + list(success_qs) + list(failure_qs)}.values())
    victory_encounters = list(CombatEncounter.objects.filter(victory_scene_id=scene_id).select_related("scene", "enemy"))
    defeat_encounters = list(CombatEncounter.objects.filter(defeat_scene_id=scene_id).select_related("scene", "enemy"))
    return {
        "affected_choices": affected_choices,
        "victory_encounters": victory_encounters,
        "defeat_encounters": defeat_encounters,
    }


def delete_scene(scene_id):
    scene = Scene.objects.get(pk=scene_id)
    target_qs = Choice.objects.filter(target_scene_id=scene_id)
    success_qs = Choice.objects.filter(success_scene_id=scene_id)
    failure_qs = Choice.objects.filter(failure_scene_id=scene_id)
    affected_choice_ids = sorted({
        *target_qs.values_list("id", flat=True),
        *success_qs.values_list("id", flat=True),
        *failure_qs.values_list("id", flat=True),
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
    parsed = parse_choice_form(data)
    choice = Choice(
        scene=scene,
        label=parsed["label"],
        target_scene_id=parsed["target_scene_id"],
        success_scene_id=parsed["success_scene_id"],
        failure_scene_id=parsed["failure_scene_id"],
        set_flag_name=parsed["set_flag_name"],
        clear_flag_name=parsed["clear_flag_name"],
        arrival_flavor=parsed["arrival_flavor"],
        failure_arrival_flavor=parsed["failure_arrival_flavor"],
    )
    try:
        choice.full_clean()
    except ValidationError as exc:
        raise_authoring_validation_error(exc)
    choice.save()
    return choice


def update_choice(choice_id, data):
    choice = Choice.objects.get(pk=choice_id)
    parsed = parse_choice_form(data)
    choice.label = parsed["label"]
    choice.target_scene_id = parsed["target_scene_id"]
    choice.success_scene_id = parsed["success_scene_id"]
    choice.failure_scene_id = parsed["failure_scene_id"]
    choice.set_flag_name = parsed["set_flag_name"]
    choice.clear_flag_name = parsed["clear_flag_name"]
    choice.arrival_flavor = parsed["arrival_flavor"]
    choice.failure_arrival_flavor = parsed["failure_arrival_flavor"]
    try:
        choice.full_clean()
    except ValidationError as exc:
        raise_authoring_validation_error(exc)
    choice.save()
    return choice


def delete_choice(choice_id):
    choice = Choice.objects.get(pk=choice_id)
    source_scene_id = choice.scene_id
    choice.delete()
    return source_scene_id


def save_scene_position(scene_id, x, y):
    Scene.objects.filter(pk=scene_id).update(canvas_x=x, canvas_y=y)


def update_scene_items(scene_id, items_data):
    with transaction.atomic():
        SceneItem.objects.filter(scene_id=scene_id).delete()
        created = []
        for entry in items_data:
            raw_id = str(entry.get("item_id") or "").strip()
            if not raw_id:
                continue
            raw_qty = str(entry.get("quantity") or "").strip()
            quantity = int(raw_qty) if raw_qty else 1
            scene_item = SceneItem.objects.create(scene_id=scene_id, item_id=int(raw_id), quantity=quantity)
            created.append(scene_item)
    return created


def update_scene_contacts(scene_id, contacts_data):
    with transaction.atomic():
        SceneContact.objects.filter(scene_id=scene_id).delete()
        created = []
        for entry in contacts_data:
            raw_id = str(entry.get("contact_id") or "").strip()
            if not raw_id:
                continue
            raw_action = str(entry.get("action") or "").strip()
            action = raw_action if raw_action in ("gain", "lose") else "gain"
            award_once = entry.get("award_once", True)
            if award_once is None:
                award_once = True
            scene_contact = SceneContact.objects.create(
                scene_id=scene_id, contact_id=int(raw_id), action=action, award_once=bool(award_once)
            )
            created.append(scene_contact)
    return created


def update_combat_encounter(scene_id, data):
    parsed = parse_combat_form(data)
    if parsed is None:
        CombatEncounter.objects.filter(scene_id=scene_id).delete()
        return None
    encounter, _ = CombatEncounter.objects.update_or_create(scene_id=scene_id, defaults=parsed)
    return encounter
