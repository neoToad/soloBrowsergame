from django.contrib import admin

from game.models import Contact, Gang, Property, Territory


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("name", "property_type", "cash_per_turn", "heat_per_turn", "rep_per_turn")
    list_filter = ("property_type",)
    search_fields = ("name",)


@admin.register(Territory)
class TerritoryAdmin(admin.ModelAdmin):
    list_display = ("name", "cash_per_turn", "heat_per_turn", "rep_per_turn")
    search_fields = ("name", "key")


@admin.register(Gang)
class GangAdmin(admin.ModelAdmin):
    list_display = ("key", "name")
    search_fields = ("key", "name")
    prepopulated_fields = {"key": ("name",)}


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("key", "name")
    search_fields = ("key", "name")
    prepopulated_fields = {"key": ("name",)}
