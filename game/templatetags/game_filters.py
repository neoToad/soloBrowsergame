from django import template

register = template.Library()


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
