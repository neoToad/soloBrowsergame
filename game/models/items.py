from django.db import models

class Item(models.Model):
    key          = models.SlugField(unique=True)
    name         = models.CharField(max_length=200)
    description  = models.TextField()
    is_consumable = models.BooleanField(default=False)

    EFFECT_TYPES = [
        ('heal_hp',  'Heal HP'),
        ('add_stat', 'Permanently increase a stat'),
    ]

    effect_type  = models.CharField(
                       max_length=20,
                       choices=EFFECT_TYPES,
                       blank=True,
                   )
    effect_stat  = models.CharField(max_length=20, blank=True)
    # Model field name to target for add_stat: strength, agility, intellect, charisma
    effect_value = models.IntegerField(default=0)

    equip_slot   = models.CharField(max_length=20, blank=True)
    # Slot identifier reserved for future equip logic: weapon, armor, accessory

    passive_stat  = models.CharField(max_length=20, blank=True)
    # Model field name to boost passively while carried: strength, agility, intellect, charisma
    passive_value = models.IntegerField(default=0)

    def __str__(self):
        return self.name
