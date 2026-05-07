from django.contrib import admin

from game.admin.actions import close_combat_states
from game.models import CombatEncounter, CombatState, Enemy, EventLog, SceneItem


@admin.register(SceneItem)
class SceneItemAdmin(admin.ModelAdmin):
    list_display = ("scene", "item", "quantity", "award_once")
    list_filter = ("scene", "item")
    list_select_related = True


@admin.register(Enemy)
class EnemyAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "max_hp", "defense", "attack_modifier", "damage_range")
    search_fields = ("key", "name")
    prepopulated_fields = {"key": ("name",)}
    autocomplete_fields = ()
    save_on_top = True

    @admin.display(description="Damage")
    def damage_range(self, obj):
        return f"{obj.damage_min}–{obj.damage_max}"


@admin.register(CombatEncounter)
class CombatEncounterAdmin(admin.ModelAdmin):
    list_display = ("scene", "enemy")
    list_select_related = True
    autocomplete_fields = ("scene", "enemy")
    fields = ("scene", "enemy", "victory_scene", "victory_arrival_flavor", "defeat_scene", "defeat_arrival_flavor")


@admin.register(CombatState)
class CombatStateAdmin(admin.ModelAdmin):
    list_display = ("session", "enemy", "enemy_hp", "turn_number", "is_active")
    list_filter = ("is_active", "enemy")
    list_select_related = True
    actions = [close_combat_states]


@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ("session", "timestamp", "text")
    list_filter = ("session",)
    search_fields = ("text", "session__session_key")
    list_select_related = True
    readonly_fields = ("session", "timestamp")
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)
