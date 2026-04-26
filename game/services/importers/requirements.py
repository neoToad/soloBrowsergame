from __future__ import annotations

from dataclasses import dataclass

from game.models.items import Item
from game.models.requirements import Requirement, RequirementGroup
from game.models.world import Contact, Quest

from .refs import get_by_key_or_warn
from .types import ImportResult


@dataclass(frozen=True)
class RequirementScope:
    scope_type: str
    scope_key: str


def import_requirement_groups(
    groups_data: list[dict] | None,
    scope: RequirementScope,
    result: ImportResult,
) -> list[RequirementGroup]:
    groups: list[RequirementGroup] = []
    for index, gdata in enumerate(groups_data or []):
        label = gdata["label"]
        group_key = gdata.get("group_key") or gdata.get("key") or label
        group, created = RequirementGroup.objects.update_or_create(
            scope_type=scope.scope_type,
            scope_key=scope.scope_key,
            group_key=group_key,
            defaults={
                "label": label,
                "logic": gdata.get("logic", "all"),
            },
        )
        if created:
            result.record_created("requirement_groups")
        else:
            result.record_updated("requirement_groups")

        # If duplicate keys exist in the same scope we still need deterministic ownership.
        if any(g.group_key == group_key for g in groups):
            fallback_key = f"{group_key}-{index}"
            group, created = RequirementGroup.objects.update_or_create(
                scope_type=scope.scope_type,
                scope_key=scope.scope_key,
                group_key=fallback_key,
                defaults={
                    "label": label,
                    "logic": gdata.get("logic", "all"),
                },
            )
            if created:
                result.record_created("requirement_groups")
            else:
                result.record_updated("requirement_groups")

        prior_requirement_ids = list(group.requirements.values_list("id", flat=True))
        group.requirements.clear()
        if prior_requirement_ids:
            Requirement.objects.filter(id__in=prior_requirement_ids, groups__isnull=True).delete()
        for cdata in (gdata.get("conditions") or []):
            req = Requirement.objects.create(
                condition_type=cdata["condition_type"],
                flag_name=cdata.get("flag_name") or "",
                stat_name=cdata.get("stat_name") or "",
                stat_value=cdata.get("stat_value") or 0,
                required_ending_type=cdata.get("required_ending_type") or "",
                required_item=get_by_key_or_warn(Item, cdata.get("required_item"), result),
                required_quest=get_by_key_or_warn(Quest, cdata.get("required_quest"), result),
                required_contact=get_by_key_or_warn(Contact, cdata.get("required_contact"), result),
            )
            group.requirements.add(req)
            result.record_created("requirements")
        groups.append(group)
    return groups
