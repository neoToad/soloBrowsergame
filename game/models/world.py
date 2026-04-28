import re

from django.core.exceptions import ValidationError
from django.db import models
from .requirements import RequirementGroup
from .items import Item
from ..constants import STAT_DISPLAY_NAMES
from ..services.flag_registry import validate_flag_name

class Arc(models.Model):
    key   = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class Quest(models.Model):
    key         = models.SlugField(unique=True)
    title       = models.CharField(max_length=200)
    description = models.TextField()
    is_unlocked = models.BooleanField(default=True)
    # Convention: is_unlocked=False means "not yet authored / hidden from players".
    # It is a content visibility flag set by admins, NOT a player-facing requirement gate.
    # Player-facing gating (e.g. "requires level 3") belongs in the requirements M2M.
    arc         = models.ForeignKey(
                      'Arc',
                      null=True, blank=True,
                      on_delete=models.SET_NULL,
                      related_name='quests'
                  )
    arc_order       = models.IntegerField(default=0, null=True, blank=True,)
    entrance_scene  = models.ForeignKey(
                          'Scene',
                          null=True, blank=True,
                          on_delete=models.SET_NULL,
                          related_name='+'
                      )

    # Access requirements — all groups must pass to see or enter this quest
    requirements = models.ManyToManyField(
                       RequirementGroup,
                       blank=True,
                       related_name='gated_quests'
                   )

    hub_scenes = models.ManyToManyField(
        'Scene',
        blank=True,
        related_name='posted_quests',
        limit_choices_to={'scene_type': 'hub'},
        help_text="Hub scenes whose notice board lists this quest.",
    )

    is_repeatable = models.BooleanField(
        default=False,
        help_text="If True, this quest's entry choice re-appears after completion."
    )

    class Meta:
        ordering = ['arc_order']

    def __str__(self):
        return self.title


class Scene(models.Model):
    key      = models.SlugField(unique=True)
    SCENE_TYPES = [
        ('normal',  'Normal'),
        ('hub',     'Hub'),
        ('combat',  'Combat'),
        ('ending',  'Ending'),
    ]
    scene_type = models.CharField(
        max_length=20,
        choices=SCENE_TYPES,
        default='normal',
    )
    title    = models.CharField(max_length=200)
    body     = models.TextField()
    order    = models.IntegerField(default=0)

    requires_roll    = models.BooleanField(default=False)
    roll_stat        = models.CharField(
                           max_length=50, blank=True,
                           choices=[('', '---')] + [(v, v) for v in STAT_DISPLAY_NAMES.keys()]
                       )
    roll_difficulty  = models.IntegerField(default=10)

    ending_type = models.CharField(
                      max_length=20,
                      choices=[
                          ('victory', 'Victory'),
                          ('defeat',  'Defeat'),
                          ('neutral', 'Neutral'),
                      ],
                      blank=True
                  )

    ambient_sound = models.CharField(max_length=100, blank=True)
    # slug of a static audio file e.g. 'cave_drip', 'tavern_noise'

    consume_item = models.ForeignKey(
                       Item,
                       null=True, blank=True,
                       on_delete=models.SET_NULL,
                       related_name='consumed_by_scenes',
                       help_text="If set, this item is removed from inventory when the player arrives at this scene.",
                   )

    quest = models.ForeignKey(
        'Quest',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='scenes',
    )

    canvas_x = models.IntegerField(default=0)
    canvas_y = models.IntegerField(default=0)

    cash_change = models.IntegerField(default=0, help_text="Cash delta when arriving at this scene.")
    rep_change  = models.IntegerField(default=0, help_text="Reputation delta when arriving at this scene.")
    heat_change = models.IntegerField(default=0, help_text="Heat change when arriving at this scene (can be negative).")

    receive_property = models.ForeignKey(
        'game.Property',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Property awarded when arriving at this scene."
    )
    lose_property = models.ForeignKey(
        'game.Property',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Property lost when arriving at this scene."
    )

    @property
    def is_hub(self):
        return self.scene_type == 'hub'

    @property
    def is_combat(self):
        return self.scene_type == 'combat'

    @property
    def is_ending(self):
        return self.scene_type == 'ending'

    def clean(self):
        super().clean()
        if self.requires_roll and self.roll_stat not in STAT_DISPLAY_NAMES:
            raise ValidationError({'roll_stat': 'Must be a valid stat when requires_roll is True.'})
        if self.scene_type == 'ending' and not self.ending_type:
            raise ValidationError({'ending_type': 'Ending scenes must have a non-blank ending_type.'})
        if self.ending_type and self.scene_type != 'ending':
            raise ValidationError({'scene_type': 'Scenes with an ending_type must have scene_type "ending".'})
        if self.quest_id:
            expected_prefix = f"{self.quest.key}__"
            if not self.key.startswith(expected_prefix):
                raise ValidationError(
                    {'key': f'Scene key must start with "{expected_prefix}" when attached to this quest.'}
                )
            slug_part = self.key[len(expected_prefix):]
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug_part):
                raise ValidationError(
                    {'key': f'Scene key must match "{expected_prefix}{{scene-slug}}" using lowercase letters, numbers, and hyphens.'}
                )

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.key


