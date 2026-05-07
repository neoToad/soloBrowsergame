from __future__ import annotations

from game.models.combat import Enemy
from game.models.world import Contact

from .types import ImportResult


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
