def process_turn_income(session):
    """
    Applies passive income from all un-contested PlayerProperties.
    Returns (log_strings: list[str], income_totals: dict).
    Heat is clamped at 0. stats.save() called once if any property paid out.
    """
    from ..models import PlayerProperty, PlayerTerritory
    stats = session.stats
    totals = {'cash': 0, 'heat': 0, 'rep': 0}
    logs = []
    properties = PlayerProperty.objects.filter(session=session).select_related('property')

    for pp in properties:
        prop = pp.property
        stats.cash += prop.cash_per_turn
        totals['cash'] += prop.cash_per_turn

        actual_heat_removed = min(prop.heat_per_turn, stats.heat)
        stats.heat = max(0, stats.heat - prop.heat_per_turn)
        totals['heat'] -= actual_heat_removed

        stats.rep += prop.rep_per_turn
        totals['rep'] += prop.rep_per_turn

        parts = []
        if prop.cash_per_turn:        parts.append(f"+${prop.cash_per_turn}")
        if actual_heat_removed:       parts.append(f"-{actual_heat_removed} heat")
        if prop.rep_per_turn:         parts.append(f"+{prop.rep_per_turn} rep")
        if parts:
            logs.append(f"{prop.name}: {', '.join(parts)}.")

    territories = PlayerTerritory.objects.filter(session=session).select_related("territory")
    for pt in territories:
        territory = pt.territory
        stats.cash += territory.cash_per_turn
        totals["cash"] += territory.cash_per_turn

        actual_heat_removed = min(territory.heat_per_turn, stats.heat)
        stats.heat = max(0, stats.heat - territory.heat_per_turn)
        totals["heat"] -= actual_heat_removed

        stats.rep += territory.rep_per_turn
        totals["rep"] += territory.rep_per_turn

        parts = []
        if territory.cash_per_turn:
            parts.append(f"+${territory.cash_per_turn}")
        if actual_heat_removed:
            parts.append(f"-{actual_heat_removed} heat")
        if territory.rep_per_turn:
            parts.append(f"+{territory.rep_per_turn} rep")
        if parts:
            logs.append(f"{territory.name}: {', '.join(parts)}.")

    if logs:
        stats.save()

    return logs, totals


def apply_property_rewards(session, scene):
    """
    Awards or removes properties based on scene arrival effects.
    Returns a list of log strings.
    """
    from ..models.property import PlayerDiscoveredTerritory, PlayerProperty, PlayerTerritory
    logs = []

    if scene.receive_property:
        if not PlayerProperty.objects.filter(session=session, property=scene.receive_property).exists():
            PlayerProperty.objects.create(session=session, property=scene.receive_property)
            logs.append(f"You have acquired: {scene.receive_property.name}")

    if scene.lose_property:
        pp = PlayerProperty.objects.filter(session=session, property=scene.lose_property).first()
        if pp:
            pp.delete()
            logs.append(f"You have lost: {scene.lose_property.name}")

    if scene.receive_territory:
        PlayerDiscoveredTerritory.objects.get_or_create(session=session, territory=scene.receive_territory)
        if not PlayerTerritory.objects.filter(session=session, territory=scene.receive_territory).exists():
            PlayerTerritory.objects.create(session=session, territory=scene.receive_territory)
            if f"You have acquired: {scene.receive_territory.name}" not in logs:
                logs.append(f"You have acquired: {scene.receive_territory.name}")

    if scene.lose_territory:
        pt = PlayerTerritory.objects.filter(session=session, territory=scene.lose_territory).first()
        if pt:
            pt.delete()
            if f"You have lost: {scene.lose_territory.name}" not in logs:
                logs.append(f"You have lost: {scene.lose_territory.name}")

    return logs


def get_turn_summary(session, income_totals, newly_unlocked):
    """
    Assembles the end-of-turn summary dict for the template.
    income_totals: dict with keys cash, heat, rep (actual deltas).
    newly_unlocked: list of Scene objects unlocked this turn.
    """
    has_activity = (
        any(income_totals.values())
        or bool(newly_unlocked)
    )
    return {
        'income_totals': income_totals,
        'newly_unlocked': newly_unlocked,
        'has_activity': has_activity,
    }
