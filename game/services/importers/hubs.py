from __future__ import annotations

from game.models.items import Item
from game.models.property import Territory
from game.models.world import Choice, Scene

from .refs import get_by_key_or_warn
from .requirements import RequirementScope, import_requirement_groups
from .shared import (
    import_choices_for_scene,
    import_scene_contacts,
    import_scene_gang_standings,
    import_scene_items,
)
from .types import ImportResult


def import_hubs_data(data: dict) -> ImportResult:
    result = ImportResult()
    scene_map: dict[str, Scene] = {}
    choices_by_scene: dict[str, dict[tuple[str, int], Choice]] = {}

    for hdata in data.get("hubs") or []:
        roll = hdata.get("roll", {}) or {}
        arrival = hdata.get("arrival", {}) or {}
        scene, created = Scene.objects.update_or_create(
            key=hdata["key"],
            defaults={
                "scene_type": hdata["scene_type"],
                "title": hdata["title"],
                "body": hdata["body"],
                "order": hdata.get("order", 0),
                "requires_roll": roll.get("requires_roll", False),
                "roll_stat": roll.get("roll_stat") or "",
                "roll_difficulty": roll.get("roll_difficulty") or 10,
                "ending_type": "",
                "cash_change": arrival.get("cash_change", 0),
                "rep_change": arrival.get("rep_change", 0),
                "heat_change": arrival.get("heat_change", 0),
                "consume_item": get_by_key_or_warn(Item, arrival.get("consume_item"), result),
                "receive_property": None,
                "lose_property": None,
                "receive_territory": None,
                "lose_territory": None,
                "discover_territory": get_by_key_or_warn(Territory, arrival.get("discover_territory"), result),
            },
        )
        scene_map[scene.key] = scene
        if created:
            result.record_created("hubs")
        else:
            result.record_updated("hubs")

    for hdata in data.get("hubs") or []:
        scene_obj = scene_map[hdata["key"]]
        choices_by_scene[scene_obj.key] = import_choices_for_scene(hdata, scene_obj, scene_map, result)
        for choice_data in (hdata.get("choices") or []):
            choice = choices_by_scene[scene_obj.key][(choice_data["label"], choice_data.get("order", 0))]
            choice_scope = RequirementScope(
                scope_type="choice",
                scope_key=f"{scene_obj.key}:{choice.order}:{choice.label}",
            )
            groups = import_requirement_groups(choice_data.get("requirements") or [], choice_scope, result)
            choice.requirements.set(groups)
        import_scene_items(hdata, scene_obj, result)
        import_scene_contacts(hdata, scene_obj, result)
        import_scene_gang_standings(hdata, scene_obj, result)

    return result
