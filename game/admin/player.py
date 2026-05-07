from django.contrib import admin

from game.admin.inlines import (
    PlayerContactInline,
    PlayerDiscoveredTerritoryInline,
    PlayerGangStandingInline,
    PlayerInventoryInline,
    PlayerPropertyInline,
    PlayerStatsInline,
    PlayerTerritoryInline,
)
from game.models import (
    CompletedQuest,
    GameSession,
    PlayerContact,
    PlayerDiscoveredTerritory,
    PlayerGangStanding,
    PlayerInventory,
    PlayerProperty,
    PlayerStats,
    PlayerTerritory,
)


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ("session_key", "turn_counter", "current_scene", "created_at")
    search_fields = ("session_key",)
    readonly_fields = ("session_key", "created_at")
    inlines = [
        PlayerStatsInline,
        PlayerInventoryInline,
        PlayerPropertyInline,
        PlayerTerritoryInline,
        PlayerDiscoveredTerritoryInline,
        PlayerContactInline,
        PlayerGangStandingInline,
    ]


@admin.register(PlayerStats)
class PlayerStatsAdmin(admin.ModelAdmin):
    list_display = ("session", "level", "experience", "hp", "strength", "agility", "intellect", "charisma", "cash", "heat", "rep")
    list_select_related = True


@admin.register(PlayerInventory)
class PlayerInventoryAdmin(admin.ModelAdmin):
    list_display = ("session", "item", "quantity", "acquired_at")
    list_filter = ("item",)
    search_fields = ("session__session_key", "item__name")
    list_select_related = True
    readonly_fields = ("acquired_at",)


@admin.register(CompletedQuest)
class CompletedQuestAdmin(admin.ModelAdmin):
    list_display = ("session", "quest", "ending_type", "completed_at")
    list_filter = ("quest", "ending_type")
    list_select_related = True
    readonly_fields = ("completed_at",)
    date_hierarchy = "completed_at"


@admin.register(PlayerProperty)
class PlayerPropertyAdmin(admin.ModelAdmin):
    list_display = ("session", "property")
    list_select_related = True


@admin.register(PlayerTerritory)
class PlayerTerritoryAdmin(admin.ModelAdmin):
    list_display = ("session", "territory")
    list_select_related = True


@admin.register(PlayerDiscoveredTerritory)
class PlayerDiscoveredTerritoryAdmin(admin.ModelAdmin):
    list_display = ("session", "territory", "discovered_at")
    list_select_related = True
    readonly_fields = ("discovered_at",)


@admin.register(PlayerContact)
class PlayerContactAdmin(admin.ModelAdmin):
    list_display = ("session", "contact", "acquired_at")
    list_filter = ("contact",)
    list_select_related = True
    readonly_fields = ("acquired_at",)


@admin.register(PlayerGangStanding)
class PlayerGangStandingAdmin(admin.ModelAdmin):
    list_display = ("session", "gang", "standing")
    list_filter = ("gang",)
    list_select_related = True
