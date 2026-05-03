from __future__ import annotations

from pathlib import Path

import yaml

from game.models.combat import Enemy
from game.models.items import Item
from game.models.property import Property, Territory
from game.models.world import Contact, Gang, Scene


def render_yaml(payload: dict) -> str:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


def build_items_payload() -> dict:
    items = []
    for item in Item.objects.order_by("key"):
        items.append(
            {
                "key": item.key,
                "name": item.name,
                "description": item.description,
                "is_consumable": item.is_consumable,
                "effect_type": item.effect_type or "",
                "effect_stat": item.effect_stat or "",
                "effect_value": item.effect_value,
                "passive_stat": item.passive_stat or "",
                "passive_value": item.passive_value,
            }
        )
    return {"items": items}


def build_enemies_payload() -> dict:
    enemies = []
    for enemy in Enemy.objects.order_by("key"):
        enemies.append(
            {
                "key": enemy.key,
                "name": enemy.name,
                "description": enemy.description,
                "max_hp": enemy.max_hp,
                "attack_modifier": enemy.attack_modifier,
                "defense": enemy.defense,
                "damage_min": enemy.damage_min,
                "damage_max": enemy.damage_max,
            }
        )
    return {"enemies": enemies}


def build_contacts_payload() -> dict:
    contacts = []
    for contact in Contact.objects.order_by("key"):
        contacts.append(
            {
                "key": contact.key,
                "name": contact.name,
                "description": contact.description,
            }
        )
    return {"contacts": contacts}


def build_enemies_contacts_payload() -> dict:
    payload = build_enemies_payload()
    payload.update(build_contacts_payload())
    return payload


def build_gangs_payload() -> dict:
    gangs = []
    for gang in Gang.objects.order_by("key"):
        gangs.append(
            {
                "key": gang.key,
                "name": gang.name,
                "description": gang.description,
            }
        )
    return {"gangs": gangs}


def build_properties_payload() -> dict:
    properties = []
    for prop in Property.objects.select_related("resolution_scene").order_by("key"):
        properties.append(
            {
                "key": prop.key,
                "name": prop.name,
                "description": prop.description or "",
                "property_type": prop.property_type,
                "cash_per_turn": prop.cash_per_turn,
                "heat_per_turn": prop.heat_per_turn,
                "rep_per_turn": prop.rep_per_turn,
                "is_contestable": prop.is_contestable,
                "resolution_scene": prop.resolution_scene.key if prop.resolution_scene else None,
            }
        )
    return {"properties": properties}


def build_territories_payload() -> dict:
    territories = []
    for territory in Territory.objects.select_related("resolution_scene").order_by("key"):
        territories.append(
            {
                "key": territory.key,
                "name": territory.name,
                "description": territory.description or "",
                "cash_per_turn": territory.cash_per_turn,
                "heat_per_turn": territory.heat_per_turn,
                "rep_per_turn": territory.rep_per_turn,
                "is_contestable": territory.is_contestable,
                "resolution_scene": territory.resolution_scene.key if territory.resolution_scene else None,
            }
        )
    return {"territories": territories}


def build_world_payload() -> dict:
    payload = build_gangs_payload()
    payload.update(build_properties_payload())
    payload.update(build_territories_payload())
    return payload


def _requirement_to_dict(requirement) -> dict:
    return {
        "condition_type": requirement.condition_type,
        "flag_name": requirement.flag_name or None,
        "stat_name": requirement.stat_name or None,
        "stat_value": requirement.stat_value,
        "required_item": requirement.required_item.key if requirement.required_item else None,
        "required_quest": requirement.required_quest.key if requirement.required_quest else None,
        "required_contact": requirement.required_contact.key if requirement.required_contact else None,
        "required_ending_type": requirement.required_ending_type or None,
    }


def _requirement_groups_to_list(groups_qs) -> list[dict]:
    groups = []
    for group in groups_qs.order_by("group_key", "id"):
        row = {
            "label": group.label,
            "logic": group.logic,
            "conditions": [_requirement_to_dict(req) for req in group.requirements.all().order_by("id")],
        }
        if group.group_key:
            row["group_key"] = group.group_key
        groups.append(row)
    return groups


