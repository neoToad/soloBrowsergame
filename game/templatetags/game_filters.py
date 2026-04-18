from django import template
from game.services.progression import XP_THRESHOLDS, MAX_LEVEL, RANK_TITLES, LEVEL_UP_FLAVOR

register = template.Library()


@register.filter
def hp_color_class(current, maximum):
    """
    Returns a CSS class name based on HP percentage.
    >60% → hp-healthy (green), 30–60% → hp-warning (yellow), ≤30% → hp-danger (red).
    Usage: {{ stats.hp|hp_color_class:stats.max_hp }}
    """
    try:
        pct = max(0, min(100, int(int(current) / int(maximum) * 100)))
    except (ValueError, ZeroDivisionError, TypeError):
        pct = 0
    if pct > 60:
        return 'hp-healthy'
    elif pct > 30:
        return 'hp-warning'
    return 'hp-danger'


@register.filter
def hp_pct(current, maximum):
    """
    Returns HP as an integer percentage clamped 0–100.
    Usage: {{ stats.hp|hp_pct:stats.max_hp }}
    """
    try:
        pct = int(int(current) / int(maximum) * 100)
        return max(0, min(100, pct))
    except (ValueError, ZeroDivisionError, TypeError):
        return 0


@register.filter
def xp_pct(experience, level):
    """
    Returns XP progress within the current level as an integer percentage 0–100.
    At MAX_LEVEL, always returns 100.
    Usage: {{ stats.experience|xp_pct:stats.level }}
    """
    try:
        level = int(level)
        experience = int(experience)
        if level >= MAX_LEVEL:
            return 100
        floor   = XP_THRESHOLDS.get(level, 0)
        ceiling = XP_THRESHOLDS.get(level + 1, floor + 1)
        span    = ceiling - floor
        if span <= 0:
            return 100
        return max(0, min(100, int((experience - floor) / span * 100)))
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def rank_title(level):
    """
    Returns the street rank title for the given level integer.
    Usage: {{ stats.level|rank_title }}
    """
    try:
        return RANK_TITLES.get(int(level), '—')
    except (ValueError, TypeError):
        return '—'


@register.filter
def levelup_flavor(level):
    """
    Returns the crime-setting flavor string for the given level number.
    LEVEL_UP_FLAVOR is keyed by level number.
    Usage: {{ stats.level|levelup_flavor }}
    """
    try:
        return LEVEL_UP_FLAVOR.get(int(level), '')
    except (ValueError, TypeError, KeyError):
        return ''
