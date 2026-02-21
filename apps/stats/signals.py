"""
Signal handlers for stats models.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import CompetitiveStats, PracticeStats


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_stats(sender, instance, created, **kwargs):
    """Create stats entries when a new user is created."""
    if created:
        CompetitiveStats.objects.create(user=instance)
        PracticeStats.objects.create(user=instance)