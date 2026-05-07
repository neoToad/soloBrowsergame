"""Shared quest-builder view helpers used by scene and choice endpoints."""

from django.urls import reverse

from game.constants import STAT_DISPLAY_NAMES
from game.models import Item, Quest, Requirement, Scene


def choice_context(*, quest, quest_id, choice=None, source_scene_id=None, routing_type="direct"):
    scenes = list(
        quest.scenes
        .only("id", "key", "title", "scene_type")
        .order_by("order")
    )
    quest_scene_ids = {s.id for s in scenes}
    hub_scenes = list(
        Scene.objects.filter(scene_type="hub")
        .exclude(pk__in=quest_scene_ids)
        .only("id", "key", "title")
        .order_by("title")
    )
    source_scene = (
        Scene.objects.filter(pk=source_scene_id).only("id", "scene_type").first()
        if source_scene_id else None
    )
    requirement_groups = (
        list(choice.requirements.prefetch_related("requirements").all())
        if choice else []
    )
    req_save_url = (
        reverse("admin:quest_builder_choice_requirements_save", args=[quest_id, choice.id])
        if choice else ""
    )
    return {
        "quest_id": quest_id,
        "source_scene_id": source_scene_id,
        "source_scene": source_scene,
        "choice": choice,
        "scenes": scenes,
        "hub_scenes": hub_scenes,
        "routing_type": routing_type,
        "requirement_groups": requirement_groups,
        "req_save_url": req_save_url,
        "all_quests": list(Quest.objects.order_by("title")),
        "all_items": list(Item.objects.order_by("name")),
        "stat_choices": [(field, label) for field, label in STAT_DISPLAY_NAMES.items()],
        "requirement_types": Requirement.CONDITION_TYPES,
    }
