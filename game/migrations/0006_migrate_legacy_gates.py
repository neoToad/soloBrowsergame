from django.db import migrations

def migrate_legacy_gates(apps, schema_editor):
    Choice = apps.get_model('game', 'Choice')
    Quest = apps.get_model('game', 'Quest')
    Requirement = apps.get_model('game', 'Requirement')
    RequirementGroup = apps.get_model('game', 'RequirementGroup')

    # 1. Migrate Choice legacy gates
    for choice in Choice.objects.exclude(required_stat='').exclude(required_stat__isnull=True):
        req = Requirement.objects.create(
            condition_type='stat_gte',
            stat_name=choice.required_stat,
            stat_value=choice.required_minimum
        )
        group = RequirementGroup.objects.create(
            label=f"{choice.label} stat gate",
            logic='all'
        )
        group.requirements.add(req)
        choice.requirements.add(group)

    # 2. Migrate Quest legacy stat gates
    for quest in Quest.objects.exclude(required_stat='').exclude(required_stat__isnull=True):
        req = Requirement.objects.create(
            condition_type='stat_gte',
            stat_name=quest.required_stat,
            stat_value=quest.required_minimum
        )
        group = RequirementGroup.objects.create(
            label=f"{quest.title} stat gate",
            logic='all'
        )
        group.requirements.add(req)
        quest.requirements.add(group)

    # 3. Migrate Quest legacy quest prerequisites
    for quest in Quest.objects.filter(required_quest__isnull=False):
        req = Requirement.objects.create(
            condition_type='quest_completed',
            required_quest=quest.required_quest
        )
        group = RequirementGroup.objects.create(
            label=f"{quest.title} prerequisite",
            logic='all'
        )
        group.requirements.add(req)
        quest.requirements.add(group)

class Migration(migrations.Migration):

    dependencies = [
        ('game', '0005_add_quest_requirements_field'),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_gates),
    ]
