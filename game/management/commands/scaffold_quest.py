from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from game.models.world import Quest, Scene, Choice

class Command(BaseCommand):
    help = 'Scaffolds a new quest with an entrance and two ending scenes (victory/defeat).'

    def add_arguments(self, parser):
        parser.add_argument('quest_key', type=str, help='The unique key for the quest.')
        parser.add_argument('quest_title', type=str, help='The human-readable title for the quest.')

    def handle(self, *args, **options):
        quest_key = options['quest_key']
        quest_title = options['quest_title']

        if Quest.objects.filter(key=quest_key).exists():
            raise CommandError(f"Error: A Quest with key '{quest_key}' already exists.")

        try:
            with transaction.atomic():
                # 1. Create Quest
                quest = Quest.objects.create(
                    key=quest_key,
                    title=quest_title,
                    is_unlocked=True,
                    is_repeatable=False,
                    arc=None
                )

                # 2. Create three Scenes
                entrance_scene = Scene.objects.create(
                    quest=quest,
                    key=f"{quest_key}__entrance",
                    title="Entrance",
                    scene_type="normal",
                    order=1
                )

                victory_scene = Scene.objects.create(
                    quest=quest,
                    key=f"{quest_key}__victory",
                    title="Victory",
                    scene_type="ending",
                    ending_type="victory",
                    order=2
                )

                defeat_scene = Scene.objects.create(
                    quest=quest,
                    key=f"{quest_key}__defeat",
                    title="Defeat",
                    scene_type="ending",
                    ending_type="defeat",
                    order=3
                )

                # 3. Create Choices on entrance pointing to victory and defeat
                Choice.objects.create(
                    scene=entrance_scene,
                    label="→ Victory",
                    target_scene=victory_scene,
                    order=1
                )

                Choice.objects.create(
                    scene=entrance_scene,
                    label="→ Defeat",
                    target_scene=defeat_scene,
                    order=2
                )

                # 4. Set entrance scene on quest
                quest.entrance_scene = entrance_scene
                quest.save()

                # 5. Print created objects
                self.stdout.write(self.style.SUCCESS(f"Successfully created Quest '{quest_title}' ({quest.pk})"))
                self.stdout.write(f"  Quest:   {quest.key} (pk={quest.pk})")
                self.stdout.write(f"  Scene:   {entrance_scene.key} (pk={entrance_scene.pk})")
                self.stdout.write(f"  Scene:   {victory_scene.key} (pk={victory_scene.pk})")
                self.stdout.write(f"  Scene:   {defeat_scene.key} (pk={defeat_scene.pk})")

        except Exception as e:
            raise CommandError(f"An error occurred during quest scaffolding: {e}")
