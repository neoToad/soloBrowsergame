from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.management import CommandError
from django.utils.text import slugify

from game.models.combat import CombatEncounter, Enemy
from game.models.items import Item
from game.models.property import Property, Territory
from game.models.world import Arc, Choice, Contact, Gang, Quest, Scene, SceneContact, SceneItem

from .refs import get_by_key_or_warn, resolve_scene
from .requirements import RequirementScope, import_requirement_groups
from .types import ImportResult


def import_items_data(data: dict) -> ImportResult:
    result = ImportResult()
    for idata in data.get("items") or []:
        key = idata["key"]
        item = Item.objects.filter(key=key).first()
        created = item is None
        if item is None:
            item = Item(key=key)
        item.name = idata["name"]
        item.description = idata["description"]
        item.is_consumable = idata.get("is_consumable", False)
        item.effect_type = idata.get("effect_type") or ""
        item.effect_stat = idata.get("effect_stat") or ""
        item.effect_value = idata.get("effect_value", 0)
        item.passive_stat = idata.get("passive_stat") or ""
        item.passive_value = idata.get("passive_value", 0)
        try:
            item.full_clean()
        except ValidationError as exc:
            raise CommandError(f"Invalid item '{key}': {exc.message_dict}") from exc
        item.save()
        if created:
            result.record_created("items")
        else:
            result.record_updated("items")
    return result


def import_enemies_and_contacts_data(data: dict) -> ImportResult:
    result = ImportResult()
    for edata in data.get("enemies") or []:
        _, created = Enemy.objects.update_or_create(
            key=edata["key"],
            defaults={
                "name": edata["name"],
                "description": edata["description"],
                "max_hp": edata.get("max_hp", 10),
                "attack_modifier": edata.get("attack_modifier", 0),
                "defense": edata.get("defense", 8),
                "damage_min": edata.get("damage_min", 1),
                "damage_max": edata.get("damage_max", 4),
            },
        )
        if created:
            result.record_created("enemies")
        else:
            result.record_updated("enemies")

    for cdata in data.get("contacts") or []:
        _, created = Contact.objects.update_or_create(
            key=cdata["key"],
            defaults={
                "name": cdata["name"],
                "description": cdata.get("description", ""),
            },
        )
        if created:
            result.record_created("contacts")
        else:
            result.record_updated("contacts")
    return result


def import_world_data(data: dict) -> ImportResult:
    result = ImportResult()
    for gdata in data.get("gangs") or []:
        _, created = Gang.objects.update_or_create(
            key=gdata["key"],
            defaults={
                "name": gdata["name"],
                "description": gdata.get("description", ""),
            },
        )
        if created:
            result.record_created("gangs")
        else:
            result.record_updated("gangs")

    for pdata in data.get("properties") or []:
        property_key = pdata.get("key") or slugify(pdata["name"])
        if not pdata.get("key"):
            result.warn(f"Property '{pdata['name']}' missing key; using generated key '{property_key}'")
        property_type = pdata.get("property_type")
        allowed_property_types = {choice[0] for choice in Property.PROPERTY_TYPES}
        if property_type not in allowed_property_types:
            result.warn(
                f"Property '{property_key}' has unsupported property_type '{property_type}'; "
                "skipping."
            )
            continue
        _, created = Property.objects.update_or_create(
            key=property_key,
            defaults={
                "name": pdata["name"],
                "property_type": property_type,
                "cash_per_turn": pdata.get("cash_per_turn", 0),
                "heat_per_turn": pdata.get("heat_per_turn", 0),
                "rep_per_turn": pdata.get("rep_per_turn", 0),
                "is_contestable": pdata.get("is_contestable", False),
                "resolution_scene": get_by_key_or_warn(Scene, pdata.get("resolution_scene"), result),
            },
        )
        if created:
            result.record_created("properties")
        else:
            result.record_updated("properties")

    for tdata in data.get("territories") or []:
        territory_key = tdata.get("key") or slugify(tdata["name"])
        if not tdata.get("key"):
            result.warn(f"Territory '{tdata['name']}' missing key; using generated key '{territory_key}'")
        _, created = Territory.objects.update_or_create(
            key=territory_key,
            defaults={
                "name": tdata["name"],
                "description": tdata.get("description", ""),
                "cash_per_turn": tdata.get("cash_per_turn", 0),
                "heat_per_turn": tdata.get("heat_per_turn", 0),
                "rep_per_turn": tdata.get("rep_per_turn", 0),
                "is_contestable": tdata.get("is_contestable", False),
                "resolution_scene": get_by_key_or_warn(Scene, tdata.get("resolution_scene"), result),
            },
        )
        if created:
            result.record_created("territories")
        else:
            result.record_updated("territories")
    return result


