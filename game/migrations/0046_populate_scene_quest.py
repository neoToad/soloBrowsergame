from django.db import migrations


def populate_scene_quest(apps, schema_editor):
    db = schema_editor.connection.alias
    Quest = apps.get_model('game', 'Quest')
    Scene = apps.get_model('game', 'Scene')
    for quest in Quest.objects.using(db).all():
        scene_pks = list(quest.scenes.using(db).values_list('pk', flat=True))
        if scene_pks:
            Scene.objects.using(db).filter(pk__in=scene_pks).update(quest=quest)


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0045_scene_quest_fk'),
    ]

    operations = [
        migrations.RunPython(populate_scene_quest, migrations.RunPython.noop),
    ]