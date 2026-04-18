from django.db import models
from .world import Scene
from .player import GameSession

class Enemy(models.Model):
    key              = models.SlugField(unique=True)
    name             = models.CharField(max_length=200)
    description      = models.TextField()
    max_hp           = models.IntegerField(default=10)
    attack_modifier  = models.IntegerField(default=0)
    defense          = models.IntegerField(default=8)
    damage_min       = models.IntegerField(default=1)
    damage_max       = models.IntegerField(default=4)
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
    victory_scene = models.ForeignKey(
                        Scene,
                        null=True, blank=True,
                        related_name='+',
                        on_delete=models.SET_NULL,
                    )
    defeat_scene  = models.ForeignKey(
                        Scene,
                        null=True, blank=True,
                        related_name='+',
                        on_delete=models.SET_NULL,
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