def _import_choices_for_scene(scene_data: dict, scene_obj: Scene, scene_map: dict[str, Scene], result: ImportResult) -> dict[tuple[str, int], Choice]:
    choices: dict[tuple[str, int], Choice] = {}
    for choice_data in (scene_data.get("choices") or []):
        choice = Choice.objects.filter(
            scene=scene_obj,
            label=choice_data["label"],
            order=choice_data.get("order", 0),
        ).first()
        created = choice is None
        if created:
            choice = Choice(
                scene=scene_obj,
                label=choice_data["label"],
                order=choice_data.get("order", 0),
            )
        choice.arrival_flavor = choice_data.get("arrival_flavor") or ""
        choice.failure_arrival_flavor = choice_data.get("failure_arrival_flavor") or ""
        choice.set_flag_name = choice_data.get("set_flag_name") or ""
        choice.clear_flag_name = choice_data.get("clear_flag_name") or ""
        choice.target_scene = resolve_scene(choice_data.get("target_scene"), scene_map, result)
        choice.success_scene = resolve_scene(choice_data.get("success_scene"), scene_map, result)
        choice.failure_scene = resolve_scene(choice_data.get("failure_scene"), scene_map, result)
        try:
            choice.full_clean()
        except ValidationError as exc:
            raise CommandError(
                f"Invalid choice '{scene_obj.key}:{choice.label}#{choice.order}': {exc.message_dict}"
            ) from exc
        choice.save()
        choice.requirements.clear()
        key = (choice_data["label"], choice_data.get("order", 0))
        choices[key] = choice
        if created:
            result.record_created("choices")
        else:
            result.record_updated("choices")
    return choices


def _import_scene_items(scene_data: dict, scene_obj: Scene, result: ImportResult) -> None:
    deleted, _ = SceneItem.objects.filter(scene=scene_obj).delete()
    if deleted:
        result.record_deleted("scene_items", deleted)
    for entry in (scene_data.get("scene_items") or scene_data.get("items") or []):
        SceneItem.objects.create(
            scene=scene_obj,
            item=get_by_key_or_warn(Item, entry["item"], result),
            quantity=entry.get("quantity", 1),
            award_once=entry.get("award_once", True),
        )
        result.record_created("scene_items")


def _import_scene_contacts(scene_data: dict, scene_obj: Scene, result: ImportResult) -> None:
    deleted, _ = SceneContact.objects.filter(scene=scene_obj).delete()
    if deleted:
        result.record_deleted("scene_contacts", deleted)
    for entry in (scene_data.get("scene_contacts") or scene_data.get("contacts") or []):
        SceneContact.objects.create(
            scene=scene_obj,
            contact=get_by_key_or_warn(Contact, entry["contact"], result),
            action=entry.get("action", "gain"),
            award_once=entry.get("award_once", True),
        )
        result.record_created("scene_contacts")


def _import_combat_encounter(scene_data: dict, scene_obj: Scene, scene_map: dict[str, Scene], result: ImportResult) -> None:
    if scene_data.get("scene_type") != "combat":
        return
    combat = scene_data.get("combat_encounter") or scene_data.get("combat") or {}
    enemy = get_by_key_or_warn(Enemy, combat.get("enemy"), result)
    if enemy is None:
        result.warn(f"Skipping CombatEncounter for '{scene_obj.key}'; enemy not found")
        return
    _, created = CombatEncounter.objects.update_or_create(
        scene=scene_obj,
        defaults={
            "enemy": enemy,
            "victory_scene": resolve_scene(combat.get("victory_scene"), scene_map, result),
            "defeat_scene": resolve_scene(combat.get("defeat_scene"), scene_map, result),
            "victory_arrival_flavor": combat.get("victory_arrival_flavor") or "",
            "defeat_arrival_flavor": combat.get("defeat_arrival_flavor") or "",
        },
    )
    if created:
        result.record_created("combat_encounters")
    else:
        result.record_updated("combat_encounters")


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
            },
        )
        scene_map[scene.key] = scene
        if created:
            result.record_created("hubs")
        else:
            result.record_updated("hubs")

    for hdata in data.get("hubs") or []:
        scene_obj = scene_map[hdata["key"]]
        choices_by_scene[scene_obj.key] = _import_choices_for_scene(hdata, scene_obj, scene_map, result)
        for choice_data in (hdata.get("choices") or []):
            choice = choices_by_scene[scene_obj.key][(choice_data["label"], choice_data.get("order", 0))]
            choice_scope = RequirementScope(
                scope_type="choice",
                scope_key=f"{scene_obj.key}:{choice.order}:{choice.label}",
            )
            groups = import_requirement_groups(choice_data.get("requirements") or [], choice_scope, result)
            choice.requirements.set(groups)
        _import_scene_items(hdata, scene_obj, result)
        _import_scene_contacts(hdata, scene_obj, result)

    return result


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
        choices_by_scene[scene_obj.key] = _import_choices_for_scene(sdata, scene_obj, scene_map, result)

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
        _import_scene_items(sdata, scene_obj, result)
        _import_scene_contacts(sdata, scene_obj, result)
        _import_combat_encounter(sdata, scene_obj, scene_map, result)

    Scene.objects.filter(quest=quest).exclude(key__in=scene_map.keys()).update(quest=None)
    hub_keys = qdata.get("hub_scenes") or []
    quest.hub_scenes.set(Scene.objects.filter(key__in=hub_keys))
    return result
