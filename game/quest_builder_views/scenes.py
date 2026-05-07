"""Scene-focused quest-builder views for panel, mutations, and section saves."""

from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string

from game.constants import STAT_DISPLAY_NAMES
from game.models import (
    Choice,
    CombatEncounter,
    Contact,
    Gang,
    Item,
    Property,
    Quest,
    Requirement,
    Scene,
    Territory,
)
from game.models.combat import Enemy as EnemyModel
from game.presentation import responses as response_utils
from game.quest_builder_views.partials import qb_error
from game.services.quest_builder import (
    create_scene as create_scene_service,
    delete_scene as delete_scene_service,
    get_delete_scene_consequences as get_delete_scene_consequences_service,
    get_scene_hub_exits,
    parse_scene_contacts_rows as parse_scene_contacts_rows_service,
    parse_scene_items_rows as parse_scene_items_rows_service,
    save_scene_position as save_scene_position_service,
    update_combat_encounter as update_combat_encounter_service,
    update_scene as update_scene_service,
    update_scene_contacts as update_scene_contacts_service,
    update_scene_gang_standings as update_scene_gang_standings_service,
    update_scene_items as update_scene_items_service,
)


def scene_panel(request, quest_id, scene_id=None):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    quest = get_object_or_404(Quest, pk=quest_id)
    scene = None
    scene_choices = []
    scene_items = []
    scene_gang_standings = []
    combat_encounter = None
    if scene_id is not None:
        scene = get_object_or_404(quest.scenes.all(), pk=scene_id)
        scene_choices = list(
            Choice.objects.filter(scene=scene)
            .select_related("target_scene", "success_scene", "failure_scene")
            .order_by("order")
        )
        scene_items = list(scene.scene_items.select_related("item").order_by("id"))
        scene_gang_standings = list(scene.scene_gang_standings.select_related("gang").order_by("id"))
        try:
            combat_encounter = scene.combat_encounter
        except CombatEncounter.DoesNotExist:
            combat_encounter = None

    scene_contacts = list(scene.scene_contacts.select_related("contact").order_by("id")) if scene else []
    all_contacts = list(Contact.objects.order_by("name"))
    all_items = list(Item.objects.order_by("name"))
    all_enemies = list(EnemyModel.objects.order_by("name"))
    all_quests = list(Quest.objects.order_by("title"))
    all_gangs = list(Gang.objects.order_by("name"))
    all_properties = list(Property.objects.order_by("name"))
    all_territories = list(Territory.objects.order_by("name"))
    quest_scenes = list(quest.scenes.only("id", "key", "title").order_by("order"))

    context = {
        "quest_id": quest_id,
        "scene": scene,
        "scene_choices": scene_choices,
        "scene_types": Scene.SCENE_TYPES,
        "roll_stat_options": list(STAT_DISPLAY_NAMES.items()),
        "default_roll_difficulty": 12,
        "scene_items": scene_items,
        "all_items": all_items,
        "scene_contacts": scene_contacts,
        "all_contacts": all_contacts,
        "all_enemies": all_enemies,
        "all_properties": all_properties,
        "all_territories": all_territories,
        "quest_scenes": quest_scenes,
        "combat_encounter": combat_encounter,
        "all_quests": all_quests,
        "all_gangs": all_gangs,
        "stat_choices": [(field, label) for field, label in STAT_DISPLAY_NAMES.items()],
        "requirement_types": Requirement.CONDITION_TYPES,
        "scene_gang_standings": scene_gang_standings,
    }
    return render(request, "admin/quest_builder/partials/scene_panel.html", context)


