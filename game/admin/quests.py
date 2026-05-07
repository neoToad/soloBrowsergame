from django.contrib import admin
from django.db.models import Count
from django.urls import path, reverse
from django.utils.html import format_html

from game.admin.actions import show_export_quest_commands
from game.admin.inlines import (
    ChoiceInline,
    ChoiceRequirementGroupInline,
    CombatEncounterInline,
    RequirementInline,
    SceneContactInline,
    SceneGangStandingInline,
    SceneItemInline,
)
from game.admin.quest_builder_urls import build_quest_builder_urls
from game.models import Arc, Choice, Item, Quest, Requirement, RequirementGroup, Scene


@admin.register(Arc)
class ArcAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "order")
    search_fields = ("key", "title")


@admin.register(Quest)
class QuestAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "title",
        "arc",
        "arc_order",
        "is_unlocked",
        "is_repeatable",
        "entrance_scene",
        "scene_count",
        "view_builder_link",
        "export_command_hint",
    )
    list_filter = ("arc", "is_unlocked", "is_repeatable")
    search_fields = ("key", "title")
    list_select_related = True
    autocomplete_fields = ("entrance_scene",)
    filter_horizontal = ("requirements", "hub_scenes")
    inlines = []
    save_on_top = True
    actions = [show_export_quest_commands]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_scene_count=Count("scenes", distinct=True))

    @admin.display(description="Scenes", ordering="_scene_count")
    def scene_count(self, obj):
        return obj._scene_count

    @admin.display(description="Builder")
    def view_builder_link(self, obj):
        url = reverse("admin:quest_builder_canvas", args=[obj.pk])
        graph_url = reverse("admin:quest_graph", args=[obj.pk])
        return format_html(
            '<a href="{}">Open Builder →</a><br><small><a href="{}">View Static Graph</a></small>',
            url,
            graph_url,
        )

    @admin.display(description="Export Command")
    def export_command_hint(self, obj):
        return format_html("<code>python manage.py export_quest {}</code>", obj.key)

    def get_urls(self):
        custom = [
            path(
                "<int:quest_id>/graph/",
                self.admin_site.admin_view(self.graph_view),
                name="quest_graph",
            ),
            *build_quest_builder_urls(self.admin_site),
        ]
        return custom + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["quest_builder_url"] = reverse("admin:quest_builder_list")
        return super().changelist_view(request, extra_context=extra_context)

    def graph_view(self, request, quest_id):
        from django.shortcuts import get_object_or_404, render

        quest = get_object_or_404(Quest, pk=quest_id)
        scenes = (
            quest.scenes.prefetch_related(
                "choices",
                "choices__target_scene",
                "choices__success_scene",
                "choices__failure_scene",
                "consume_item",
                "scene_items__item",
                "combat_encounter__enemy",
                "combat_encounter__victory_scene",
                "combat_encounter__defeat_scene",
            ).order_by("order")
        )
        context = {
            **self.admin_site.each_context(request),
            "quest": quest,
            "scenes": scenes,
            "title": f"Scene Graph — {quest.title}",
            "opts": Quest._meta,
        }
        return render(request, "admin/game/quest_graph.html", context)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "is_consumable", "effect_summary")
    list_filter = ("is_consumable", "effect_type")
    search_fields = ("key", "name", "description")
    prepopulated_fields = {"key": ("name",)}
    fieldsets = (
        (None, {"fields": ("key", "name", "description", "is_consumable")}),
        (
            "Active Effect",
            {
                "fields": ("effect_type", "effect_stat", "effect_value"),
                "description": "Fires when player clicks USE. Consumes item if is_consumable=True.",
            },
        ),
        (
            "Passive Bonus",
            {
                "fields": ("passive_stat", "passive_value"),
                "description": "Applied automatically while the item is carried. Never consumed.",
            },
        ),
    )
    save_on_top = True

    @admin.display(description="Effect Summary")
    def effect_summary(self, obj):
        parts = []
        if obj.effect_type:
            parts.append(f"USE:{obj.effect_type}")
        if obj.passive_stat:
            parts.append(f"PASSIVE:{obj.passive_stat}+{obj.passive_value}")
        return ", ".join(parts) or "—"


@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = ("condition_type", "stat_name", "required_item", "required_quest", "required_contact", "stat_value")
    search_fields = ("stat_name",)


@admin.register(RequirementGroup)
class RequirementGroupAdmin(admin.ModelAdmin):
    list_display = ("label", "logic")
    search_fields = ("label",)
    inlines = [RequirementInline]


@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "body_preview", "scene_type", "requires_roll", "cash_change", "rep_change", "heat_change", "order")
    list_filter = ("scene_type", "requires_roll", "ending_type")
    search_fields = ("key", "title", "body")
    list_select_related = True
    prepopulated_fields = {"key": ("title",)}
    readonly_fields = ("key_format_note",)
    autocomplete_fields = (
        "consume_item",
        "receive_property",
        "lose_property",
        "receive_territory",
        "lose_territory",
        "discover_territory",
    )
    fieldsets = (
        ("Identity", {"fields": ("key", "key_format_note", "title", "order")}),
        ("Narrative", {"fields": ("body",)}),
        ("Type", {"fields": ("scene_type", "ending_type")}),
        ("Roll Settings", {"fields": ("requires_roll", "roll_difficulty", "roll_stat")}),
        (
            "Arrival Effects",
            {
                "fields": (
                    "cash_change",
                    "rep_change",
                    "heat_change",
                    "consume_item",
                    "receive_property",
                    "lose_property",
                    "receive_territory",
                    "lose_territory",
                    "discover_territory",
                ),
                "description": "Stat rewards/penalties, property/territory changes, and item consumption upon arrival.",
            },
        ),
    )
    inlines = [ChoiceInline, SceneItemInline, SceneContactInline, SceneGangStandingInline, CombatEncounterInline]
    save_on_top = True

    @admin.display(description="Body Preview")
    def body_preview(self, obj):
        return (obj.body[:77] + "...") if len(obj.body) > 80 else obj.body

    @admin.display(description="Key Format")
    def key_format_note(self, obj):
        return "{quest_key}__{scene_slug}"


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ("scene", "label", "target_scene", "order")
    list_filter = ("scene__quest",)
    search_fields = ("label", "scene__key")
    list_select_related = True
    autocomplete_fields = ("target_scene", "success_scene", "failure_scene")
    fieldsets = (
        ("Basic", {"fields": ("scene", "label", "order", "arrival_flavor", "failure_arrival_flavor")}),
        (
            "Routing",
            {
                "fields": ("target_scene", "success_scene", "failure_scene"),
                "description": "For non-roll choices use target_scene. For roll choices use success_scene / failure_scene and leave target_scene blank.",
            },
        ),
        (
            "Flags",
            {
                "fields": ("set_flag_name", "clear_flag_name"),
                "description": (
                    "Use a registered flag key or one of these dynamic patterns: "
                    "approach_<key>, approach_<key>_failed, ran_<activity_key>_<3|5|10>x."
                ),
            },
        ),
    )
    inlines = [ChoiceRequirementGroupInline]
    save_on_top = True
