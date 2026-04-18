from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0034_choice_failure_arrival_flavor_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='combatstate',
            name='pending_e_roll',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='combatstate',
            name='pending_e_total',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='combatstate',
            name='pending_e_hit',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='combatstate',
            name='pending_e_dmg',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]