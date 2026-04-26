from dataclasses import dataclass
from typing import Callable, ClassVar

from django.db import models
from django.db.models import Q

from .items import Item


@dataclass
class PlayerContext:
    stats: object  # PlayerStats instance
    inventory: dict  # {item_id: PlayerInventory instance}
    completed_map: dict  # {quest_id: ending_type string}
    flags: dict = None
    contacts: dict = None  # {contact_id: PlayerContact instance}

    def __post_init__(self):
        if self.flags is None:
            self.flags = {}
        if self.contacts is None:
            self.contacts = {}


class Requirement(models.Model):
    """
    A single evaluatable condition. Requirements are grouped by
    RequirementGroup which controls AND/OR logic between them.
    """

    CONDITION_TYPES = [
        ("stat_gte", "Stat >= value"),
        ("stat_lte", "Stat <= value"),
        ("has_item", "Has item in inventory"),
        ("missing_item", "Does not have item"),
        ("quest_completed", "Quest completed"),
        ("quest_not_done", "Quest not completed"),
        ("quest_ending", "Quest completed with specific ending"),
        ("level_gte", "Player level >= value"),
        ("xp_gte", "Player XP >= value"),
        ("has_flag", "Flag is set"),
        ("missing_flag", "Flag is not set"),
        ("has_contact", "Has contact"),
        ("missing_contact", "Does not have contact"),
    ]

    condition_type = models.CharField(max_length=50, choices=CONDITION_TYPES)

    # Flag conditions
    flag_name = models.CharField(max_length=100, blank=True)

    # Stat conditions
    stat_name = models.CharField(max_length=50, blank=True)
    stat_value = models.IntegerField(default=0, blank=True)

    # Item conditions
    required_item = models.ForeignKey(
        Item,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    # Quest conditions
    required_quest = models.ForeignKey(
        "Quest",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    required_ending_type = models.CharField(max_length=20, blank=True)

    # Contact conditions
    required_contact = models.ForeignKey(
        "Contact",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    EVALUATORS: ClassVar[dict[str, Callable[["Requirement", PlayerContext], bool]]] = {}

    @classmethod
    def register_evaluator(cls, condition_type: str):
        def _decorator(func):
            cls.EVALUATORS[condition_type] = func
            return func

        return _decorator

    def evaluate(self, ctx: PlayerContext):
        """
        Returns True if this condition is met.
          ctx - PlayerContext instance (stats, inventory, completed_map)
        """
        evaluator = self.EVALUATORS.get(self.condition_type)
        if evaluator is None:
            return False
        return evaluator(self, ctx)

    def __str__(self):
        return (
            f"{self.get_condition_type_display()} - "
            f"{self.stat_name or self.required_item or self.required_quest or ''}"
        )


class RequirementGroup(models.Model):
    """
    A named group of Requirements with internal AND or OR logic.
    Multiple groups on a Scene or Choice are always ANDed together:
    every group must pass. The OR/AND logic is internal to each group.

    Example: "Has key OR high agility, AND must have completed the mine"
      Group 1 (logic: any): has_item rusty_key | stat_gte agility 8
      Group 2 (logic: all): quest_completed the_haunted_mine
    Both groups must pass. Within group 1, either condition is enough.
    """

    LOGIC_CHOICES = [
        ("all", "All must pass (AND)"),
        ("any", "Any one must pass (OR)"),
    ]

    label = models.CharField(max_length=200)
    logic = models.CharField(max_length=10, choices=LOGIC_CHOICES, default="all")
    scope_type = models.CharField(max_length=50, null=True, blank=True)
    scope_key = models.CharField(max_length=255, null=True, blank=True)
    group_key = models.CharField(max_length=255, null=True, blank=True)
    requirements = models.ManyToManyField(Requirement, related_name="groups")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scope_type", "scope_key", "group_key"],
                condition=Q(scope_type__isnull=False) & Q(scope_key__isnull=False) & Q(group_key__isnull=False),
                name="uq_requirement_group_scoped_identity",
            )
        ]

    def evaluate(self, ctx: PlayerContext):
        results = [r.evaluate(ctx) for r in self.requirements.all()]
        if not results:
            return True
        return all(results) if self.logic == "all" else any(results)

    def __str__(self):
        return self.label


@Requirement.register_evaluator("stat_gte")
def _eval_stat_gte(requirement: Requirement, ctx: PlayerContext) -> bool:
    return getattr(ctx.stats, requirement.stat_name, 0) >= requirement.stat_value


@Requirement.register_evaluator("stat_lte")
def _eval_stat_lte(requirement: Requirement, ctx: PlayerContext) -> bool:
    return getattr(ctx.stats, requirement.stat_name, 0) <= requirement.stat_value


@Requirement.register_evaluator("has_item")
def _eval_has_item(requirement: Requirement, ctx: PlayerContext) -> bool:
    return requirement.required_item_id in ctx.inventory


@Requirement.register_evaluator("missing_item")
def _eval_missing_item(requirement: Requirement, ctx: PlayerContext) -> bool:
    return requirement.required_item_id not in ctx.inventory


@Requirement.register_evaluator("quest_completed")
def _eval_quest_completed(requirement: Requirement, ctx: PlayerContext) -> bool:
    return requirement.required_quest_id in ctx.completed_map


@Requirement.register_evaluator("quest_not_done")
def _eval_quest_not_done(requirement: Requirement, ctx: PlayerContext) -> bool:
    return requirement.required_quest_id not in ctx.completed_map


@Requirement.register_evaluator("quest_ending")
def _eval_quest_ending(requirement: Requirement, ctx: PlayerContext) -> bool:
    return ctx.completed_map.get(requirement.required_quest_id) == requirement.required_ending_type


@Requirement.register_evaluator("level_gte")
def _eval_level_gte(requirement: Requirement, ctx: PlayerContext) -> bool:
    return ctx.stats.level >= requirement.stat_value


@Requirement.register_evaluator("xp_gte")
def _eval_xp_gte(requirement: Requirement, ctx: PlayerContext) -> bool:
    return ctx.stats.experience >= requirement.stat_value


@Requirement.register_evaluator("has_flag")
def _eval_has_flag(requirement: Requirement, ctx: PlayerContext) -> bool:
    return bool(ctx.flags.get(requirement.flag_name))


@Requirement.register_evaluator("missing_flag")
def _eval_missing_flag(requirement: Requirement, ctx: PlayerContext) -> bool:
    return not ctx.flags.get(requirement.flag_name)


@Requirement.register_evaluator("has_contact")
def _eval_has_contact(requirement: Requirement, ctx: PlayerContext) -> bool:
    return requirement.required_contact_id in ctx.contacts


@Requirement.register_evaluator("missing_contact")
def _eval_missing_contact(requirement: Requirement, ctx: PlayerContext) -> bool:
    return requirement.required_contact_id not in ctx.contacts
