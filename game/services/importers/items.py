from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.management import CommandError

from game.models.items import Item

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
