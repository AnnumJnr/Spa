"""
Bot player models.
"""
import uuid
from django.db import models
import random


class BotProfile(models.Model):
    """
    Represents a bot player with personality and difficulty.
    """
    DIFFICULTY_BEGINNER = 'beginner'
    DIFFICULTY_INTERMEDIATE = 'intermediate'
    DIFFICULTY_ADVANCED = 'advanced'
    DIFFICULTY_EXPERT = 'expert'
    
    DIFFICULTY_CHOICES = [
        (DIFFICULTY_BEGINNER, 'Beginner'),
        (DIFFICULTY_INTERMEDIATE, 'Intermediate'),
        (DIFFICULTY_ADVANCED, 'Advanced'),
        (DIFFICULTY_EXPERT, 'Expert'),
    ]
    
    # Bot names pool
    BOT_NAMES = [
        'Kwame', 'Kofi', 'Yaw', 'Akwasi', 'Kwabena',  # Male day names
        'Akua', 'Adwoa', 'Abenaa', 'Akosua', 'Ama',  # Female day names
        'Nana', 'Kojo', 'Esi', 'Adjoa', 'Efua',
        'Kobby', 'Abena', 'Kweku', 'Ekua', 'Fiifi'
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    name = models.CharField(max_length=50)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES)
    
    # Bot personality traits (for future enhancement)
    aggression_level = models.IntegerField(default=5)  # 1-10
    risk_tolerance = models.IntegerField(default=5)    # 1-10
    
    # Statistics (optional)
    games_played = models.IntegerField(default=0)
    games_won = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'bot_profiles'
    
    def __str__(self):
        return f"{self.name} ({self.difficulty})"
    
    @classmethod
    def get_or_create_bot(cls, difficulty):
        """Get or create a bot for the specified difficulty."""
        # Try to find an existing bot
        bot = cls.objects.filter(difficulty=difficulty).first()
        
        if not bot:
            # Create new bot
            name = random.choice(cls.BOT_NAMES)
            bot = cls.objects.create(
                name=name,
                difficulty=difficulty,
                aggression_level=cls._get_aggression_for_difficulty(difficulty),
                risk_tolerance=cls._get_risk_for_difficulty(difficulty)
            )
        
        return bot
    
    @staticmethod
    def _get_aggression_for_difficulty(difficulty):
        """Get aggression level based on difficulty."""
        mapping = {
            'beginner': 3,
            'intermediate': 5,
            'advanced': 7,
            'expert': 9,
        }
        return mapping.get(difficulty, 5)
    
    @staticmethod
    def _get_risk_for_difficulty(difficulty):
        """Get risk tolerance based on difficulty."""
        mapping = {
            'beginner': 2,
            'intermediate': 5,
            'advanced': 7,
            'expert': 8,
        }
        return mapping.get(difficulty, 5)