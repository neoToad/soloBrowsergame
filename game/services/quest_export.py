from __future__ import annotations

from pathlib import Path

import yaml
from django.core.management import CommandError

from game.models.combat import CombatEncounter
from game.models.world import Quest


def _requirement_to_dict(requirement):
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


def _requirement_groups_to_list(groups_qs):
    groups = []
    for group in groups_qs.order_by("group_key", "id"):
        row = {
            "label": group.label,
            "logic": group.logic,
            "conditions": [
                _requirement_to_dict(req) for req in group.requirements.all().order_by("id")
            ],
        }
        if group.group_key:
            row["group_key"] = group.group_key
        groups.append(row)
    return groups


def _choice_to_dict(choice):
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


def _scene_to_dict(scene, encounter_by_scene_id):
    combat_payload = None
    encounter = encounter_by_scene_id.get(scene.id)
    if encounter:
        combat_payload = {
            "enemy": encounter.enemy.key,
            "victory_scene": encounter.victory_scene.key if encounter.victory_scene else None,
            "defeat_scene": encounter.defeat_scene.key if encounter.defeat_scene else None,
            "victory_arrival_flavor": encounter.victory_arrival_flavor or None,
            "defeat_arrival_flavor": encounter.defeat_arrival_flavor or None,
        }

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
                {
                    "gang": row.gang.key,
                    "standing_change": row.standing_change,
                }
                for row in scene.scene_gang_standings.all().order_by("id")
            ],
        },
        "scene_items": [
            {
                "item": si.item.key,
                "quantity": si.quantity,
                "award_once": si.award_once,
            }
            for si in scene.scene_items.all().order_by("id")
        ],
        "scene_contacts": [
            {
                "contact": sc.contact.key,
                "action": sc.action,
                "award_once": sc.award_once,
            }
            for sc in scene.scene_contacts.all().order_by("id")
        ],
        "choices": [_choice_to_dict(choice) for choice in scene.choices.all().order_by("order", "id")],
        "combat_encounter": combat_payload,
    }


def build_quest_export_payload(quest_key: str) -> dict:
    quest = (
        Quest.objects.select_related("arc", "entrance_scene")
        .prefetch_related(
            "hub_scenes",
            "requirements__requirements",
            "scenes__scene_items__item",
            "scenes__scene_contacts__contact",
            "scenes__choices__target_scene",
            "scenes__choices__success_scene",
            "scenes__choices__failure_scene",
            "scenes__choices__requirements__requirements",
            "scenes__scene_gang_standings__gang",
        )
        .filter(key=quest_key)
        .first()
    )
    if quest is None:
        raise CommandError(f"Quest not found: {quest_key}")
    if quest.entrance_scene is None:
        raise CommandError(f"Quest '{quest_key}' has no entrance_scene.")

    encounters = CombatEncounter.objects.select_related(
        "enemy", "victory_scene", "defeat_scene", "scene"
    ).filter(scene__quest=quest)
    encounter_by_scene_id = {enc.scene_id: enc for enc in encounters}

    scenes = list(quest.scenes.all().order_by("order", "key"))
    return {
        "quest": {
            "key": quest.key,
            "title": quest.title,
            "description": quest.description,
            "arc": quest.arc.key if quest.arc else None,
            "arc_order": quest.arc_order or 0,
            "is_repeatable": quest.is_repeatable,
            "hub_scenes": [scene.key for scene in quest.hub_scenes.all().order_by("key")],
            "entrance_scene": quest.entrance_scene.key,
            "requirements": _requirement_groups_to_list(quest.requirements.all()),
        },
        "scenes": [_scene_to_dict(scene, encounter_by_scene_id) for scene in scenes],
    }


def render_quest_yaml(payload: dict) -> str:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


def default_quest_export_path(payload: dict) -> Path:
    quest_block = payload["quest"]
    arc_key = quest_block.get("arc") or "misc"
    return Path("yaml_files") / "quests" / arc_key / f"{quest_block['key']}.yaml"
