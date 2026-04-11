from django.db import models
from .player import GameSession

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
