from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.management import CommandError

from game.models.property import Property, Territory
from game.models.world import Arc, Choice, Quest, Scene
from game.models.items import Item

from .refs import get_by_key_or_warn
from .requirements import RequirementScope, import_requirement_groups
from .shared import (
    import_choices_for_scene,
    import_combat_encounter,
    import_scene_contacts,
    import_scene_gang_standings,
    import_scene_items,
)
from .types import ImportResult


def import_quest_data(data: dict) -> ImportResult:
    result = ImportResult()
    qdata = data["quest"]
    arc = get_by_key_or_warn(Arc, qdata.get("arc"), result)

    quest, created = Quest.objects.update_or_create(
        key=qdata["key"],
        defaults={
            "title": qdata["title"],
            "description": qdata["description"],
            "is_repeatable": qdata.get("is_repeatable", False),
            "arc_order": qdata.get("arc_order", 0),
            "arc": arc,
            "entrance_scene": None,
        },
    )
    if created:
        result.record_created("quests")
    else:
        result.record_updated("quests")

    scene_map: dict[str, Scene] = {}
    choices_by_scene: dict[str, dict[tuple[str, int], Choice]] = {}
    for sdata in data["scenes"]:
        roll = sdata.get("roll", {}) or {}
        ending = sdata.get("ending", {}) or {}
        arrival = sdata.get("arrival", {}) or {}
        ending_type = ending.get("ending_type") or sdata.get("ending_type") or ""
        if sdata.get("scene_type") == "ending" and not ending_type:
            raise CommandError(
                f"Scene '{sdata['key']}' is scene_type='ending' but has no ending.ending_type value."
            )
        scene = Scene.objects.filter(key=sdata["key"]).first()
        created = scene is None
        if scene is None:
            scene = Scene(key=sdata["key"])
        scene.quest = quest
        scene.scene_type = sdata["scene_type"]
        scene.title = sdata["title"]
        scene.body = sdata["body"]
        scene.order = sdata.get("order", 0)
        scene.requires_roll = roll.get("requires_roll", False)
        scene.roll_stat = roll.get("roll_stat") or ""
        scene.roll_difficulty = roll.get("roll_difficulty") or 10
        scene.ending_type = ending_type
        scene.cash_change = arrival.get("cash_change", sdata.get("cash_change", 0))
        scene.rep_change = arrival.get("rep_change", sdata.get("rep_change", 0))
        scene.heat_change = arrival.get("heat_change", sdata.get("heat_change", 0))
        scene.consume_item = get_by_key_or_warn(Item, arrival.get("consume_item"), result)
        scene.receive_property = get_by_key_or_warn(Property, arrival.get("receive_property"), result)
        scene.lose_property = get_by_key_or_warn(Property, arrival.get("lose_property"), result)
        scene.receive_territory = get_by_key_or_warn(Territory, arrival.get("receive_territory"), result)
        scene.lose_territory = get_by_key_or_warn(Territory, arrival.get("lose_territory"), result)
        scene.discover_territory = get_by_key_or_warn(Territory, arrival.get("discover_territory"), result)
        try:
            scene.clean()
        except ValidationError as exc:
            raise CommandError(f"Invalid scene '{sdata['key']}': {exc.message_dict}") from exc
        scene.save()
        scene_map[scene.key] = scene
        if created:
            result.record_created("scenes")
        else:
            result.record_updated("scenes")

    quest.entrance_scene = scene_map[qdata["entrance_scene"]]
    quest.save(update_fields=["entrance_scene"])

    for sdata in data["scenes"]:
        scene_obj = scene_map[sdata["key"]]
        choices_by_scene[scene_obj.key] = import_choices_for_scene(sdata, scene_obj, scene_map, result)

    for sdata in data["scenes"]:
        scene_obj = scene_map[sdata["key"]]
        for choice_data in (sdata.get("choices") or []):
            choice = choices_by_scene[scene_obj.key][(choice_data["label"], choice_data.get("order", 0))]
            choice_scope = RequirementScope(
                scope_type="choice",
                scope_key=f"{scene_obj.key}:{choice.order}:{choice.label}",
            )
            groups = import_requirement_groups(choice_data.get("requirements") or [], choice_scope, result)
            choice.requirements.set(groups)

    quest_scope = RequirementScope(scope_type="quest", scope_key=quest.key)
    quest_groups = import_requirement_groups(qdata.get("requirements") or [], quest_scope, result)
    quest.requirements.set(quest_groups)

    for sdata in data["scenes"]:
        scene_obj = scene_map[sdata["key"]]
        import_scene_items(sdata, scene_obj, result)
        import_scene_contacts(sdata, scene_obj, result)
        import_scene_gang_standings(sdata, scene_obj, result)
        import_combat_encounter(sdata, scene_obj, scene_map, result)

    Scene.objects.filter(quest=quest).exclude(key__in=scene_map.keys()).update(quest=None)
    hub_keys = qdata.get("hub_scenes") or []
    quest.hub_scenes.set(Scene.objects.filter(key__in=hub_keys))
    return result
