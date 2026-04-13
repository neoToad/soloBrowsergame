from dataclasses import dataclass
from django.db import models
from .items import Item

@dataclass
class PlayerContext:
    stats: object        # PlayerStats instance
    inventory: dict      # {item_id: PlayerInventory instance}
    completed_map: dict  # {quest_id: ending_type string}
    flags: dict = None

    def __post_init__(self):
        if self.flags is None:
            self.flags = {}

class Requirement(models.Model):
    """
    A single evaluatable condition. Requirements are grouped by
    RequirementGroup which controls AND/OR logic between them.
    """

    CONDITION_TYPES = [
        ('stat_gte',        'Stat >= value'),
        ('stat_lte',        'Stat <= value'),
        ('has_item',        'Has item in inventory'),
        ('missing_item',    'Does not have item'),
        ('quest_completed', 'Quest completed'),
        ('quest_not_done',  'Quest not completed'),
        ('quest_ending',    'Quest completed with specific ending'),
        ('level_gte',       'Player level >= value'),
        ('xp_gte',          'Player XP >= value'),
        ('has_flag',     'Flag is set'),
        ('missing_flag', 'Flag is not set'),
    ]

    condition_type = models.CharField(max_length=50, choices=CONDITION_TYPES)

    # Flag conditions
    flag_name = models.CharField(max_length=100, blank=True)

    # Stat conditions
    stat_name  = models.CharField(max_length=50, blank=True)
    stat_value = models.IntegerField(default=0, blank=True)

    # Item conditions
    required_item = models.ForeignKey(
                        Item,
                        null=True, blank=True,
                        on_delete=models.SET_NULL,
                        related_name='+'
                    )

    # Quest conditions
    required_quest = models.ForeignKey(
                         'Quest',
                         null=True, blank=True,
                         on_delete=models.SET_NULL,
                         related_name='+'
                     )
    required_ending_type = models.CharField(max_length=20, blank=True)

    def evaluate(self, ctx: PlayerContext):
        """
        Returns True if this condition is met.
          ctx — PlayerContext instance (stats, inventory, completed_map)
        """
        ct = self.condition_type

        if ct == 'stat_gte':
            return getattr(ctx.stats, self.stat_name, 0) >= self.stat_value
        if ct == 'stat_lte':
            return getattr(ctx.stats, self.stat_name, 0) <= self.stat_value
        if ct == 'has_item':
            return self.required_item_id in ctx.inventory
        if ct == 'missing_item':
            return self.required_item_id not in ctx.inventory
        if ct == 'quest_completed':
            return self.required_quest_id in ctx.completed_map
        if ct == 'quest_not_done':
            return self.required_quest_id not in ctx.completed_map
        if ct == 'quest_ending':
            return ctx.completed_map.get(self.required_quest_id) == \
                   self.required_ending_type
        if ct == 'level_gte':
            return ctx.stats.level >= self.stat_value
        if ct == 'xp_gte':
            return ctx.stats.experience >= self.stat_value

        if ct == 'has_flag':
            return bool(ctx.flags.get(self.flag_name))
        if ct == 'missing_flag':
            return not ctx.flags.get(self.flag_name)

        return False

    def __str__(self):
        return (
            f"{self.get_condition_type_display()} — "
            f"{self.stat_name or self.required_item or self.required_quest or ''}"
        )


class RequirementGroup(models.Model):
    """
    A named group of Requirements with internal AND or OR logic.
    Multiple groups on a Scene or Choice are always AND'd together —
    every group must pass. The OR/AND logic is internal to each group.

    Example: 'Has key OR high agility, AND must have completed the mine'
      Group 1 (logic: any): has_item rusty_key | stat_gte agility 8
      Group 2 (logic: all): quest_completed the_haunted_mine
    Both groups must pass. Within group 1, either condition is enough.
    """

    LOGIC_CHOICES = [
        ('all', 'All must pass (AND)'),
        ('any', 'Any one must pass (OR)'),
    ]

    label        = models.CharField(max_length=200)
    logic        = models.CharField(
                       max_length=10,
                       choices=LOGIC_CHOICES,
                       default='all'
                   )
    requirements = models.ManyToManyField(
                       Requirement,
                       related_name='groups'
                   )

    def evaluate(self, ctx: PlayerContext):
        results = [
            r.evaluate(ctx)
            for r in self.requirements.all()
        ]
        if not results:
            return True
        return all(results) if self.logic == 'all' else any(results)

    def __str__(self):
        return self.label
