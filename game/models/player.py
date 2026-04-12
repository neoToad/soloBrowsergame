from django.db import models
from .world import Scene, Quest
from .items import Item

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


class PlayerSceneState(models.Model):
    session = models.ForeignKey(
        GameSession,
        related_name='scene_states',
        on_delete=models.CASCADE
    )
    scene = models.ForeignKey(
        Scene,
        related_name='player_states',
        on_delete=models.CASCADE
    )
    STATE_CHOICES = [
        ('locked', 'Locked'),
        ('available', 'Available'),
        ('completed', 'Completed'),
    ]
    state = models.CharField(
        max_length=20,
        choices=STATE_CHOICES,
        default='available'
    )

    class Meta:
        unique_together = ('session', 'scene')

    def __str__(self):
        return f"{self.session} — {self.scene.title} ({self.state})"
