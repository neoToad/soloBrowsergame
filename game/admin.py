from django.contrib import admin
from .models import (
    Arc, Quest, Item, Requirement, RequirementGroup, Scene, Choice,
    GameSession, PlayerStats, PlayerInventory, SceneItem, CompletedQuest,
    Enemy, CombatEncounter, CombatState, EventLog
)

@admin.register(Arc)
class ArcAdmin(admin.ModelAdmin):
    list_display = ('key', 'title', 'order')

@admin.register(Quest)
class QuestAdmin(admin.ModelAdmin):
    list_display = ('key', 'title', 'arc', 'arc_order', 'is_unlocked')

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('key', 'name', 'is_consumable')

@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = ('condition_type', 'stat_name', 'required_item', 'required_quest', 'stat_value')

@admin.register(RequirementGroup)
class RequirementGroupAdmin(admin.ModelAdmin):
    list_display = ('label', 'logic')
    filter_horizontal = ('requirements',)

@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = ('key', 'title', 'quest', 'is_hub', 'is_combat', 'is_ending', 'requires_roll', 'order')
    filter_horizontal = ('requirements',)

@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ('scene', 'label', 'target_scene', 'consume_item', 'order')
    filter_horizontal = ('requirements',)

@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ('session_key', 'current_scene', 'created_at')

@admin.register(PlayerStats)
class PlayerStatsAdmin(admin.ModelAdmin):
    list_display = ('session', 'level', 'experience', 'hp', 'strength', 'agility', 'intellect', 'charisma')

@admin.register(PlayerInventory)
class PlayerInventoryAdmin(admin.ModelAdmin):
    list_display = ('session', 'item', 'quantity', 'acquired_at')

@admin.register(SceneItem)
class SceneItemAdmin(admin.ModelAdmin):
    list_display = ('scene', 'item', 'quantity', 'award_once')

@admin.register(CompletedQuest)
class CompletedQuestAdmin(admin.ModelAdmin):
    list_display = ('session', 'quest', 'ending_type', 'completed_at')

@admin.register(Enemy)
class EnemyAdmin(admin.ModelAdmin):
    list_display = ('key', 'name', 'max_hp', 'attack_modifier', 'defense')

@admin.register(CombatEncounter)
class CombatEncounterAdmin(admin.ModelAdmin):
    list_display = ('scene', 'enemy')

@admin.register(CombatState)
class CombatStateAdmin(admin.ModelAdmin):
    list_display = ('session', 'enemy', 'enemy_hp', 'turn_number', 'is_active')

@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ('session', 'timestamp', 'text')
