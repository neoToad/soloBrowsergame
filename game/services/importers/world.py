from __future__ import annotations

from django.utils.text import slugify

from game.models.property import Property, Territory
from game.models.world import Gang

from .types import ImportResult


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
                "description": pdata.get("description", ""),
                "property_type": property_type,
                "cash_per_turn": pdata.get("cash_per_turn", 0),
                "heat_per_turn": pdata.get("heat_per_turn", 0),
                "rep_per_turn": pdata.get("rep_per_turn", 0),
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
            },
        )
        if created:
            result.record_created("territories")
        else:
            result.record_updated("territories")
    return result
