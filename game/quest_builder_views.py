from collections import defaultdict

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseNotAllowed
from django.template.loader import render_to_string
from django.urls import reverse

from .models import Choice, Contact, CombatEncounter, Item, Property, Quest, Requirement, Scene
from .models.combat import Enemy as EnemyModel
from .services.quest_builder import (
    get_canvas_data,
    get_scene_hub_exits,
    validate_quest as validate_quest_service,
    create_scene as create_scene_service,
    update_scene as update_scene_service,
    delete_scene as delete_scene_service,
    get_delete_scene_consequences as get_delete_scene_consequences_service,
    create_choice as create_choice_service,
    update_choice as update_choice_service,
    delete_choice as delete_choice_service,
    save_scene_position as save_scene_position_service,
    update_scene_items as update_scene_items_service,
    update_combat_encounter as update_combat_encounter_service,
    build_requirement_groups_from_post as build_requirement_groups_from_post_service,
    update_scene_contacts as update_scene_contacts_service,
)
from .constants import STAT_DISPLAY_NAMES
from .presentation import responses as response_utils


def _choice_context(*, quest, quest_id, choice=None, source_scene_id=None, routing_type='direct'):
    scenes = list(
        quest.scenes
        .only('id', 'key', 'title', 'scene_type')
        .order_by('order')
    )
    quest_scene_ids = {s.id for s in scenes}
    hub_scenes = list(
        Scene.objects.filter(scene_type='hub')
        .exclude(pk__in=quest_scene_ids)
        .only('id', 'key', 'title')
        .order_by('title')
    )
    source_scene = (
        Scene.objects.filter(pk=source_scene_id).only('id', 'scene_type').first()
        if source_scene_id else None
    )
    requirement_groups = (
        list(choice.requirements.prefetch_related('requirements').all())
        if choice else []
    )
    req_save_url = (
        reverse('admin:quest_builder_choice_requirements_save', args=[quest_id, choice.id])
        if choice else ''
    )
    return {
        'quest_id':            quest_id,
        'source_scene_id':     source_scene_id,
        'source_scene':        source_scene,
        'choice':              choice,
        'scenes':              scenes,
        'hub_scenes':          hub_scenes,
        'routing_type':        routing_type,
        'requirement_groups':  requirement_groups,
        'req_save_url':        req_save_url,
        'all_quests':          list(Quest.objects.order_by('title')),
        'all_items':           list(Item.objects.order_by('name')),
        'stat_choices':        [(field, label) for field, label in STAT_DISPLAY_NAMES.items()],
        'requirement_types':   Requirement.CONDITION_TYPES,
    }


def quest_validate(request, quest_id):
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    get_object_or_404(Quest, pk=quest_id)
    warnings = validate_quest_service(quest_id)

    html = render_to_string(
        'admin/quest_builder/partials/validation_panel.html',
        {'warnings': warnings},
        request=request,
    )
    return HttpResponse(html)


def quest_builder_list(request):
    quests = Quest.objects.select_related('arc').order_by('arc__order', 'arc_order', 'title')

    quests_by_arc = defaultdict(list)
    for q in quests:
        arc_title = q.arc.title if q.arc else "No Arc"
        quests_by_arc[arc_title].append(q)

    context = {
        'quests_by_arc': dict(quests_by_arc),
        'title': 'Quest Builder',
    }
    return render(request, 'admin/quest_builder/list.html', context)


def quest_builder_canvas(request, quest_id):
    canvas_data = get_canvas_data(quest_id)
    context = {
        **canvas_data,
        'title': f"Quest Builder - {canvas_data['quest'].title}",
    }
    return render(request, 'admin/quest_builder/canvas.html', context)


