from django.core.management.base import BaseCommand, CommandError
from django.core import serializers
from game.models.world import Quest, Scene, Choice, SceneItem
from game.models.requirements import RequirementGroup, Requirement
from game.models.items import Item
from game.models.combat import Enemy, CombatEncounter

class Command(BaseCommand):
    help = 'Export a quest and all its related objects to JSON fixture format.'

    def add_arguments(self, parser):
        parser.add_argument('quest_key', type=str, help='The key of the quest to export.')
        parser.add_argument('--output', type=str, help='Optional output file path.')

    def handle(self, *args, **options):
        quest_key = options['quest_key']
        output_path = options['output']

        try:
            quest = Quest.objects.get(key=quest_key)
        except Quest.DoesNotExist:
            raise CommandError(f"Quest with key '{quest_key}' does not exist.")

        # Collecting all objects
        objects_to_export = []

        # 1. The Quest
        objects_to_export.append(quest)

        # 2. All Scenes belonging to it
        scenes = Scene.objects.filter(quest=quest)
        for scene in scenes:
            objects_to_export.append(scene)

        # 3. All Choices belonging to those scenes
        choices = Choice.objects.filter(scene__in=scenes)
        for choice in choices:
            objects_to_export.append(choice)

        # 4. All SceneItems belonging to those scenes
        scene_items = SceneItem.objects.filter(scene__in=scenes)
        for si in scene_items:
            objects_to_export.append(si)

        # 5. RequirementGroups and Requirements referenced by Quest, Scene, Choice
        req_groups = set()
        req_groups.update(quest.requirements.all())
        for scene in scenes:
            req_groups.update(scene.requirements.all())
        for choice in choices:
            req_groups.update(choice.requirements.all())

        requirements = set()
        for group in req_groups:
            objects_to_export.append(group)
            requirements.update(group.requirements.all())

        for req in requirements:
            objects_to_export.append(req)

        # 6. Items referenced by SceneItems, Choice.consume_item, and Requirements
        items = set()
        for si in scene_items:
            items.add(si.item)
        for choice in choices:
            if choice.consume_item:
                items.add(choice.consume_item)
        for req in requirements:
            if req.required_item:
                items.add(req.required_item)

        for item in items:
            objects_to_export.append(item)

        # 7. Enemies and CombatEncounters on those scenes
        encounters = CombatEncounter.objects.filter(scene__in=scenes)
        enemies = set()
        for encounter in encounters:
            objects_to_export.append(encounter)
            enemies.add(encounter.enemy)

        for enemy in enemies:
            objects_to_export.append(enemy)

        # Serialize
        try:
            data = serializers.serialize(
                'json',
                objects_to_export,
                indent=2,
                use_natural_foreign_keys=True,
                use_natural_primary_keys=True
            )
        except Exception as e:
            raise CommandError(f"Serialization failed: {e}")

        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(data)
            self.stdout.write(self.style.SUCCESS(f"Quest '{quest_key}' exported to {output_path}"))
        else:
            self.stdout.write(data)
