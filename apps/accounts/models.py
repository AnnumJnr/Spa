"""
User and profile models for Spa Game.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid


class User(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    
    # Profile fields
    display_name = models.CharField(max_length=50, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Online status
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.username
    
    @property
    def name(self):
        """Return display name or username."""
        return self.display_name or self.username


class PlayerProfile(models.Model):
    """
    Extended profile for game-related statistics and preferences.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Game preferences
    preferred_difficulty = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('expert', 'Expert'),
        ],
        default='intermediate'
    )
    
    # Settings
    sound_enabled = models.BooleanField(default=True)
    animations_enabled = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'player_profiles'
    
    def __str__(self):
        return f"Profile: {self.user.username}"