def scene_save(request, quest_id, scene_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    quest = get_object_or_404(Quest, pk=quest_id)
    get_object_or_404(quest.scenes.all(), pk=scene_id)
    try:
        scene = update_scene_service(scene_id, request.POST)
    except ValueError as exc:
        return qb_error(request, str(exc), status=400)

    scene.hub_exits = get_scene_hub_exits(scene.id, quest_id)
    html = render_to_string(
        "admin/quest_builder/partials/scene_save_response.html",
        {"scene": scene, "quest_id": quest_id, "toast_message": f'Scene "{scene.title}" saved.'},
        request=request,
    )
    response = HttpResponse(html)
    response_utils.attach_triggers(response, {"sceneUpdated": {"sceneId": scene.id}, "scene.updated": {"sceneId": scene.id}})
    return response


def scene_create(request, quest_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    get_object_or_404(Quest, pk=quest_id)
    try:
        scene = create_scene_service(quest_id, request.POST)
    except ValueError as exc:
        return qb_error(request, str(exc), status=400)

    html = render_to_string(
        "admin/quest_builder/partials/scene_create_response.html",
        {"scene": scene, "quest_id": quest_id, "toast_message": f'Scene "{scene.title}" created.'},
        request=request,
    )
    response = HttpResponse(html)
    response_utils.attach_triggers(response, {"sceneUpdated": {"sceneId": scene.id}, "scene.updated": {"sceneId": scene.id}})
    return response


def scene_delete(request, quest_id, scene_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    quest = get_object_or_404(Quest, pk=quest_id)
    scene = get_object_or_404(quest.scenes.all(), pk=scene_id)

    if request.POST.get("confirmed") != "1":
        consequences = get_delete_scene_consequences_service(scene_id)
        html = render_to_string(
            "admin/quest_builder/partials/scene_delete_confirm.html",
            {
                "scene": scene,
                "quest_id": quest_id,
                "affected_choices": consequences["affected_choices"],
                "victory_encounters": consequences["victory_encounters"],
                "defeat_encounters": consequences["defeat_encounters"],
            },
            request=request,
        )
        return HttpResponse(html)

    affected_choice_ids = delete_scene_service(scene_id)
    html = render_to_string(
        "admin/quest_builder/partials/scene_delete_response.html",
        {"scene_id": scene_id, "scene_title": scene.title, "affected_choice_ids": affected_choice_ids},
        request=request,
    )
    response = HttpResponse(html)
    response_utils.attach_triggers(response, {"sceneUpdated": {"sceneId": scene_id}, "scene.updated": {"sceneId": scene_id}})
    return response


def scene_move(request, quest_id, scene_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    quest = get_object_or_404(Quest, pk=quest_id)
    get_object_or_404(quest.scenes.all(), pk=scene_id)

    try:
        x = int((request.POST.get("x") or "").strip())
        y = int((request.POST.get("y") or "").strip())
    except (TypeError, ValueError):
        return qb_error(request, "x and y must be integers", status=400)

    save_scene_position_service(scene_id, x, y)
    return HttpResponse(status=204)


def scene_items_save(request, quest_id, scene_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    quest = get_object_or_404(Quest, pk=quest_id)
    scene = get_object_or_404(quest.scenes.all(), pk=scene_id)

    try:
        items_data = parse_scene_items_rows_service(request.POST)
    except ValueError as exc:
        return qb_error(request, str(exc), status=400)

    scene_items = update_scene_items_service(scene.id, items_data)
    all_items = list(Item.objects.order_by("name"))

    html = render_to_string(
        "admin/quest_builder/partials/items_section.html",
        {
            "quest_id": quest_id,
            "scene": scene,
            "scene_items": scene_items,
            "all_items": all_items,
            "toast_message": "Items saved.",
        },
        request=request,
    )
    return HttpResponse(html)


def scene_contacts_save(request, quest_id, scene_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    quest = get_object_or_404(Quest, pk=quest_id)
    scene = get_object_or_404(quest.scenes.all(), pk=scene_id)

    try:
        contacts_data = parse_scene_contacts_rows_service(request.POST)
    except ValueError as exc:
        return qb_error(request, str(exc), status=400)

    scene_contacts = update_scene_contacts_service(scene.id, contacts_data)
    all_contacts = list(Contact.objects.order_by("name"))

    html = render_to_string(
        "admin/quest_builder/partials/contacts_section.html",
        {
            "quest_id": quest_id,
            "scene": scene,
            "scene_contacts": scene_contacts,
            "all_contacts": all_contacts,
            "toast_message": "Contacts saved.",
        },
        request=request,
    )
    return HttpResponse(html)


def scene_gang_standings_save(request, quest_id, scene_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    quest = get_object_or_404(Quest, pk=quest_id)
    scene = get_object_or_404(quest.scenes.all(), pk=scene_id)

    standings_data = []
    index = 0
    while True:
        gang_id_key = f"gang_id_{index}"
        standing_change_key = f"standing_change_{index}"
        if gang_id_key not in request.POST and standing_change_key not in request.POST:
            break
        standings_data.append(
            {
                "gang_id": request.POST.get(gang_id_key, ""),
                "standing_change": request.POST.get(standing_change_key, "0"),
            }
        )
        index += 1

    scene_gang_standings = update_scene_gang_standings_service(scene.id, standings_data)
    all_gangs = list(Gang.objects.order_by("name"))

    html = render_to_string(
        "admin/quest_builder/partials/gang_standings_section.html",
        {
            "quest_id": quest_id,
            "scene": scene,
            "scene_gang_standings": scene_gang_standings,
            "all_gangs": all_gangs,
            "toast_message": "Gang standings saved.",
        },
        request=request,
    )
    return HttpResponse(html)


def scene_combat_save(request, quest_id, scene_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    quest = get_object_or_404(Quest, pk=quest_id)
    scene = get_object_or_404(quest.scenes.all(), pk=scene_id)

    encounter = update_combat_encounter_service(scene.id, request.POST)
    all_enemies = list(EnemyModel.objects.order_by("name"))
    quest_scenes = list(quest.scenes.only("id", "key", "title").order_by("order"))

    html = render_to_string(
        "admin/quest_builder/partials/combat_section.html",
        {
            "quest_id": quest_id,
            "scene": scene,
            "combat_encounter": encounter,
            "all_enemies": all_enemies,
            "quest_scenes": quest_scenes,
            "toast_message": "Combat encounter saved.",
        },
        request=request,
    )
    return HttpResponse(html)
