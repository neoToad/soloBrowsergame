import random

def process_turn_income(session):
    """
    Applies passive income from all un-contested PlayerProperties.
    Returns (log_strings: list[str], income_totals: dict).
    Heat is clamped at 0. stats.save() called once if any property paid out.
    """
    from ..models import PlayerProperty
    stats = session.stats
    totals = {'cash': 0, 'heat': 0, 'rep': 0}
    logs = []

    properties = PlayerProperty.objects.filter(
        session=session, is_contested=False
    ).select_related('property')

    for pp in properties:
        prop = pp.property
        stats.cash += prop.income_per_turn
        totals['cash'] += prop.income_per_turn

        actual_heat_removed = min(prop.heat_reduction, stats.heat)
        stats.heat = max(0, stats.heat - prop.heat_reduction)
        totals['heat'] -= actual_heat_removed

        stats.rep += prop.rep_bonus
        totals['rep'] += prop.rep_bonus

        parts = []
        if prop.income_per_turn:  parts.append(f"+${prop.income_per_turn}")
        if actual_heat_removed:   parts.append(f"-{actual_heat_removed} heat")
        if prop.rep_bonus:        parts.append(f"+{prop.rep_bonus} rep")
        if parts:
            logs.append(f"{prop.name}: {', '.join(parts)}.")

    if properties.exists():
        stats.save()

    return logs, totals


def check_rival_contests(session):
    """
    Rolls against heat to trigger a rival contest on a random contestable property.
    Returns (log_string: str | None, unlocked_scene: Scene | None).
    """
    from ..models import PlayerProperty
    from ..models.property import RivalClaim

    stats = session.stats
    contest_chance = stats.heat / 200.0
    if random.random() >= contest_chance:
        return None, None

    contestable = PlayerProperty.objects.filter(
        session=session,
        is_contested=False,
        property__is_contestable=True,
        property__resolution_scene__isnull=False,   # only contest if a resolution exists
    ).select_related('property__resolution_scene')

    if not contestable.exists():
        return None, None

    target = random.choice(list(contestable))
    target.is_contested = True
    target.save()

    resolution_scene = target.property.resolution_scene
    RivalClaim.objects.create(player_property=target, resolution_scene=resolution_scene)

    log = (
        f"A rival crew is moving on {target.property.name}. "
        f"Deal with it before you lose the place."
    )
    return log, resolution_scene


def resolve_contest(session, claim, ending_type):
    """
    Called when the player completes the contest resolution scene.
    ending_type: 'victory' | 'defeat' | 'neutral'
    Returns a log string. Callers create EventLog entries.
    """
    pp = claim.player_property
    prop_name = pp.property.name

    if ending_type == 'victory':
        claim.delete()
        pp.is_contested = False
        pp.save()
        return f"Rival backed down. {prop_name} is yours again."
    else:
        pp.delete()   # cascade-deletes claim
        return f"You couldn't hold it. {prop_name} is gone."


def get_turn_summary(session, income_totals, newly_unlocked):
    """
    Assembles the end-of-turn summary dict for the template.
    income_totals: dict with keys cash, heat, rep (actual deltas).
    newly_unlocked: list of Scene objects unlocked this turn.
    """
    from ..models.property import RivalClaim
    active_claims = list(
        RivalClaim.objects.filter(
            player_property__session=session
        ).select_related('player_property__property', 'resolution_scene')
    )
    has_activity = (
        any(income_totals.values())
        or bool(newly_unlocked)
        or bool(active_claims)
    )
    return {
        'income_totals': income_totals,
        'newly_unlocked': newly_unlocked,
        'active_claims': active_claims,
        'has_activity': has_activity,
    }
