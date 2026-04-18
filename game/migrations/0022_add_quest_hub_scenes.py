from django.db import migrations, models


def backfill_hub_scenes(apps, schema_editor):
    Quest = apps.get_model('game', 'Quest')
    Scene = apps.get_model('game', 'Scene')
    try:
        board = Scene.objects.get(key='hub__notice_board')
    except Scene.DoesNotExist:
        return
    for quest in Quest.objects.filter(is_unlocked=True):
        quest.hub_scenes.add(board)


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0021_remove_scene_requirements'),
    ]

    operations = [
        migrations.AddField(
            model_name='quest',
            name='hub_scenes',
            field=models.ManyToManyField(
                blank=True,
                help_text='Hub scenes whose notice board lists this quest.',
                limit_choices_to={'scene_type': 'hub'},
                related_name='posted_quests',
                to='game.scene',
            ),
        ),
        migrations.RunPython(backfill_hub_scenes, migrations.RunPython.noop),
    ]