from django.db import migrations


def _clone_group(group, RequirementGroup):
    clone = RequirementGroup.objects.create(
        label=group.label,
        logic=group.logic,
    )
    clone.requirements.set(group.requirements.all())
    return clone


def backfill_scopes(apps, schema_editor):
    RequirementGroup = apps.get_model("game", "RequirementGroup")
    Quest = apps.get_model("game", "Quest")
    Choice = apps.get_model("game", "Choice")

    assigned = {}
    used_group_keys: dict[tuple[str, str], set[str]] = {}

    def unique_group_key(scope_type: str, scope_key: str, base_key: str) -> str:
        owner = (scope_type, scope_key)
        bucket = used_group_keys.setdefault(owner, set())
        if base_key not in bucket:
            bucket.add(base_key)
            return base_key
        suffix = 2
        while True:
            candidate = f"{base_key}-{suffix}"
            if candidate not in bucket:
                bucket.add(candidate)
                return candidate
            suffix += 1

    for quest in Quest.objects.all():
        desired_scope_type = "quest"
        desired_scope_key = quest.key
        for group in list(quest.requirements.all()):
            desired_group_key = unique_group_key(
                desired_scope_type,
                desired_scope_key,
                group.group_key or group.label,
            )
            desired_scope = (desired_scope_type, desired_scope_key, desired_group_key)
            existing_scope = (group.scope_type, group.scope_key, group.group_key)

            if existing_scope == desired_scope:
                assigned[group.pk] = desired_scope
                continue

            if group.pk in assigned and assigned[group.pk] != desired_scope:
                clone = _clone_group(group, RequirementGroup)
                clone.scope_type = desired_scope_type
                clone.scope_key = desired_scope_key
                clone.group_key = desired_group_key
                clone.save(update_fields=["scope_type", "scope_key", "group_key"])
                quest.requirements.remove(group)
                quest.requirements.add(clone)
                assigned[clone.pk] = desired_scope
                continue

            group.scope_type = desired_scope_type
            group.scope_key = desired_scope_key
            group.group_key = desired_group_key
            group.save(update_fields=["scope_type", "scope_key", "group_key"])
            assigned[group.pk] = desired_scope

    for choice in Choice.objects.select_related("scene").all():
        scene = choice.scene
        desired_scope_type = "choice"
        desired_scope_key = f"{scene.key}:{choice.order}:{choice.label}"
        for group in list(choice.requirements.all()):
            desired_group_key = unique_group_key(
                desired_scope_type,
                desired_scope_key,
                group.group_key or group.label,
            )
            desired_scope = (desired_scope_type, desired_scope_key, desired_group_key)
            existing_scope = (group.scope_type, group.scope_key, group.group_key)

            if existing_scope == desired_scope:
                assigned[group.pk] = desired_scope
                continue

            if group.pk in assigned and assigned[group.pk] != desired_scope:
                clone = _clone_group(group, RequirementGroup)
                clone.scope_type = desired_scope_type
                clone.scope_key = desired_scope_key
                clone.group_key = desired_group_key
                clone.save(update_fields=["scope_type", "scope_key", "group_key"])
                choice.requirements.remove(group)
                choice.requirements.add(clone)
                assigned[clone.pk] = desired_scope
                continue

            group.scope_type = desired_scope_type
            group.scope_key = desired_scope_key
            group.group_key = desired_group_key
            group.save(update_fields=["scope_type", "scope_key", "group_key"])
            assigned[group.pk] = desired_scope


class Migration(migrations.Migration):
    dependencies = [
        ("game", "0049_requirementgroup_scope_identity"),
    ]

    operations = [
        migrations.RunPython(backfill_scopes, migrations.RunPython.noop),
    ]
