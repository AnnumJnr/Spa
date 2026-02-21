"""
Player statistics models.
"""
import uuid
from django.db import models
from django.conf import settings


class CompetitiveStats(models.Model):
    """
    Competitive game statistics (non-practice games).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='competitive_stats'
    )
    
    # Game counts
    total_games = models.IntegerField(default=0)
    games_won = models.IntegerField(default=0)
    games_lost = models.IntegerField(default=0)
    
    # Set statistics
    total_sets_won = models.IntegerField(default=0)
    total_sets_lost = models.IntegerField(default=0)
    
    # Scoring
    total_points_scored = models.IntegerField(default=0)
    highest_score_in_game = models.IntegerField(default=0)
    
    # Bonus statistics
    six_bonuses_earned = models.IntegerField(default=0)
    seven_bonuses_earned = models.IntegerField(default=0)
    steal_bonuses_earned = models.IntegerField(default=0)
    
    # Fouls
    total_fouls = models.IntegerField(default=0)
    
    # Streaks
    current_win_streak = models.IntegerField(default=0)
    best_win_streak = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'competitive_stats'
        verbose_name_plural = 'Competitive stats'
    
    def __str__(self):
        return f"Stats for {self.user.username}"
    
    @property
    def win_rate(self):
        """Calculate win rate percentage."""
        if self.total_games == 0:
            return 0.0
        return (self.games_won / self.total_games) * 100


class PracticeStats(models.Model):
    """
    Practice mode statistics (separate from competitive).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='practice_stats'
    )
    
    # Game counts
    total_games = models.IntegerField(default=0)
    games_won = models.IntegerField(default=0)
    
    # Performance by bot difficulty
    wins_vs_beginner = models.IntegerField(default=0)
    wins_vs_intermediate = models.IntegerField(default=0)
    wins_vs_advanced = models.IntegerField(default=0)
    wins_vs_expert = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'practice_stats'
        verbose_name_plural = 'Practice stats'
    
    def __str__(self):
        return f"Practice stats for {self.user.username}"