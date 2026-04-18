from django.db import models
from .requirements import RequirementGroup
from .items import Item

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
    arc_order       = models.IntegerField(default=0)
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
    quest    = models.ForeignKey(
                   Quest,
                   null=True, blank=True,
                   on_delete=models.SET_NULL,
                   related_name='scenes'
               )
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
    roll_stat        = models.CharField(max_length=50, blank=True)
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

    canvas_x = models.IntegerField(default=0)
    canvas_y = models.IntegerField(default=0)

    @property
    def is_hub(self):
        return self.scene_type == 'hub'

    @property
    def is_combat(self):
        return self.scene_type == 'combat'

    @property
    def is_ending(self):
        return self.scene_type == 'ending'

    class Meta:
        ordering = ['quest', 'order']

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
    arrival_flavor = models.TextField(blank=True)

    # Item consumption — separate from gating, this is an action on take
    consume_item = models.ForeignKey(
                       Item,
                       null=True, blank=True,
                       on_delete=models.SET_NULL,
                       related_name='consumed_by_choices'
                   )
    # If set, this item is removed from inventory when the choice is taken

    set_flag_name   = models.CharField(max_length=100, blank=True,
                          help_text="If set, this flag is set on the session when this choice is taken.")
    clear_flag_name = models.CharField(max_length=100, blank=True,
                          help_text="If set, this flag is cleared from the session when this choice is taken.")

    # Visibility and access requirements
    requirements = models.ManyToManyField(
                       RequirementGroup,
                       blank=True,
                       related_name='gated_choices'
                   )

    # If set, this choice starts the linked quest; hidden once quest is completed
    # (unless Quest.is_repeatable is True)
    quest = models.ForeignKey(
                'Quest',
                null=True, blank=True,
                on_delete=models.SET_NULL,
                related_name='entry_choices',
                help_text="If set, this choice starts the linked quest and is hidden "
                          "once the quest is completed (unless the quest is repeatable)."
            )

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.scene.key} → {self.label}"

    def resolve_target(self, roll_succeeded: bool | None = None):
        """
        Return the Scene this choice routes to.
        Pass roll_succeeded=True/False when the parent scene requires a roll.
        Pass roll_succeeded=None (default) for non-roll scenes.
        """
        if self.scene.requires_roll:
            if roll_succeeded is None:
                raise ValueError(
                    f"Choice {self.pk} belongs to a roll scene but "
                    "roll_succeeded was not provided."
                )
            return self.success_scene if roll_succeeded else self.failure_scene
        return self.target_scene


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


class SceneUnlock(models.Model):
    from_scene = models.ForeignKey(
        Scene,
        related_name='unlocks',
        on_delete=models.CASCADE
    )
    unlocks_scene = models.ForeignKey(
        Scene,
        related_name='unlocked_by',
        on_delete=models.CASCADE
    )
    requires_choice = models.ForeignKey(
        'Choice',
        null=True,
        blank=True,
        related_name='triggers_unlocks',
        on_delete=models.SET_NULL
    )
    requires_item = models.ForeignKey(
        Item,
        null=True,
        blank=True,
        related_name='+',
        on_delete=models.SET_NULL
    )

    def __str__(self):
        return f"{self.from_scene} -> {self.unlocks_scene}"