def scene_panel(request, quest_id, scene_id=None):
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    quest = get_object_or_404(Quest, pk=quest_id)
    scene = None
    scene_choices = []
    scene_items = []
    combat_encounter = None
    if scene_id is not None:
        scene = get_object_or_404(quest.scenes.all(), pk=scene_id)
        scene_choices = list(
            Choice.objects.filter(scene=scene)
            .select_related('target_scene', 'success_scene', 'failure_scene')
            .order_by('order')
        )
        scene_items = list(
            scene.scene_items.select_related('item').order_by('id')
        )
        try:
            combat_encounter = scene.combat_encounter
        except CombatEncounter.DoesNotExist:
            combat_encounter = None

    scene_contacts = list(scene.scene_contacts.select_related('contact').order_by('id')) if scene else []
    all_contacts = list(Contact.objects.order_by('name'))
    all_items = list(Item.objects.order_by('name'))
    all_enemies = list(EnemyModel.objects.order_by('name'))
    all_quests = list(Quest.objects.order_by('title'))
    all_properties = list(Property.objects.order_by('name'))
    quest_scenes = list(
        quest.scenes.only('id', 'key', 'title').order_by('order')
    )

    context = {
        'quest_id':              quest_id,
        'scene':                 scene,
        'scene_choices':         scene_choices,
        'scene_types':           Scene.SCENE_TYPES,
        'roll_stat_options': list(STAT_DISPLAY_NAMES.items()),
        'default_roll_difficulty': 12,
        'scene_items':           scene_items,
        'all_items':             all_items,
        'scene_contacts':        scene_contacts,
        'all_contacts':          all_contacts,
        'all_enemies':           all_enemies,
        'all_properties':        all_properties,
        'quest_scenes':          quest_scenes,
        'combat_encounter':      combat_encounter,
        'all_quests':            all_quests,
        'stat_choices':          [(field, label) for field, label in STAT_DISPLAY_NAMES.items()],
        'requirement_types':     Requirement.CONDITION_TYPES,
    }
    return render(request, 'admin/quest_builder/partials/scene_panel.html', context)


