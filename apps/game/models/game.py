"""
Core game models.
"""
import uuid
from django.db import models
from django.conf import settings
from apps.game.engine.constants import GameStatus, GameConfig


class Game(models.Model):
    """
    Represents a single game instance.
    A game consists of multiple sets until a player reaches target score.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Game configuration
    target_score = models.IntegerField(default=GameConfig.DEFAULT_TARGET_SCORE)
    is_practice = models.BooleanField(default=False)  # Practice mode vs competitive
    
    # Game state
    status = models.CharField(
        max_length=20,
        choices=[
            (GameStatus.WAITING, 'Waiting'),
            (GameStatus.ACTIVE, 'Active'),
            (GameStatus.FINISHED, 'Finished'),
        ],
        default=GameStatus.WAITING
    )
    
    # Current lead player (hidden from clients except the lead)
    current_lead = models.ForeignKey(
        'GamePlayer',
        on_delete=models.SET_NULL,
        null=True,
        related_name='leading_games'
    )
    
    # Turn order (JSON array of player IDs)
    turn_order = models.JSONField(default=list)
    
    # Deck state (serialized)
    deck_state = models.JSONField(default=dict)
    
    # Winner
    winner = models.ForeignKey(
        'GamePlayer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_games'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'games'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Game {self.id} ({self.status})"
    
    @property
    def num_players(self):
        return self.players.count()
    
    @property
    def current_set(self):
        """Get the active set for this game."""
        return self.sets.filter(status='active').first()


class GamePlayer(models.Model):
    """
    Represents a player in a specific game.
    Links User to Game with game-specific data.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='players'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='game_participations',
        null=True,
        blank=True  # Null for bot players
    )


    # Guest player identifier (for non-authenticated players)
    guest_name = models.CharField(max_length=50, null=True, blank=True)
    is_guest = models.BooleanField(default=False)
    
    # Bot player indicator
    is_bot = models.BooleanField(default=False)
    bot_difficulty = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('expert', 'Expert'),
        ]
    )
    
    # Game-specific player data
    seat_position = models.IntegerField()  # 0, 1, 2, 3 (clockwise)
    score = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)  # False if fouled out
    
    # Connection state
    is_connected = models.BooleanField(default=True)
    last_action_at = models.DateTimeField(auto_now=True)
    
    # Timestamps
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'game_players'
        ordering = ['seat_position']
        unique_together = [['game', 'seat_position']]
    
    def __str__(self):
        name = self.user.username if self.user else f"Bot ({self.bot_difficulty})"
        return f"{name} in Game {self.game.id}"
    
    @property
    def player_id(self):
        """Convenience property for engine compatibility."""
        return self.id
    
    @property
    def display_name(self):
   
        """Get display name for this player."""
        if self.is_bot:
            return f"Bot ({self.bot_difficulty})"
        if self.is_guest and self.guest_name:
            return self.guest_name
        if self.user:
            return self.user.display_name if hasattr(self.user, 'display_name') and self.user.display_name else self.user.username
        return f"Guest_{str(self.id)[:8]}"