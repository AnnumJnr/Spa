"""
Game history and statistics models.
"""
import uuid
from django.db import models
from django.conf import settings


class GameHistory(models.Model):
    """
    Record of completed games (competitive only).
    Used for player statistics and leaderboards.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    game = models.OneToOneField(
        'Game',
        on_delete=models.CASCADE,
        related_name='history'
    )
    
    # Winner
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='won_games_history'
    )
    
    # Participants (JSON array of user IDs)
    participants = models.JSONField(default=list)
    
    # Final scores (JSON: {user_id: score})
    final_scores = models.JSONField(default=dict)
    
    # Game statistics
    total_sets = models.IntegerField(default=0)
    total_rounds = models.IntegerField(default=0)
    total_fouls = models.IntegerField(default=0)
    
    # Duration
    duration_seconds = models.IntegerField(null=True, blank=True)
    
    # Timestamps
    completed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'game_history'
        ordering = ['-completed_at']
        verbose_name_plural = 'Game histories'
    
    def __str__(self):
        return f"History for Game {self.game.id}"