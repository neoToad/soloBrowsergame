from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.management import CommandError

from game.models.combat import CombatEncounter, Enemy
from game.models.items import Item
from game.models.world import Choice, Contact, Gang, Scene, SceneContact, SceneGangStanding, SceneItem

from .refs import get_by_key_or_warn, resolve_scene
from .types import ImportResult


def import_choices_for_scene(
    scene_data: dict, scene_obj: Scene, scene_map: dict[str, Scene], result: ImportResult
) -> dict[tuple[str, int], Choice]:
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


def import_scene_items(scene_data: dict, scene_obj: Scene, result: ImportResult) -> None:
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


def import_scene_contacts(scene_data: dict, scene_obj: Scene, result: ImportResult) -> None:
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


def import_scene_gang_standings(scene_data: dict, scene_obj: Scene, result: ImportResult) -> None:
    deleted, _ = SceneGangStanding.objects.filter(scene=scene_obj).delete()
    if deleted:
        result.record_deleted("scene_gang_standings", deleted)
    arrival = scene_data.get("arrival") or {}
    for entry in (arrival.get("gang_standing_changes") or []):
        gang = get_by_key_or_warn(Gang, entry.get("gang"), result)
        if gang is None:
            continue
        SceneGangStanding.objects.create(
            scene=scene_obj,
            gang=gang,
            standing_change=entry.get("standing_change", 0),
        )
        result.record_created("scene_gang_standings")


def import_combat_encounter(
    scene_data: dict, scene_obj: Scene, scene_map: dict[str, Scene], result: ImportResult
) -> None:
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
