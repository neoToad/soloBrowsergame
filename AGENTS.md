# Agent Guide

## Stack
- Django 6.0+, Python 3.10+, HTMX (no JS frameworks)
- SQLite (dev), templates in `templates/`, static in `static/`


## Architecture Rules
- **Business logic → services only.** Views read request, call service, return response. Never put logic in views.

