"""
Set model - represents one set within a game (5 rounds).
"""
import uuid
from django.db import models
from apps.game.engine.constants import SetStatus


class Set(models.Model):
    """
    Represents a single set within a game.
    A set consists of 5 internal rounds.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    game = models.ForeignKey(
        'Game',
        on_delete=models.CASCADE,
        related_name='sets'
    )
    
    # Set number (1, 2, 3, ...)
    set_number = models.IntegerField()
    
    # Set state
    status = models.CharField(
        max_length=20,
        choices=[
            (SetStatus.ACTIVE, 'Active'),
            (SetStatus.ENDED, 'Ended'),
        ],
        default=SetStatus.ACTIVE
    )
    
    # Current round index (0-4)
    current_round_index = models.IntegerField(default=0)
    
    # Lead player for this set
    lead_player = models.ForeignKey(
        'GamePlayer',
        on_delete=models.SET_NULL,
        null=True,
        related_name='led_sets'
    )
    
    # Player hands (JSON: {player_id: [cards]})
    hands = models.JSONField(default=dict)
    
    # Active players in this set (JSON array of player IDs)
    active_players = models.JSONField(default=list)
    
    # Round history (JSON array of round states)
    rounds = models.JSONField(default=list)
    
    # Stack state (JSON or null)
    stack_state = models.JSONField(null=True, blank=True)
    
    # Players who have used stack this set (JSON array)
    stack_used_by = models.JSONField(default=list)
    
    # Winner of this set
    winner = models.ForeignKey(
        'GamePlayer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_sets'
    )
    
    # Score awarded
    score_awarded = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'sets'
        ordering = ['set_number']
        unique_together = [['game', 'set_number']]
    
    def __str__(self):
        return f"Set {self.set_number} of Game {self.game.id}"