class Choice(models.Model):
    scene        = models.ForeignKey(
                       Scene,
                       related_name='choices',
                       on_delete=models.CASCADE
                   )
    label        = models.CharField(max_length=300)
    order        = models.IntegerField(default=0)

    # Routing — used when no roll is required
    target_scene = models.ForeignKey(
                       Scene,
                       null=True, blank=True,
                       related_name='+',
                       on_delete=models.SET_NULL
                   )

    # Roll routing — used when the scene requires a roll
    success_scene = models.ForeignKey(
                        Scene,
                        null=True, blank=True,
                        related_name='+',
                        on_delete=models.SET_NULL
                    )
    failure_scene = models.ForeignKey(
                        Scene,
                        null=True, blank=True,
                        related_name='+',
                        on_delete=models.SET_NULL
                    )

    # Flavor logged to EventLog when this choice leads to its target
    arrival_flavor         = models.TextField(blank=True)
    failure_arrival_flavor = models.TextField(blank=True,
                                help_text="Logged instead of arrival_flavor when a roll fails.")

    set_flag_name   = models.CharField(max_length=100, blank=True,
                          help_text=(
                              "If set, this flag is set on the session when this choice is taken. "
                              "Use a registered key or supported dynamic pattern."
                          ))
    clear_flag_name = models.CharField(max_length=100, blank=True,
                          help_text=(
                              "If set, this flag is cleared from the session when this choice is taken. "
                              "Use a registered key or supported dynamic pattern."
                          ))

    # Visibility and access requirements
    requirements = models.ManyToManyField(
                       RequirementGroup,
                       blank=True,
                       related_name='gated_choices'
                   )

    class Meta:
        ordering = ['order']

    def clean(self):
        super().clean()
        legacy_fields = {}
        if self.pk:
            legacy_fields = (
                Choice.objects.filter(pk=self.pk)
                .values("set_flag_name", "clear_flag_name")
                .first()
                or {}
            )

        set_legacy = (legacy_fields.get("set_flag_name", "").strip(),)
        clear_legacy = (legacy_fields.get("clear_flag_name", "").strip(),)
        errors = {}
        try:
            self.set_flag_name = validate_flag_name(
                self.set_flag_name,
                field_label="set_flag_name",
                legacy_values=[v for v in set_legacy if v],
            )
        except ValidationError as exc:
            errors["set_flag_name"] = exc.messages
        try:
            self.clear_flag_name = validate_flag_name(
                self.clear_flag_name,
                field_label="clear_flag_name",
                legacy_values=[v for v in clear_legacy if v],
            )
        except ValidationError as exc:
            errors["clear_flag_name"] = exc.messages
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.scene.key} -> {self.label}"


class SceneItem(models.Model):
    scene      = models.ForeignKey(
        Scene,
        related_name='scene_items',
        on_delete=models.CASCADE
    )
    item       = models.ForeignKey(
        Item,
        related_name='found_in',
        on_delete=models.CASCADE
    )
    quantity   = models.IntegerField(default=1)
    award_once = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.item.name} x{self.quantity} in {self.scene.key}"


class Gang(models.Model):
    key         = models.SlugField(unique=True)
    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Contact(models.Model):
    key         = models.SlugField(unique=True)
    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class SceneContact(models.Model):
    ACTION_CHOICES = [
        ('gain', 'Gain'),
        ('lose', 'Lose'),
    ]

    scene      = models.ForeignKey(
        Scene,
        related_name='scene_contacts',
        on_delete=models.CASCADE
    )
    contact    = models.ForeignKey(
        Contact,
        related_name='found_in',
        on_delete=models.CASCADE
    )
    action     = models.CharField(max_length=10, choices=ACTION_CHOICES, default='gain')
    award_once = models.BooleanField(
        default=True,
        help_text="If True, gaining this contact is skipped when the player already has it."
    )

    def __str__(self):
        return f"{self.action} {self.contact.name} in {self.scene.key}"
