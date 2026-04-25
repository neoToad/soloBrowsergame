import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import yaml

from game.models.combat import CombatEncounter, Enemy
from game.models.items import Item
from game.models.jobs import ContactJobOffer, Job, JobApproach, JobBeatVariant
from game.models.property import Property
from game.models.requirements import Requirement, RequirementGroup
from game.models.world import Arc, Choice, Contact, Quest, Scene, SceneContact, SceneItem


def _compact_requirement(requirement, item_key_by_id, quest_key_by_id, contact_key_by_id):
    return {
        "id": requirement.id,
        "condition_type": requirement.condition_type,
        "flag_name": requirement.flag_name or None,
        "stat_name": requirement.stat_name or None,
        "stat_value": requirement.stat_value,
        "required_item": item_key_by_id.get(requirement.required_item_id),
        "required_quest": quest_key_by_id.get(requirement.required_quest_id),
        "required_contact": contact_key_by_id.get(requirement.required_contact_id),
        "required_ending_type": requirement.required_ending_type or None,
    }


def _compact_requirement_group(group, item_key_by_id, quest_key_by_id, contact_key_by_id):
    conditions = [
        _compact_requirement(req, item_key_by_id, quest_key_by_id, contact_key_by_id)
        for req in group.requirements.all().order_by("id")
    ]
    return {
        "id": group.id,
        "label": group.label,
        "logic": group.logic,
        "conditions": conditions,
    }


