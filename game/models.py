from django.db import models

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
    arc         = models.ForeignKey(
                      Arc,
                      null=True, blank=True,
                      on_delete=models.SET_NULL,
                      related_name='quests'
                  )
    arc_order       = models.IntegerField(default=0)
    # Stat gate
    required_stat    = models.CharField(max_length=50, blank=True)
    required_minimum = models.IntegerField(default=0)

    # Quest prerequisite gate
    required_quest = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='unlocks'
    )

    entrance_scene  = models.ForeignKey(
                          'Scene',
                          null=True, blank=True,
                          on_delete=models.SET_NULL,
                          related_name='+'
                      )

    class Meta:
        ordering = ['arc_order']

    def __str__(self):
        return self.title


class Item(models.Model):
    key          = models.SlugField(unique=True)
    name         = models.CharField(max_length=200)
    description  = models.TextField()
    is_consumable = models.BooleanField(default=False)

    def __str__(self):
        return self.name


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
    ]

    condition_type = models.CharField(max_length=50, choices=CONDITION_TYPES)

    # Stat conditions
    stat_name  = models.CharField(max_length=50, blank=True)
    stat_value = models.IntegerField(default=0)

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

    def evaluate(self, stats, inventory, completed_map):
        """
        Returns True if this condition is met.
          stats         — PlayerStats instance
          inventory     — dict of {item_id: PlayerInventory instance}
          completed_map — dict of {quest_id: ending_type string}
        """
        ct = self.condition_type

        if ct == 'stat_gte':
            return getattr(stats, self.stat_name, 0) >= self.stat_value
        if ct == 'stat_lte':
            return getattr(stats, self.stat_name, 0) <= self.stat_value
        if ct == 'has_item':
            return self.required_item_id in inventory
        if ct == 'missing_item':
            return self.required_item_id not in inventory
        if ct == 'quest_completed':
            return self.required_quest_id in completed_map
        if ct == 'quest_not_done':
            return self.required_quest_id not in completed_map
        if ct == 'quest_ending':
            return completed_map.get(self.required_quest_id) == \
                   self.required_ending_type
        if ct == 'level_gte':
            return stats.level >= self.stat_value
        if ct == 'xp_gte':
            return stats.experience >= self.stat_value

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

    def evaluate(self, stats, inventory, completed_map):
        results = [
            r.evaluate(stats, inventory, completed_map)
            for r in self.requirements.all()
        ]
        if not results:
            return True
        return all(results) if self.logic == 'all' else any(results)

    def __str__(self):
        return self.label


class Scene(models.Model):
    key      = models.SlugField(unique=True)
    quest    = models.ForeignKey(
                   Quest,
                   null=True, blank=True,
                   on_delete=models.SET_NULL,
                   related_name='scenes'
               )
    is_hub   = models.BooleanField(default=False)
    is_combat = models.BooleanField(default=False)
    is_ending = models.BooleanField(default=False)
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

    # Access requirements — all groups must pass to enter this scene
    requirements = models.ManyToManyField(
                       RequirementGroup,
                       blank=True,
                       related_name='gated_scenes'
                   )

    ambient_sound = models.CharField(max_length=100, blank=True)
    # slug of a static audio file e.g. 'cave_drip', 'tavern_noise'

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
                       related_name='+',
                       on_delete=models.CASCADE
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

    # Visibility and access requirements
    requirements = models.ManyToManyField(
                       RequirementGroup,
                       blank=True,
                       related_name='gated_choices'
                   )

    # Simplified gating for Prompt 4/5
    required_stat = models.CharField(max_length=50, blank=True)
    required_minimum = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.scene.key} → {self.label}"


class GameSession(models.Model):
    session_key   = models.CharField(max_length=100, unique=True)
    current_scene = models.ForeignKey(
                        Scene,
                        on_delete=models.SET_NULL,
                        null=True
                    )
    created_at    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.session_key


class PlayerStats(models.Model):
    session   = models.OneToOneField(
                    GameSession,
                    related_name='stats',
                    on_delete=models.CASCADE
                )
    strength  = models.IntegerField(default=5)
    agility   = models.IntegerField(default=5)
    intellect = models.IntegerField(default=5)
    charisma  = models.IntegerField(default=5)
    hp        = models.IntegerField(default=20)
    max_hp    = models.IntegerField(default=20)
    level       = models.IntegerField(default=1)
    experience  = models.IntegerField(default=0)
    stat_points = models.IntegerField(default=0)

    def __str__(self):
        return f"Stats for {self.session}"


class PlayerInventory(models.Model):
    session     = models.ForeignKey(
                      GameSession,
                      related_name='inventory',
                      on_delete=models.CASCADE
                  )
    item        = models.ForeignKey(
                      Item,
                      related_name='held_by',
                      on_delete=models.CASCADE
                  )
    quantity    = models.IntegerField(default=1)
    acquired_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('session', 'item')
        ordering        = ['acquired_at']

    def __str__(self):
        return f"{self.session} — {self.item.name} x{self.quantity}"


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


class CompletedQuest(models.Model):
    session      = models.ForeignKey(
                       GameSession,
                       related_name='completed_quests',
                       on_delete=models.CASCADE
                   )
    quest        = models.ForeignKey(
                       Quest,
                       on_delete=models.CASCADE
                   )
    ending_type  = models.CharField(max_length=20)
    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.session} — {self.quest.title} ({self.ending_type})"


class Enemy(models.Model):
    key              = models.SlugField(unique=True)
    name             = models.CharField(max_length=200)
    description      = models.TextField()
    max_hp           = models.IntegerField(default=10)
    attack_modifier  = models.IntegerField(default=0)
    defense          = models.IntegerField(default=8)
    damage_min       = models.IntegerField(default=1)
    damage_max       = models.IntegerField(default=4)
    victory_scene    = models.ForeignKey(
                           Scene,
                           null=True, blank=True,
                           related_name='+',
                           on_delete=models.SET_NULL
                       )
    defeat_scene     = models.ForeignKey(
                           Scene,
                           null=True, blank=True,
                           related_name='+',
                           on_delete=models.SET_NULL
                       )

    def __str__(self):
        return self.name


class CombatEncounter(models.Model):
    scene  = models.OneToOneField(
                 Scene,
                 related_name='combat_encounter',
                 on_delete=models.CASCADE
             )
    enemy  = models.ForeignKey(
                 Enemy,
                 related_name='encounters',
                 on_delete=models.CASCADE
             )

    def __str__(self):
        return f"{self.scene.key} vs {self.enemy.name}"


class CombatState(models.Model):
    session      = models.OneToOneField(
                       GameSession,
                       related_name='combat_state',
                       on_delete=models.CASCADE
                   )
    enemy        = models.ForeignKey(Enemy, on_delete=models.CASCADE)
    enemy_hp     = models.IntegerField()
    turn_number  = models.IntegerField(default=1)
    is_active    = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.session} vs {self.enemy.name} (turn {self.turn_number})"


class EventLog(models.Model):
    session   = models.ForeignKey(
                    GameSession,
                    related_name='log',
                    on_delete=models.CASCADE
                )
    timestamp = models.DateTimeField(auto_now_add=True)
    text      = models.TextField()

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.session} — {self.text[:50]}"