def scene_save(request, quest_id, scene_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    get_object_or_404(quest.scenes.all(), pk=scene_id)
    try:
        scene = update_scene_service(scene_id, request.POST)
    except ValueError as exc:
        return response_utils.error_response(
            request,
            message=str(exc),
            status=400,
            htmx_template='admin/quest_builder/partials/inline_error.html',
            full_template='admin/quest_builder/partials/inline_error.html',
            triggers={'quest_builder.error': {'message': str(exc), 'status': 400}},
        )

    scene.hub_exits = get_scene_hub_exits(scene.id, quest_id)
    html = render_to_string(
        'admin/quest_builder/partials/scene_save_response.html',
        {
            'scene':         scene,
            'quest_id':      quest_id,
            'toast_message': f'Scene "{scene.title}" saved.',
        },
        request=request,
    )
    response = HttpResponse(html)
    response_utils.attach_triggers(response, {
        'sceneUpdated': {'sceneId': scene.id},
        'scene.updated': {'sceneId': scene.id},
    })
    return response


def scene_create(request, quest_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    get_object_or_404(Quest, pk=quest_id)
    try:
        scene = create_scene_service(quest_id, request.POST)
    except ValueError as exc:
        return response_utils.error_response(
            request,
            message=str(exc),
            status=400,
            htmx_template='admin/quest_builder/partials/inline_error.html',
            full_template='admin/quest_builder/partials/inline_error.html',
            triggers={'quest_builder.error': {'message': str(exc), 'status': 400}},
        )

    html = render_to_string(
        'admin/quest_builder/partials/scene_create_response.html',
        {
            'scene':         scene,
            'quest_id':      quest_id,
            'toast_message': f'Scene "{scene.title}" created.',
        },
        request=request,
    )
    response = HttpResponse(html)
    response_utils.attach_triggers(response, {
        'sceneUpdated': {'sceneId': scene.id},
        'scene.updated': {'sceneId': scene.id},
    })
    return response


def scene_delete(request, quest_id, scene_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    scene = get_object_or_404(quest.scenes.all(), pk=scene_id)

    if request.POST.get('confirmed') != '1':
        consequences = get_delete_scene_consequences_service(scene_id)
        html = render_to_string(
            'admin/quest_builder/partials/scene_delete_confirm.html',
            {
                'scene':              scene,
                'quest_id':           quest_id,
                'affected_choices':   consequences['affected_choices'],
                'victory_encounters': consequences['victory_encounters'],
                'defeat_encounters':  consequences['defeat_encounters'],
            },
            request=request,
        )
        return HttpResponse(html)

    affected_choice_ids = delete_scene_service(scene_id)

    html = render_to_string(
        'admin/quest_builder/partials/scene_delete_response.html',
        {
            'scene_id':           scene_id,
            'scene_title':        scene.title,
            'affected_choice_ids': affected_choice_ids,
        },
        request=request,
    )
    response = HttpResponse(html)
    response_utils.attach_triggers(response, {
        'sceneUpdated': {'sceneId': scene_id},
        'scene.updated': {'sceneId': scene_id},
    })
    return response


def scene_move(request, quest_id, scene_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    get_object_or_404(quest.scenes.all(), pk=scene_id)

    try:
        x = int((request.POST.get('x') or '').strip())
        y = int((request.POST.get('y') or '').strip())
    except (TypeError, ValueError):
        return response_utils.error_response(
            request,
            message="x and y must be integers",
            status=400,
            htmx_template='admin/quest_builder/partials/inline_error.html',
            full_template='admin/quest_builder/partials/inline_error.html',
            triggers={'quest_builder.error': {'message': 'x and y must be integers', 'status': 400}},
        )

    save_scene_position_service(scene_id, x, y)
    return HttpResponse(status=204)


def scene_items_save(request, quest_id, scene_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    scene = get_object_or_404(quest.scenes.all(), pk=scene_id)

    items_data = []
    index = 0
    while True:
        item_id_key = f'item_id_{index}'
        qty_key = f'quantity_{index}'
        if item_id_key not in request.POST and qty_key not in request.POST:
            break
        items_data.append({
            'item_id':  request.POST.get(item_id_key, ''),
            'quantity': request.POST.get(qty_key, '1'),
        })
        index += 1

    scene_items = update_scene_items_service(scene.id, items_data)
    all_items = list(Item.objects.order_by('name'))

    html = render_to_string(
        'admin/quest_builder/partials/items_section.html',
        {
            'quest_id':      quest_id,
            'scene':         scene,
            'scene_items':   scene_items,
            'all_items':     all_items,
            'toast_message': 'Items saved.',
        },
        request=request,
    )
    return HttpResponse(html)


def scene_contacts_save(request, quest_id, scene_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    scene = get_object_or_404(quest.scenes.all(), pk=scene_id)

    contacts_data = []
    index = 0
    while True:
        contact_id_key = f'contact_id_{index}'
        action_key = f'action_{index}'
        award_once_key = f'award_once_{index}'
        if contact_id_key not in request.POST and action_key not in request.POST and award_once_key not in request.POST:
            break
        raw_award_once = (request.POST.get(award_once_key) or '').strip().lower()
        contacts_data.append({
            'contact_id': request.POST.get(contact_id_key, ''),
            'action': request.POST.get(action_key, ''),
            'award_once': raw_award_once in ('on', '1', 'true', 'yes'),
        })
        index += 1

    scene_contacts = update_scene_contacts_service(scene.id, contacts_data)
    all_contacts = list(Contact.objects.order_by('name'))

    html = render_to_string(
        'admin/quest_builder/partials/contacts_section.html',
        {
            'quest_id':      quest_id,
            'scene':         scene,
            'scene_contacts': scene_contacts,
            'all_contacts':  all_contacts,
            'toast_message': 'Contacts saved.',
        },
        request=request,
    )
    return HttpResponse(html)


def scene_combat_save(request, quest_id, scene_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    scene = get_object_or_404(quest.scenes.all(), pk=scene_id)

    encounter = update_combat_encounter_service(scene.id, request.POST)
    all_enemies = list(EnemyModel.objects.order_by('name'))
    quest_scenes = list(
        quest.scenes.only('id', 'key', 'title').order_by('order')
    )

    html = render_to_string(
        'admin/quest_builder/partials/combat_section.html',
        {
            'quest_id':        quest_id,
            'scene':           scene,
            'combat_encounter': encounter,
            'all_enemies':     all_enemies,
            'quest_scenes':    quest_scenes,
            'toast_message':   'Combat encounter saved.',
        },
        request=request,
    )
    return HttpResponse(html)


def choice_panel(request, quest_id, source_scene_id=None, choice_id=None):
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    quest = get_object_or_404(Quest, pk=quest_id)
    choice = None
    routing_type = 'direct'

    if choice_id is not None:
        choice = get_object_or_404(Choice, pk=choice_id)
        source_scene_id = choice.scene_id
        if choice.success_scene_id or choice.failure_scene_id:
            routing_type = 'roll'

    context = _choice_context(
        quest=quest,
        quest_id=quest_id,
        choice=choice,
        source_scene_id=source_scene_id,
        routing_type=routing_type,
    )
    return render(request, 'admin/quest_builder/partials/choice_panel.html', context)


def choice_create(request, quest_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    raw_source = (request.POST.get('source_scene_id') or '').strip()
    if not raw_source:
        return response_utils.error_response(
            request,
            message="source_scene_id required",
            status=400,
            htmx_template='admin/quest_builder/partials/inline_error.html',
            full_template='admin/quest_builder/partials/inline_error.html',
            triggers={'quest_builder.error': {'message': 'source_scene_id required', 'status': 400}},
        )
    try:
        source_scene_id = int(raw_source)
    except ValueError:
        return response_utils.error_response(
            request,
            message="source_scene_id must be a valid integer",
            status=400,
            htmx_template='admin/quest_builder/partials/inline_error.html',
            full_template='admin/quest_builder/partials/inline_error.html',
            triggers={'quest_builder.error': {'message': 'source_scene_id must be a valid integer', 'status': 400}},
        )

    if not quest.scenes.filter(pk=source_scene_id).exists():
        return response_utils.error_response(
            request,
            message="Source scene does not belong to this quest.",
            status=403,
            htmx_template='admin/quest_builder/partials/inline_error.html',
            full_template='admin/quest_builder/partials/inline_error.html',
            triggers={'quest_builder.error': {'message': 'Source scene does not belong to this quest.', 'status': 403}},
        )

    choice = create_choice_service(source_scene_id, request.POST)
    routing_type = 'roll' if (choice.success_scene_id or choice.failure_scene_id) else 'direct'

    context = _choice_context(
        quest=quest,
        quest_id=quest_id,
        choice=choice,
        source_scene_id=choice.scene_id,
        routing_type=routing_type,
    )
    html = render_to_string(
        'admin/quest_builder/partials/choice_panel.html',
        context,
        request=request,
    )
    response = HttpResponse(html)
    response_utils.attach_triggers(response, {
        'choiceCreated': {
            'id':               choice.id,
            'quest_id':         quest_id,
            'source_scene_id':  choice.scene_id,
            'routing_type':     routing_type,
            'target_scene_id':  choice.target_scene_id,
            'success_scene_id': choice.success_scene_id,
            'failure_scene_id': choice.failure_scene_id,
            'label':            choice.label,
        },
        'choice.created': {
            'id':               choice.id,
            'questId':          quest_id,
            'sourceSceneId':    choice.scene_id,
            'routingType':      routing_type,
            'targetSceneId':    choice.target_scene_id,
            'successSceneId':   choice.success_scene_id,
            'failureSceneId':   choice.failure_scene_id,
            'label':            choice.label,
        },
    })
    return response


def choice_save(request, quest_id, choice_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    choice_check = get_object_or_404(Choice, pk=choice_id)
    if not quest.scenes.filter(pk=choice_check.scene_id).exists():
        return response_utils.error_response(
            request,
            message="Choice does not belong to this quest.",
            status=403,
            htmx_template='admin/quest_builder/partials/inline_error.html',
            full_template='admin/quest_builder/partials/inline_error.html',
            triggers={'quest_builder.error': {'message': 'Choice does not belong to this quest.', 'status': 403}},
        )
    choice = update_choice_service(choice_id, request.POST)
    build_requirement_groups_from_post_service(choice, request.POST)
    routing_type = 'roll' if (choice.success_scene_id or choice.failure_scene_id) else 'direct'

    response = response_utils.empty_response()
    response_utils.attach_triggers(response, {
        'choiceUpdated': {
            'id':               choice.id,
            'source_scene_id':  choice.scene_id,
            'routing_type':     routing_type,
            'target_scene_id':  choice.target_scene_id,
            'success_scene_id': choice.success_scene_id,
            'failure_scene_id': choice.failure_scene_id,
            'label':            choice.label,
        },
        'choice.updated': {
            'id':               choice.id,
            'sourceSceneId':    choice.scene_id,
            'routingType':      routing_type,
            'targetSceneId':    choice.target_scene_id,
            'successSceneId':   choice.success_scene_id,
            'failureSceneId':   choice.failure_scene_id,
            'label':            choice.label,
        },
    })
    return response


def choice_delete(request, quest_id, choice_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    choice = get_object_or_404(Choice, pk=choice_id)
    if not quest.scenes.filter(pk=choice.scene_id).exists():
        return response_utils.error_response(
            request,
            message="Choice does not belong to this quest.",
            status=403,
            htmx_template='admin/quest_builder/partials/inline_error.html',
            full_template='admin/quest_builder/partials/inline_error.html',
            triggers={'quest_builder.error': {'message': 'Choice does not belong to this quest.', 'status': 403}},
        )
    source_scene_id = delete_choice_service(choice_id)

    response = response_utils.empty_response()
    response_utils.attach_triggers(response, {
        'choiceDeleted': {
            'id':              choice_id,
            'source_scene_id': source_scene_id,
        },
        'choice.deleted': {
            'id':           choice_id,
            'sourceSceneId': source_scene_id,
        },
    })
    return response


def choice_requirements_save(request, quest_id, choice_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    quest = get_object_or_404(Quest, pk=quest_id)
    choice = get_object_or_404(Choice, pk=choice_id)
    if not quest.scenes.filter(pk=choice.scene_id).exists():
        return response_utils.error_response(
            request,
            message="Choice does not belong to this quest.",
            status=403,
            htmx_template='admin/quest_builder/partials/inline_error.html',
            full_template='admin/quest_builder/partials/inline_error.html',
            triggers={'quest_builder.error': {'message': 'Choice does not belong to this quest.', 'status': 403}},
        )
    build_requirement_groups_from_post_service(choice, request.POST)

    html = render_to_string(
        'admin/quest_builder/partials/requirements_section.html',
        {
            'quest_id':           quest_id,
            'requirement_groups': list(choice.requirements.prefetch_related('requirements').all()),
            'save_url':           reverse('admin:quest_builder_choice_requirements_save', args=[quest_id, choice_id]),
            'all_quests':         list(Quest.objects.order_by('title')),
            'all_items':          list(Item.objects.order_by('name')),
            'all_contacts':       list(Contact.objects.order_by('name')),
            'stat_choices':       [(field, label) for field, label in STAT_DISPLAY_NAMES.items()],
            'requirement_types':  Requirement.CONDITION_TYPES,
            'toast_message':      'Requirements saved.',
        },
        request=request,
    )
    return HttpResponse(html)
