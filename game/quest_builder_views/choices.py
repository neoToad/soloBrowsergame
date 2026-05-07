"""Choice-focused quest-builder views for panel rendering and CRUD handlers."""

from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse

from game.constants import STAT_DISPLAY_NAMES
from game.models import Choice, Contact, Item, Quest, Requirement
from game.presentation import responses as response_utils
from game.quest_builder_views.partials import choice_context
from game.services.quest_builder import (
    build_requirement_groups_from_post as build_requirement_groups_from_post_service,
    create_choice as create_choice_service,
    delete_choice as delete_choice_service,
    update_choice as update_choice_service,
)


def choice_panel(request, quest_id, source_scene_id=None, choice_id=None):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    quest = get_object_or_404(Quest, pk=quest_id)
    choice = None
    routing_type = "direct"

    if choice_id is not None:
        choice = get_object_or_404(Choice, pk=choice_id)
        source_scene_id = choice.scene_id
        if choice.success_scene_id or choice.failure_scene_id:
            routing_type = "roll"

    context = choice_context(
        quest=quest,
        quest_id=quest_id,
        choice=choice,
        source_scene_id=source_scene_id,
        routing_type=routing_type,
    )
    return render(request, "admin/quest_builder/partials/choice_panel.html", context)


def choice_create(request, quest_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    quest = get_object_or_404(Quest, pk=quest_id)
    raw_source = (request.POST.get("source_scene_id") or "").strip()
    if not raw_source:
        return response_utils.error_response(
            request,
            message="source_scene_id required",
            status=400,
            htmx_template="admin/quest_builder/partials/inline_error.html",
            full_template="admin/quest_builder/partials/inline_error.html",
            triggers={"quest_builder.error": {"message": "source_scene_id required", "status": 400}},
        )
    try:
        source_scene_id = int(raw_source)
    except ValueError:
        return response_utils.error_response(
            request,
            message="source_scene_id must be a valid integer",
            status=400,
            htmx_template="admin/quest_builder/partials/inline_error.html",
            full_template="admin/quest_builder/partials/inline_error.html",
            triggers={"quest_builder.error": {"message": "source_scene_id must be a valid integer", "status": 400}},
        )

    if not quest.scenes.filter(pk=source_scene_id).exists():
        return response_utils.error_response(
            request,
            message="Source scene does not belong to this quest.",
            status=403,
            htmx_template="admin/quest_builder/partials/inline_error.html",
            full_template="admin/quest_builder/partials/inline_error.html",
            triggers={"quest_builder.error": {"message": "Source scene does not belong to this quest.", "status": 403}},
        )

    try:
        choice = create_choice_service(source_scene_id, request.POST)
    except ValueError as exc:
        return response_utils.error_response(
            request,
            message=str(exc),
            status=400,
            htmx_template="admin/quest_builder/partials/inline_error.html",
            full_template="admin/quest_builder/partials/inline_error.html",
            triggers={"quest_builder.error": {"message": str(exc), "status": 400}},
        )
    routing_type = "roll" if (choice.success_scene_id or choice.failure_scene_id) else "direct"

    context = choice_context(
        quest=quest,
        quest_id=quest_id,
        choice=choice,
        source_scene_id=choice.scene_id,
        routing_type=routing_type,
    )
    html = render_to_string("admin/quest_builder/partials/choice_panel.html", context, request=request)
    response = HttpResponse(html)
    response_utils.attach_triggers(
        response,
        {
            "choiceCreated": {
                "id": choice.id,
                "quest_id": quest_id,
                "source_scene_id": choice.scene_id,
                "routing_type": routing_type,
                "target_scene_id": choice.target_scene_id,
                "success_scene_id": choice.success_scene_id,
                "failure_scene_id": choice.failure_scene_id,
                "label": choice.label,
            },
            "choice.created": {
                "id": choice.id,
                "questId": quest_id,
                "sourceSceneId": choice.scene_id,
                "routingType": routing_type,
                "targetSceneId": choice.target_scene_id,
                "successSceneId": choice.success_scene_id,
                "failureSceneId": choice.failure_scene_id,
                "label": choice.label,
            },
        },
    )
    return response


def choice_save(request, quest_id, choice_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    quest = get_object_or_404(Quest, pk=quest_id)
    choice_check = get_object_or_404(Choice, pk=choice_id)
    if not quest.scenes.filter(pk=choice_check.scene_id).exists():
        return response_utils.error_response(
            request,
            message="Choice does not belong to this quest.",
            status=403,
            htmx_template="admin/quest_builder/partials/inline_error.html",
            full_template="admin/quest_builder/partials/inline_error.html",
            triggers={"quest_builder.error": {"message": "Choice does not belong to this quest.", "status": 403}},
        )
    try:
        choice = update_choice_service(choice_id, request.POST)
    except ValueError as exc:
        return response_utils.error_response(
            request,
            message=str(exc),
            status=400,
            htmx_template="admin/quest_builder/partials/inline_error.html",
            full_template="admin/quest_builder/partials/inline_error.html",
            triggers={"quest_builder.error": {"message": str(exc), "status": 400}},
        )
    build_requirement_groups_from_post_service(choice, request.POST)
    routing_type = "roll" if (choice.success_scene_id or choice.failure_scene_id) else "direct"

    response = response_utils.empty_response()
    response_utils.attach_triggers(
        response,
        {
            "choiceUpdated": {
                "id": choice.id,
                "source_scene_id": choice.scene_id,
                "routing_type": routing_type,
                "target_scene_id": choice.target_scene_id,
                "success_scene_id": choice.success_scene_id,
                "failure_scene_id": choice.failure_scene_id,
                "label": choice.label,
            },
            "choice.updated": {
                "id": choice.id,
                "sourceSceneId": choice.scene_id,
                "routingType": routing_type,
                "targetSceneId": choice.target_scene_id,
                "successSceneId": choice.success_scene_id,
                "failureSceneId": choice.failure_scene_id,
                "label": choice.label,
            },
        },
    )
    return response


def choice_delete(request, quest_id, choice_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    quest = get_object_or_404(Quest, pk=quest_id)
    choice = get_object_or_404(Choice, pk=choice_id)
    if not quest.scenes.filter(pk=choice.scene_id).exists():
        return response_utils.error_response(
            request,
            message="Choice does not belong to this quest.",
            status=403,
            htmx_template="admin/quest_builder/partials/inline_error.html",
            full_template="admin/quest_builder/partials/inline_error.html",
            triggers={"quest_builder.error": {"message": "Choice does not belong to this quest.", "status": 403}},
        )
    source_scene_id = delete_choice_service(choice_id)

    response = response_utils.empty_response()
    response_utils.attach_triggers(
        response,
        {
            "choiceDeleted": {"id": choice_id, "source_scene_id": source_scene_id},
            "choice.deleted": {"id": choice_id, "sourceSceneId": source_scene_id},
        },
    )
    return response


def choice_requirements_save(request, quest_id, choice_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    quest = get_object_or_404(Quest, pk=quest_id)
    choice = get_object_or_404(Choice, pk=choice_id)
    if not quest.scenes.filter(pk=choice.scene_id).exists():
        return response_utils.error_response(
            request,
            message="Choice does not belong to this quest.",
            status=403,
            htmx_template="admin/quest_builder/partials/inline_error.html",
            full_template="admin/quest_builder/partials/inline_error.html",
            triggers={"quest_builder.error": {"message": "Choice does not belong to this quest.", "status": 403}},
        )
    build_requirement_groups_from_post_service(choice, request.POST)

    html = render_to_string(
        "admin/quest_builder/partials/requirements_section.html",
        {
            "quest_id": quest_id,
            "requirement_groups": list(choice.requirements.prefetch_related("requirements").all()),
            "save_url": reverse("admin:quest_builder_choice_requirements_save", args=[quest_id, choice_id]),
            "all_quests": list(Quest.objects.order_by("title")),
            "all_items": list(Item.objects.order_by("name")),
            "all_contacts": list(Contact.objects.order_by("name")),
            "stat_choices": [(field, label) for field, label in STAT_DISPLAY_NAMES.items()],
            "requirement_types": Requirement.CONDITION_TYPES,
            "toast_message": "Requirements saved.",
        },
        request=request,
    )
    return HttpResponse(html)
