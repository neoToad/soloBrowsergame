from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0023_drop_playerscenestate'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='choice',
            name='consume_item',
        ),
        migrations.AddField(
            model_name='scene',
            name='consume_item',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='consumed_by_scenes',
                to='game.item',
                help_text='If set, this item is removed from inventory when the player arrives at this scene.',
            ),
        ),
    ]