def _choice_to_dict(choice) -> dict:
    return {
        "label": choice.label,
        "order": choice.order,
        "target_scene": choice.target_scene.key if choice.target_scene else None,
        "success_scene": choice.success_scene.key if choice.success_scene else None,
        "failure_scene": choice.failure_scene.key if choice.failure_scene else None,
        "arrival_flavor": choice.arrival_flavor or None,
        "failure_arrival_flavor": choice.failure_arrival_flavor or None,
        "set_flag_name": choice.set_flag_name or None,
        "clear_flag_name": choice.clear_flag_name or None,
        "requirements": _requirement_groups_to_list(choice.requirements.all()),
    }


def _hub_scene_to_dict(scene) -> dict:
    return {
        "key": scene.key,
        "scene_type": scene.scene_type,
        "title": scene.title,
        "order": scene.order,
        "body": scene.body,
        "roll": {
            "requires_roll": scene.requires_roll,
            "roll_stat": scene.roll_stat or None,
            "roll_difficulty": scene.roll_difficulty if scene.requires_roll else None,
        },
        "ending": {
            "ending_type": scene.ending_type or None,
        },
        "arrival": {
            "cash_change": scene.cash_change,
            "rep_change": scene.rep_change,
            "heat_change": scene.heat_change,
            "consume_item": scene.consume_item.key if scene.consume_item else None,
            "receive_property": scene.receive_property.key if scene.receive_property else None,
            "lose_property": scene.lose_property.key if scene.lose_property else None,
            "receive_territory": scene.receive_territory.key if scene.receive_territory else None,
            "lose_territory": scene.lose_territory.key if scene.lose_territory else None,
            "discover_territory": scene.discover_territory.key if scene.discover_territory else None,
            "gang_standing_changes": [
                {"gang": row.gang.key, "standing_change": row.standing_change}
                for row in scene.scene_gang_standings.all().order_by("id")
            ],
        },
        "scene_items": [
            {"item": si.item.key, "quantity": si.quantity, "award_once": si.award_once}
            for si in scene.scene_items.all().order_by("id")
        ],
        "scene_contacts": [
            {"contact": sc.contact.key, "action": sc.action, "award_once": sc.award_once}
            for sc in scene.scene_contacts.all().order_by("id")
        ],
        "choices": [_choice_to_dict(choice) for choice in scene.choices.all().order_by("order", "id")],
    }


def build_hubs_payload() -> dict:
    hubs = []
    scenes = (
        Scene.objects.filter(scene_type="hub")
        .prefetch_related(
            "choices__target_scene",
            "choices__success_scene",
            "choices__failure_scene",
            "choices__requirements__requirements",
            "scene_items__item",
            "scene_contacts__contact",
            "scene_gang_standings__gang",
            "consume_item",
            "receive_property",
            "lose_property",
            "receive_territory",
            "lose_territory",
            "discover_territory",
        )
        .order_by("order", "key")
    )
    for scene in scenes:
        hubs.append(_hub_scene_to_dict(scene))
    return {"hubs": hubs}


def default_domain_export_paths(base_dir: str | Path, *, combined_world: bool, combined_enemies_contacts: bool) -> dict[str, Path]:
    base = Path(base_dir)
    paths = {
        "items": base / "items.yaml",
        "hubs": base / "hubs" / "hubs.yaml",
    }
    if combined_enemies_contacts:
        paths["enemies_contacts"] = base / "enemies_and_contacts.yaml"
    else:
        paths["enemies"] = base / "enemies.yaml"
        paths["contacts"] = base / "contacts.yaml"

    if combined_world:
        paths["world"] = base / "world.yaml"
    else:
        paths["gangs"] = base / "gangs.yaml"
        paths["properties"] = base / "properties.yaml"
        paths["territories"] = base / "territories.yaml"
    return paths
