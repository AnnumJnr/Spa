"""
Admin configuration for bot models.
"""
from django.contrib import admin
from .models import BotProfile


@admin.register(BotProfile)
class BotProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'difficulty', 'aggression_level', 'risk_tolerance', 'games_played', 'games_won']
    list_filter = ['difficulty']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at']