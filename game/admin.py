from django.contrib import admin
from django.db.models import Count
from django.urls import path, reverse
from django.utils.html import format_html
from .models import (
    Arc, Quest, Item, Requirement, RequirementGroup, Scene, Choice,
    GameSession, PlayerStats, PlayerInventory, SceneItem, CompletedQuest,
    Enemy, CombatEncounter, CombatState, EventLog, SceneUnlock, PlayerSceneState
)

# 2. Custom actions
@admin.action(description='Force-close selected combat states')
def close_combat_states(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f'{updated} combat state(s) closed.')

# 3. Inline classes
class ChoiceInline(admin.TabularInline):
    model = Choice
    fk_name = 'scene'
    extra = 1
    fields = ('label', 'order', 'target_scene', 'consume_item')
    autocomplete_fields = ('target_scene', 'consume_item')
    show_change_link = True

class SceneItemInline(admin.TabularInline):
    model = SceneItem
    extra = 0
    fields = ('item', 'quantity', 'award_once')

class CombatEncounterInline(admin.StackedInline):
    model = CombatEncounter
    extra = 0
    autocomplete_fields = ('enemy',)

class SceneInline(admin.TabularInline):
    model = Scene
    extra = 0
    fields = ('key', 'title', 'order', 'scene_type')
    show_change_link = True

class PlayerStatsInline(admin.StackedInline):
    model = PlayerStats
    extra = 0
    readonly_fields = ('level', 'experience', 'stat_points')
    can_delete = False

class PlayerInventoryInline(admin.TabularInline):
    model = PlayerInventory
    extra = 0
    fields = ('item', 'quantity', 'acquired_at')
    readonly_fields = ('acquired_at',)

# 4. Admin classes
@admin.register(Arc)
class ArcAdmin(admin.ModelAdmin):
    list_display = ('key', 'title', 'order')
    search_fields = ('key', 'title')

@admin.register(Quest)
class QuestAdmin(admin.ModelAdmin):
    list_display = (
        'key', 'title', 'arc', 'arc_order', 'is_unlocked', 'is_repeatable',
        'entrance_scene',
        'scene_count', 'view_graph_link',
    )
    list_filter = ('arc', 'is_unlocked', 'is_repeatable')
    search_fields = ('key', 'title')
    list_select_related = True
    autocomplete_fields = ('entrance_scene',)
    filter_horizontal = ('requirements',)
    inlines = [SceneInline]
    save_on_top = True

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _scene_count=Count('scenes', distinct=True)
        )

    @admin.display(description='Scenes', ordering='_scene_count')
    def scene_count(self, obj):
        return obj._scene_count

    @admin.display(description='Graph')
    def view_graph_link(self, obj):
        url = reverse('admin:quest_graph', args=[obj.pk])
        return format_html('<a href="{}">View Graph →</a>', url)

    def get_urls(self):
        custom = [
            path(
                '<int:quest_id>/graph/',
                self.admin_site.admin_view(self.graph_view),
                name='quest_graph',
            ),
        ]
        return custom + super().get_urls()

    def graph_view(self, request, quest_id):
        from django.shortcuts import get_object_or_404, render
        quest = get_object_or_404(Quest, pk=quest_id)
        scenes = (
            Scene.objects
            .filter(quest=quest)
            .prefetch_related(
                'choices',
                'choices__target_scene',
                'choices__success_scene',
                'choices__failure_scene',
                'choices__consume_item',
                'scene_items__item',
                'combat_encounter__enemy',
                'combat_encounter__enemy__victory_scene',
                'combat_encounter__enemy__defeat_scene',
            )
            .order_by('order')
        )
        context = {
            **self.admin_site.each_context(request),
            'quest': quest,
            'scenes': scenes,
            'title': f'Scene Graph — {quest.title}',
            'opts': Quest._meta,
        }
        return render(request, 'admin/game/quest_graph.html', context)

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('key', 'name', 'is_consumable', 'effect_summary')
    list_filter = ('is_consumable', 'effect_type', 'equip_slot')
    search_fields = ('key', 'name', 'description')
    prepopulated_fields = {'key': ('name',)}
    fieldsets = (
        (None, {
            'fields': ('key', 'name', 'description', 'is_consumable')
        }),
        ('Active Effect', {
            'fields': ('effect_type', 'effect_stat', 'effect_value'),
            'description': 'Fires when player clicks USE. Consumes item if is_consumable=True.',
        }),
        ('Passive Bonus', {
            'fields': ('equip_slot', 'passive_stat', 'passive_value'),
            'description': 'Applied automatically while the item is carried. Never consumed.',
        }),
    )
    save_on_top = True

    @admin.display(description='Effect Summary')
    def effect_summary(self, obj):
        parts = []
        if obj.effect_type:
            parts.append(f'USE:{obj.effect_type}')
        if obj.passive_stat:
            parts.append(f'PASSIVE:{obj.passive_stat}+{obj.passive_value}')
        return ', '.join(parts) or '—'