def build_game_state_payload(include_scene_body=False):
    items = list(Item.objects.all().order_by("key"))
    enemies = list(Enemy.objects.all().order_by("key"))
    contacts = list(Contact.objects.all().order_by("key"))
    properties = list(Property.objects.all().order_by("name", "id"))
    scenes = list(Scene.objects.all().order_by("order", "key"))
    quests = list(
        Quest.objects.select_related("arc", "entrance_scene")
        .prefetch_related("hub_scenes", "scenes")
        .order_by("arc_order", "key")
    )
    arcs = list(Arc.objects.prefetch_related("quests").order_by("order", "key"))
    jobs = list(Job.objects.prefetch_related("district_hubs").order_by("title", "key"))
    approaches = list(JobApproach.objects.select_related("job").order_by("job_id", "order", "id"))
    beat_variants = list(
        JobBeatVariant.objects.select_related("job", "approach")
        .order_by("job_id", "beat_number", "order", "id")
    )
    contact_offers = list(
        ContactJobOffer.objects.select_related("job", "contact", "scene")
        .order_by("contact_id", "order", "id")
    )
    choices = list(
        Choice.objects.select_related("scene", "target_scene", "success_scene", "failure_scene")
        .order_by("scene_id", "order", "id")
    )
    scene_items = list(SceneItem.objects.select_related("scene", "item").order_by("scene_id", "id"))
    scene_contacts = list(
        SceneContact.objects.select_related("scene", "contact").order_by("scene_id", "id")
    )
    combat_encounters = list(
        CombatEncounter.objects.select_related("scene", "enemy", "victory_scene", "defeat_scene")
        .order_by("scene_id")
    )

    item_key_by_id = {item.id: item.key for item in items}
    quest_key_by_id = {quest.id: quest.key for quest in quests}
    contact_key_by_id = {contact.id: contact.key for contact in contacts}
    scene_key_by_id = {scene.id: scene.key for scene in scenes}
    approach_key_by_id = {approach.id: approach.key for approach in approaches}

    requirement_groups = list(
        RequirementGroup.objects.prefetch_related("requirements").order_by("id")
    )
    requirements = list(Requirement.objects.all().order_by("id"))

    requirement_groups_payload = [
        _compact_requirement_group(group, item_key_by_id, quest_key_by_id, contact_key_by_id)
        for group in requirement_groups
    ]
    requirements_payload = [
        _compact_requirement(req, item_key_by_id, quest_key_by_id, contact_key_by_id)
        for req in requirements
    ]

    choices_by_scene_id = defaultdict(list)
    for choice in choices:
        choice_group_ids = list(choice.requirements.values_list("id", flat=True).order_by("id"))
        choices_by_scene_id[choice.scene_id].append(
            {
                "id": choice.id,
                "label": choice.label,
                "order": choice.order,
                "target_scene": scene_key_by_id.get(choice.target_scene_id),
                "success_scene": scene_key_by_id.get(choice.success_scene_id),
                "failure_scene": scene_key_by_id.get(choice.failure_scene_id),
                "set_flag_name": choice.set_flag_name or None,
                "clear_flag_name": choice.clear_flag_name or None,
                "requirement_group_ids": choice_group_ids,
            }
        )

    scene_items_by_scene_id = defaultdict(list)
    for scene_item in scene_items:
        scene_items_by_scene_id[scene_item.scene_id].append(
            {
                "item": item_key_by_id.get(scene_item.item_id),
                "quantity": scene_item.quantity,
                "award_once": scene_item.award_once,
            }
        )

    scene_contacts_by_scene_id = defaultdict(list)
    for scene_contact in scene_contacts:
        scene_contacts_by_scene_id[scene_contact.scene_id].append(
            {
                "contact": contact_key_by_id.get(scene_contact.contact_id),
                "action": scene_contact.action,
                "award_once": scene_contact.award_once,
            }
        )

    encounter_by_scene_id = {}
    for encounter in combat_encounters:
        encounter_by_scene_id[encounter.scene_id] = {
            "enemy": encounter.enemy.key,
            "victory_scene": scene_key_by_id.get(encounter.victory_scene_id),
            "defeat_scene": scene_key_by_id.get(encounter.defeat_scene_id),
        }

    scenes_payload = []
    for scene in scenes:
        row = {
            "key": scene.key,
            "scene_type": scene.scene_type,
            "title": scene.title,
            "order": scene.order,
            "requires_roll": scene.requires_roll,
            "roll_stat": scene.roll_stat or None,
            "roll_difficulty": scene.roll_difficulty,
            "ending_type": scene.ending_type or None,
            "consume_item": item_key_by_id.get(scene.consume_item_id),
            "receive_property_id": scene.receive_property_id,
            "lose_property_id": scene.lose_property_id,
            "cash_change": scene.cash_change,
            "rep_change": scene.rep_change,
            "heat_change": scene.heat_change,
            "choices": choices_by_scene_id.get(scene.id, []),
            "scene_items": scene_items_by_scene_id.get(scene.id, []),
            "scene_contacts": scene_contacts_by_scene_id.get(scene.id, []),
            "combat_encounter": encounter_by_scene_id.get(scene.id),
        }
        if include_scene_body:
            row["body"] = scene.body
        scenes_payload.append(row)

    quests_payload = []
    for quest in quests:
        quest_group_ids = list(quest.requirements.values_list("id", flat=True).order_by("id"))
        quest_scenes = list(quest.scenes.all().order_by("order", "key"))
        quests_payload.append(
            {
                "key": quest.key,
                "title": quest.title,
                "arc": quest.arc.key if quest.arc else None,
                "arc_order": quest.arc_order,
                "is_unlocked": quest.is_unlocked,
                "is_repeatable": quest.is_repeatable,
                "entrance_scene": scene_key_by_id.get(quest.entrance_scene_id),
                "hub_scenes": [scene.key for scene in quest.hub_scenes.all().order_by("key")],
                "requirement_group_ids": quest_group_ids,
                "scenes": [
                    {
                        "key": scene.key,
                        "scene_type": scene.scene_type,
                        "title": scene.title,
                        "order": scene.order,
                    }
                    for scene in quest_scenes
                ],
            }
        )

    arcs_payload = []
    for arc in arcs:
        arcs_payload.append(
            {
                "key": arc.key,
                "title": arc.title,
                "order": arc.order,
                "quests": [quest.key for quest in arc.quests.all().order_by("arc_order", "key")],
            }
        )

    approaches_by_job_id = defaultdict(list)
    for approach in approaches:
        approaches_by_job_id[approach.job_id].append(
            {
                "key": approach.key,
                "label": approach.label,
                "order": approach.order,
                "min_recon_tier": approach.min_recon_tier,
                "roll_stat": approach.roll_stat,
                "base_difficulty": approach.base_difficulty,
            }
        )

    beat_variants_by_job_id = defaultdict(list)
    for variant in beat_variants:
        beat_variants_by_job_id[variant.job_id].append(
            {
                "beat_number": variant.beat_number,
                "key": variant.key,
                "title": variant.title,
                "order": variant.order,
                "approach": approach_key_by_id.get(variant.approach_id),
                "requires_roll": variant.requires_roll,
                "roll_stat": variant.roll_stat or None,
                "base_difficulty": variant.base_difficulty,
                "allow_abort": variant.allow_abort,
            }
        )

    contact_offers_by_job_id = defaultdict(list)
    for offer in contact_offers:
        offer_group_ids = list(offer.unlock_requirements.values_list("id", flat=True).order_by("id"))
        contact_offers_by_job_id[offer.job_id].append(
            {
                "key": offer.key,
                "contact": contact_key_by_id.get(offer.contact_id),
                "scene": scene_key_by_id.get(offer.scene_id),
                "order": offer.order,
                "is_active": offer.is_active,
                "min_run_count": offer.min_run_count,
                "required_flag": offer.required_flag or None,
                "cooldown_turns": offer.cooldown_turns,
                "unlock_requirement_group_ids": offer_group_ids,
            }
        )

    jobs_payload = []
    for job in jobs:
        job_group_ids = list(job.unlock_requirements.values_list("id", flat=True).order_by("id"))
        jobs_payload.append(
            {
                "key": job.key,
                "title": job.title,
                "is_active": job.is_active,
                "base_cooldown_turns": job.base_cooldown_turns,
                "base_cash_min": job.base_cash_min,
                "base_cash_max": job.base_cash_max,
                "base_heat": job.base_heat,
                "base_rep": job.base_rep,
                "district_hubs": [scene.key for scene in job.district_hubs.all().order_by("key")],
                "unlock_requirement_group_ids": job_group_ids,
                "approaches": approaches_by_job_id.get(job.id, []),
                "beat_variants": beat_variants_by_job_id.get(job.id, []),
                "contact_offers": contact_offers_by_job_id.get(job.id, []),
            }
        )

    payload = {
        "meta": {
            "version": 1,
            "exported_at": datetime.now(UTC).isoformat(),
            "include_scene_body": include_scene_body,
        },
        "counts": {
            "items": len(items_payload := [
                {
                    "key": item.key,
                    "name": item.name,
                    "description": item.description,
                    "is_consumable": item.is_consumable,
                    "effect_type": item.effect_type or None,
                    "effect_stat": item.effect_stat or None,
                    "effect_value": item.effect_value,
                    "passive_stat": item.passive_stat or None,
                    "passive_value": item.passive_value,
                }
                for item in items
            ]),
            "enemies": len(enemies_payload := [
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
                for enemy in enemies
            ]),
            "contacts": len(contacts_payload := [
                {
                    "key": contact.key,
                    "name": contact.name,
                    "description": contact.description,
                }
                for contact in contacts
            ]),
            "properties": len(properties_payload := [
                {
                    "id": prop.id,
                    "name": prop.name,
                    "property_type": prop.property_type,
                    "cash_per_turn": prop.cash_per_turn,
                    "heat_per_turn": prop.heat_per_turn,
                    "rep_per_turn": prop.rep_per_turn,
                    "is_contestable": prop.is_contestable,
                    "resolution_scene": scene_key_by_id.get(prop.resolution_scene_id),
                }
                for prop in properties
            ]),
            "arcs": len(arcs_payload),
            "quests": len(quests_payload),
            "scenes": len(scenes_payload),
            "jobs": len(jobs_payload),
            "requirement_groups": len(requirement_groups_payload),
            "requirements": len(requirements_payload),
        },
        "items": items_payload,
        "enemies": enemies_payload,
        "contacts": contacts_payload,
        "properties": properties_payload,
        "arcs": arcs_payload,
        "quests": quests_payload,
        "scenes": scenes_payload,
        "jobs": jobs_payload,
        "requirement_groups": requirement_groups_payload,
        "requirements": requirements_payload,
    }
    return payload


def export_game_state(path, include_scene_body=False, output_format="json"):
    payload = build_game_state_payload(include_scene_body=include_scene_body)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        if output_format == "yaml":
            yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=False)
        else:
            json.dump(payload, f, indent=2, ensure_ascii=True)
    return payload
