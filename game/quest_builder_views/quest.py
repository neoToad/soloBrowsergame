"""Quest-level quest-builder views for list, canvas, and validation endpoints."""

from collections import defaultdict

from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string

from game.models import Quest
from game.services.quest_builder import get_canvas_data, validate_quest as validate_quest_service


def quest_validate(request, quest_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    get_object_or_404(Quest, pk=quest_id)
    warnings = validate_quest_service(quest_id)

    html = render_to_string(
        "admin/quest_builder/partials/validation_panel.html",
        {"warnings": warnings},
        request=request,
    )
    return HttpResponse(html)


def quest_builder_list(request):
    quests = Quest.objects.select_related("arc").order_by("arc__order", "arc_order", "title")

    quests_by_arc = defaultdict(list)
    for q in quests:
        arc_title = q.arc.title if q.arc else "No Arc"
        quests_by_arc[arc_title].append(q)

    context = {
        "quests_by_arc": dict(quests_by_arc),
        "title": "Quest Builder",
    }
    return render(request, "admin/quest_builder/list.html", context)


def quest_builder_canvas(request, quest_id):
    canvas_data = get_canvas_data(quest_id)
    context = {
        **canvas_data,
        "title": f"Quest Builder - {canvas_data['quest'].title}",
    }
    return render(request, "admin/quest_builder/canvas.html", context)
