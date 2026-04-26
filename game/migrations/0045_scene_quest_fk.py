import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add Scene.quest FK (nullable). Uses related_name='+' to avoid clashing
    with the Quest.scenes M2M that still exists at this migration state.
    Migration 0047 removes the M2M and sets the final related_name='scenes'.
    """

    dependencies = [
        ('game', '0044_unique_together_to_unique_constraint'),
    ]

    operations = [
        migrations.AddField(
            model_name='scene',
            name='quest',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='game.quest',
            ),
        ),
    ]