@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = ('condition_type', 'stat_name', 'required_item', 'required_quest', 'stat_value')
    search_fields = ('stat_name',)

@admin.register(RequirementGroup)
class RequirementGroupAdmin(admin.ModelAdmin):
    list_display = ('label', 'logic')
    search_fields = ('label',)
    filter_horizontal = ('requirements',)

@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = ('key', 'title', 'quest', 'scene_type', 'requires_roll', 'order')
    list_filter = ('quest', 'scene_type', 'requires_roll', 'ending_type')
    search_fields = ('key', 'title', 'body')
    list_select_related = True
    filter_horizontal = ('requirements',)
    inlines = [ChoiceInline, SceneItemInline, CombatEncounterInline]
    save_on_top = True

@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ('scene', 'label', 'quest', 'target_scene', 'consume_item', 'order')
    list_filter = ('scene__quest',)
    search_fields = ('label', 'scene__key')
    list_select_related = True
    autocomplete_fields = ('target_scene', 'success_scene', 'failure_scene', 'consume_item', 'quest')
    filter_horizontal = ('requirements',)
    save_on_top = True

@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ('session_key', 'current_scene', 'created_at')
    search_fields = ('session_key',)
    readonly_fields = ('session_key', 'created_at')
    inlines = [PlayerStatsInline, PlayerInventoryInline]

@admin.register(PlayerStats)
class PlayerStatsAdmin(admin.ModelAdmin):
    list_display = ('session', 'level', 'experience', 'hp', 'strength', 'agility', 'intellect', 'charisma')
    list_select_related = True

@admin.register(PlayerInventory)
class PlayerInventoryAdmin(admin.ModelAdmin):
    list_display = ('session', 'item', 'quantity', 'acquired_at')
    list_filter = ('item',)
    search_fields = ('session__session_key', 'item__name')
    list_select_related = True
    readonly_fields = ('acquired_at',)

@admin.register(SceneItem)
class SceneItemAdmin(admin.ModelAdmin):
    list_display = ('scene', 'item', 'quantity', 'award_once')
    list_filter = ('scene', 'item')
    list_select_related = True

@admin.register(CompletedQuest)
class CompletedQuestAdmin(admin.ModelAdmin):
    list_display = ('session', 'quest', 'ending_type', 'completed_at')
    list_filter = ('quest', 'ending_type')
    list_select_related = True
    readonly_fields = ('completed_at',)
    date_hierarchy = 'completed_at'

@admin.register(Enemy)
class EnemyAdmin(admin.ModelAdmin):
    list_display = ('key', 'name', 'max_hp', 'defense', 'attack_modifier', 'damage_range')
    search_fields = ('key', 'name')
    prepopulated_fields = {'key': ('name',)}
    autocomplete_fields = ('victory_scene', 'defeat_scene')
    save_on_top = True

    @admin.display(description='Damage')
    def damage_range(self, obj):
        return f'{obj.damage_min}–{obj.damage_max}'

@admin.register(CombatEncounter)
class CombatEncounterAdmin(admin.ModelAdmin):
    list_display = ('scene', 'enemy')
    list_select_related = True
    autocomplete_fields = ('scene', 'enemy')

@admin.register(CombatState)
class CombatStateAdmin(admin.ModelAdmin):
    list_display = ('session', 'enemy', 'enemy_hp', 'turn_number', 'is_active')
    list_filter = ('is_active', 'enemy')
    list_select_related = True
    actions = [close_combat_states]

@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ('session', 'timestamp', 'text')
    list_filter = ('session',)
    search_fields = ('text', 'session__session_key')
    list_select_related = True
    readonly_fields = ('session', 'timestamp')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)


@admin.register(SceneUnlock)
class SceneUnlockAdmin(admin.ModelAdmin):
    list_display = ('from_scene', 'unlocks_scene', 'requires_choice', 'requires_item')
    list_select_related = True
    autocomplete_fields = ('from_scene', 'unlocks_scene', 'requires_choice', 'requires_item')


@admin.register(PlayerSceneState)
class PlayerSceneStateAdmin(admin.ModelAdmin):
    list_display = ('session', 'scene', 'state')
    list_filter = ('state',)
    list_select_related = True
