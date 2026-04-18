from django.db import models

class Property(models.Model):
    PROPERTY_TYPES = [
        ('safehouse', 'Safe House'),
        ('business',  'Business'),
        ('territory', 'Territory'),
    ]
    name             = models.CharField(max_length=200)
    property_type    = models.CharField(max_length=20, choices=PROPERTY_TYPES)
    income_per_turn  = models.IntegerField(default=0)
    heat_reduction   = models.IntegerField(default=0)
    rep_bonus        = models.IntegerField(default=0)
    is_contestable   = models.BooleanField(default=False)
    resolution_scene = models.ForeignKey(
        'game.Scene', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+'
    )

    def __str__(self):
        return self.name

class PlayerProperty(models.Model):
    session      = models.ForeignKey('game.GameSession', related_name='properties', on_delete=models.CASCADE)
    property     = models.ForeignKey(Property, on_delete=models.CASCADE)
    is_contested = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.session} — {self.property.name}"

class RivalClaim(models.Model):
    player_property  = models.ForeignKey(PlayerProperty, related_name='claims', on_delete=models.CASCADE)
    resolution_scene = models.ForeignKey(
        'game.Scene', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Claim on {self.player_property.property.name}"
