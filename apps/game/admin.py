"""
Admin configuration for game models.
"""
from django.contrib import admin
from .models import Game, GamePlayer, Set, GameHistory


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ['id', 'status', 'target_score', 'is_practice', 'num_players', 'created_at']
    list_filter = ['status', 'is_practice', 'created_at']
    search_fields = ['id']
    readonly_fields = ['id', 'created_at', 'started_at', 'finished_at']


@admin.register(GamePlayer)
class GamePlayerAdmin(admin.ModelAdmin):
    list_display = ['id', 'game', 'user', 'is_bot', 'seat_position', 'score', 'is_active']
    list_filter = ['is_bot', 'is_active', 'bot_difficulty']
    search_fields = ['user__username', 'game__id']
    readonly_fields = ['id', 'joined_at']


@admin.register(Set)
class SetAdmin(admin.ModelAdmin):
    list_display = ['id', 'game', 'set_number', 'status', 'winner', 'score_awarded']
    list_filter = ['status', 'created_at']
    search_fields = ['game__id']
    readonly_fields = ['id', 'created_at', 'completed_at']


@admin.register(GameHistory)
class GameHistoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'game', 'winner', 'total_sets', 'duration_seconds', 'completed_at']
    list_filter = ['completed_at']
    search_fields = ['game__id', 'winner__username']
    readonly_fields = ['id', 'completed_at']