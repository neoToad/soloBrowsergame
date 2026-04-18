from django.db import migrations, models


def populate_quest_scenes(apps, schema_editor):
    # Use raw SQL: during this migration, Quest.scenes M2M and Scene.quest FK coexist,
    # causing an ORM descriptor conflict. Raw SQL bypasses this.
    schema_editor.execute(
        "INSERT INTO game_quest_scenes (quest_id, scene_id) "
        "SELECT quest_id, id FROM game_scene WHERE quest_id IS NOT NULL"
    )


def populate_quest_entry_choices(apps, schema_editor):
    schema_editor.execute(
        "INSERT INTO game_quest_entry_choices (quest_id, choice_id) "
        "SELECT quest_id, id FROM game_choice WHERE quest_id IS NOT NULL"
    )


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0024_move_consume_item_to_scene'),
    ]

    operations = [
        # 1. Add Quest.scenes M2M (through table: game_quest_scenes)
        migrations.AddField(
            model_name='quest',
            name='scenes',
            field=models.ManyToManyField(
                blank=True,
                help_text='Scenes that belong to this quest.',
                related_name='quests',
                to='game.scene',
            ),
        ),
        # 2. Populate Quest.scenes from Scene.quest FK
        migrations.RunPython(populate_quest_scenes, migrations.RunPython.noop),
        # 3. Remove Scene.quest FK
        migrations.RemoveField(
            model_name='scene',
            name='quest',
        ),
        # 4. Add Quest.entry_choices M2M (through table: game_quest_entry_choices)
        migrations.AddField(
            model_name='quest',
            name='entry_choices',
            field=models.ManyToManyField(
                blank=True,
                help_text='Choices that start this quest (hidden after completion unless repeatable).',
                related_name='started_quests',
                to='game.choice',
            ),
        ),
        # 5. Populate Quest.entry_choices from Choice.quest FK
        migrations.RunPython(populate_quest_entry_choices, migrations.RunPython.noop),
        # 6. Remove Choice.quest FK
        migrations.RemoveField(
            model_name='choice',
            name='quest',
        ),
    ]
