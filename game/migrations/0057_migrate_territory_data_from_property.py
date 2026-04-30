from django.db import migrations


def migrate_territory_data(apps, schema_editor):
    Property = apps.get_model("game", "Property")
    Territory = apps.get_model("game", "Territory")
    PlayerProperty = apps.get_model("game", "PlayerProperty")
    PlayerTerritory = apps.get_model("game", "PlayerTerritory")
    Scene = apps.get_model("game", "Scene")

    territory_properties = Property.objects.filter(property_type="territory")

    for prop in territory_properties.iterator():
        Territory.objects.update_or_create(
            key=prop.key,
            defaults={
                "name": prop.name,
                "description": prop.description,
                "cash_per_turn": prop.cash_per_turn,
                "heat_per_turn": prop.heat_per_turn,
                "rep_per_turn": prop.rep_per_turn,
                "is_contestable": prop.is_contestable,
                "resolution_scene_id": prop.resolution_scene_id,
            },
        )

    territory_id_by_key = dict(Territory.objects.values_list("key", "id"))

    territory_player_properties = PlayerProperty.objects.filter(
        property__property_type="territory"
    ).select_related("property")
    for player_property in territory_player_properties.iterator():
        territory_id = territory_id_by_key.get(player_property.property.key)
        if not territory_id:
            continue
        PlayerTerritory.objects.update_or_create(
            session_id=player_property.session_id,
            territory_id=territory_id,
            defaults={"is_contested": player_property.is_contested},
        )

    receive_territory_props = Property.objects.filter(property_type="territory").only("id", "key")
    for prop in receive_territory_props.iterator():
        territory_id = territory_id_by_key.get(prop.key)
        if not territory_id:
            continue
        Scene.objects.filter(receive_property_id=prop.id).update(receive_territory_id=territory_id)
        Scene.objects.filter(lose_property_id=prop.id).update(lose_territory_id=territory_id)


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0056_scene_receive_territory_scene_lose_territory"),
    ]

    operations = [
        migrations.RunPython(migrate_territory_data, migrations.RunPython.noop),
    ]
