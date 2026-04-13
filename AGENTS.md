# Agent Guide

## Stack
- Django 6.0+, Python 3.10+, HTMX (no JS frameworks)
- SQLite (dev), templates in `templates/`, static in `static/`


## Architecture Rules
- **Business logic → services only.** Views read request, call service, return response. Never put logic in views.

## Key Files
| Path | Purpose |
|------|---------|
| `game/views.py` | HTTP handlers only |
| `game/services/` | All game logic |
| `game/models/` | player, world, items, combat, requirements, events |
| `game/utils.py` | `roll_d20`, `stat_modifier`, `get_effective_stats` |
| `game/constants.py` | Scene keys, stat field map, flavor text |

