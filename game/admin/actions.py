from django.contrib import admin


@admin.action(description="Force-close selected combat states")
def close_combat_states(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f"{updated} combat state(s) closed.")


@admin.action(description="Show export_quest commands for selected quests")
def show_export_quest_commands(modeladmin, request, queryset):
    for quest in queryset.order_by("key"):
        modeladmin.message_user(request, f"python manage.py export_quest {quest.key}")
