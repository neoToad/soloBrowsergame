from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0012_property_playerproperty_rivalclaim'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='item',
            name='equip_slot',
        ),
    ]