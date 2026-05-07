from django.contrib import admin

from game.models import (
    Choice,
    CombatEncounter,
    PlayerContact,
    PlayerDiscoveredTerritory,
    PlayerGangStanding,
    PlayerInventory,
    PlayerProperty,
    PlayerStats,
    PlayerTerritory,
    RequirementGroup,
    SceneContact,
    SceneGangStanding,
    SceneItem,
)


class RequirementInline(admin.TabularInline):
    model = RequirementGroup.requirements.through
    extra = 1
    fields = (
        "requirement",
        "condition_type",
        "stat_name",
        "stat_value",
        "required_item",
        "required_quest",
        "required_contact",
    )
    readonly_fields = (
        "condition_type",
        "stat_name",
        "stat_value",
        "required_item",
        "required_quest",
        "required_contact",
    )

    @admin.display(description="Type")
    def condition_type(self, obj):
        return obj.requirement.get_condition_type_display() if obj.requirement else ""

    @admin.display(description="Stat Name")
    def stat_name(self, obj):
        return obj.requirement.stat_name if obj.requirement else ""

    @admin.display(description="Value")
    def stat_value(self, obj):
        return obj.requirement.stat_value if obj.requirement else ""

    @admin.display(description="Item")
    def required_item(self, obj):
        return obj.requirement.required_item if obj.requirement else ""

    @admin.display(description="Quest")
    def required_quest(self, obj):
        return obj.requirement.required_quest if obj.requirement else ""

    @admin.display(description="Contact")
    def required_contact(self, obj):
        return obj.requirement.required_contact if obj.requirement else ""


class ChoiceRequirementGroupInline(admin.StackedInline):
    model = Choice.requirements.through
    extra = 0
    verbose_name = "Requirement Group"
    verbose_name_plural = "Requirement Groups"
    show_change_link = True


class ChoiceInline(admin.TabularInline):
    model = Choice
    fk_name = "scene"
    extra = 1
    fields = ("label", "order", "target_scene", "success_scene", "failure_scene")
    autocomplete_fields = ("target_scene", "success_scene", "failure_scene")
    show_change_link = True


class SceneItemInline(admin.TabularInline):
    model = SceneItem
    extra = 0
    fields = ("item", "quantity", "award_once")


class SceneContactInline(admin.TabularInline):
    model = SceneContact
    extra = 0
    fields = ("contact", "action", "award_once")


class SceneGangStandingInline(admin.TabularInline):
    model = SceneGangStanding
    extra = 0
    fields = ("gang", "standing_change")


class CombatEncounterInline(admin.StackedInline):
    model = CombatEncounter
    fk_name = "scene"
    extra = 0
    autocomplete_fields = ("enemy",)


class PlayerStatsInline(admin.StackedInline):
    model = PlayerStats
    extra = 0
    fields = ("strength", "agility", "intellect", "charisma", "hp", "max_hp", "cash", "heat", "rep")
    readonly_fields = ("level", "experience", "stat_points", "stat_points_awarded")
    can_delete = False


class PlayerInventoryInline(admin.TabularInline):
    model = PlayerInventory
    extra = 0
    fields = ("item", "quantity", "acquired_at")
    readonly_fields = ("acquired_at",)


class PlayerPropertyInline(admin.TabularInline):
    model = PlayerProperty
    extra = 0
    fields = ("property",)


class PlayerTerritoryInline(admin.TabularInline):
    model = PlayerTerritory
    extra = 0
    fields = ("territory",)


class PlayerDiscoveredTerritoryInline(admin.TabularInline):
    model = PlayerDiscoveredTerritory
    extra = 0
    fields = ("territory", "discovered_at")
    readonly_fields = ("discovered_at",)


class PlayerContactInline(admin.TabularInline):
    model = PlayerContact
    extra = 0
    fields = ("contact", "acquired_at")
    readonly_fields = ("acquired_at",)


class PlayerGangStandingInline(admin.TabularInline):
    model = PlayerGangStanding
    extra = 0
    fields = ("gang", "standing")
