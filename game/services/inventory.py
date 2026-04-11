def get_player_inventory(session):
    """
    Returns a dict keyed by item_id: {item_id: PlayerInventory instance}.
    Used by Requirement.evaluate() and get_available_choices().
    """
    from ..models import PlayerInventory
    qs = PlayerInventory.objects.filter(session=session).select_related('item')
    return {pi.item_id: pi for pi in qs}


def award_scene_items(session, scene, inventory):
    """
    Awards all SceneItems attached to `scene` to the session.
    Respects award_once: skips items the session already holds when award_once=True.
    Updates `inventory` dict in-place so callers see fresh data.
    Returns a list of (item, quantity) tuples for every item actually awarded,
    so the caller can log them.
    """
    from ..models import PlayerInventory
    awarded = []
    for scene_item in scene.scene_items.select_related('item').all():
        item = scene_item.item
        if scene_item.award_once and item.id in inventory:
            continue
        pi, created = PlayerInventory.objects.get_or_create(
            session=session,
            item=item,
            defaults={'quantity': 0}
        )
        pi.quantity += scene_item.quantity
        pi.save()
        inventory[item.id] = pi          # keep caller's dict current
        awarded.append((item, scene_item.quantity))
    return awarded


def consume_item(session, item, inventory):
    """
    Removes one of `item` from the session's inventory.
    Deletes the PlayerInventory row when quantity reaches 0.
    Updates `inventory` dict in-place.
    No-ops silently if the item is not held.
    """
    pi = inventory.get(item.id)
    if not pi:
        return
    pi.quantity -= 1
    if pi.quantity <= 0:
        pi.delete()
        inventory.pop(item.id, None)
    else:
        pi.save()
        inventory[item.id] = pi
