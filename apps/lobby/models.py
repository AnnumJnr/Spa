"""
Lobby and matchmaking models.
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
import string
import random


def generate_room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


class GameRoom(models.Model):
    MODE_QUICK_MATCH = 'quick_match'
    MODE_MULTIPLAYER = 'multiplayer'
    MODE_PRIVATE = 'private'
    MODE_PRACTICE = 'practice'

    MODE_CHOICES = [
        (MODE_QUICK_MATCH, 'Quick Match (1v1)'),
        (MODE_MULTIPLAYER, 'Multiplayer Lobby'),
        (MODE_PRIVATE, 'Private Room'),
        (MODE_PRACTICE, 'Practice Mode'),
    ]

    STATUS_WAITING = 'waiting'
    STATUS_STARTING = 'starting'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_FINISHED = 'finished'

    STATUS_CHOICES = [
        (STATUS_WAITING, 'Waiting for Players'),
        (STATUS_STARTING, 'Starting Soon'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_FINISHED, 'Finished'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    room_code = models.CharField(max_length=6, unique=True, default=generate_room_code)
    target_score = models.IntegerField(default=12)
    max_players = models.IntegerField(default=4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_WAITING)

    # Host is nullable so guests can create rooms
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hosted_rooms'
    )

    game = models.OneToOneField(
        'game.Game',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='room'
    )

    countdown_started_at = models.DateTimeField(null=True, blank=True)
    countdown_duration = models.IntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'game_rooms'
        ordering = ['-created_at']

    def __str__(self):
        return f"Room {self.room_code} ({self.mode})"

    @property
    def current_player_count(self):
        return self.room_players.filter(status='active').count()

    @property
    def is_full(self):
        return self.current_player_count >= self.max_players

    @property
    def can_start(self):
        # Any room can start with 2+ active players (humans or bots)
        return self.current_player_count >= 2

    def start_countdown(self):
        self.countdown_started_at = timezone.now()
        self.status = self.STATUS_STARTING
        self.save()

    def is_countdown_expired(self):
        if not self.countdown_started_at:
            return False
        elapsed = (timezone.now() - self.countdown_started_at).total_seconds()
        return elapsed >= self.countdown_duration


class RoomPlayer(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_LEFT = 'left'
    STATUS_KICKED = 'kicked'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_LEFT, 'Left'),
        (STATUS_KICKED, 'Kicked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    room = models.ForeignKey(
        GameRoom,
        on_delete=models.CASCADE,
        related_name='room_players'
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='room_participations',
        null=True,
        blank=True
    )

    # Guest support
    guest_name = models.CharField(max_length=50, null=True, blank=True)

    # Host indicator (cosmetic only - anyone can start)
    is_host = models.BooleanField(default=False)

    # Bot indicator
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

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    is_ready = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'room_players'
        ordering = ['joined_at']
        # Removed unique_together - handled in service layer

    def __str__(self):
        return f"{self.display_name} in Room {self.room.room_code}"

    @property
    def display_name(self):
        if self.is_bot:
            return f"Bot ({self.bot_difficulty})"
        if self.guest_name:
            return self.guest_name
        if self.user:
            return self.user.display_name if self.user.display_name else self.user.username
        return 'Unknown'

    @property
    def is_guest(self):
        return self.user is None and not self.is_bot


class MatchmakingQueue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='matchmaking_entries'
    )

    mode = models.CharField(
        max_length=20,
        choices=[
            ('quick_match', 'Quick Match'),
            ('multiplayer', 'Multiplayer'),
        ]
    )
    target_score = models.IntegerField(default=12)
    is_matched = models.BooleanField(default=False)
    matched_room = models.ForeignKey(
        GameRoom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matched_from_queue'
    )
    joined_queue_at = models.DateTimeField(auto_now_add=True)
    matched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'matchmaking_queue'
        ordering = ['joined_queue_at']

    def __str__(self):
        return f"{self.user.username} in {self.mode} queue"
