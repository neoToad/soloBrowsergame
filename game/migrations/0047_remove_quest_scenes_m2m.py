import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Remove Quest.scenes M2M (data already copied to Scene.quest FK in 0046)
    and set the FK's related_name to 'scenes' so quest.scenes works again.
    """

    dependencies = [
        ('game', '0046_populate_scene_quest'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='quest',
            name='scenes',
        ),
        migrations.AlterField(
            model_name='scene',
            name='quest',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='scenes',
                to='game.quest',
            ),
        ),
    ]