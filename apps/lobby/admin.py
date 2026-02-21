"""
Admin configuration for lobby models.
"""
from django.contrib import admin
from .models import GameRoom, RoomPlayer, MatchmakingQueue


@admin.register(GameRoom)
class GameRoomAdmin(admin.ModelAdmin):
    list_display = ['room_code', 'mode', 'status', 'host', 'current_player_count', 'max_players', 'created_at']
    list_filter = ['mode', 'status', 'created_at']
    search_fields = ['room_code', 'host__username']
    readonly_fields = ['id', 'room_code', 'created_at', 'started_at', 'finished_at']


@admin.register(RoomPlayer)
class RoomPlayerAdmin(admin.ModelAdmin):
    list_display = ['id', 'room', 'user', 'is_bot', 'status', 'is_ready', 'joined_at']
    list_filter = ['status', 'is_bot', 'is_ready']
    search_fields = ['user__username', 'room__room_code']
    readonly_fields = ['id', 'joined_at', 'left_at']


@admin.register(MatchmakingQueue)
class MatchmakingQueueAdmin(admin.ModelAdmin):
    list_display = ['user', 'mode', 'target_score', 'is_matched', 'joined_queue_at']
    list_filter = ['mode', 'is_matched', 'joined_queue_at']
    search_fields = ['user__username']
    readonly_fields = ['id', 'joined_queue_at', 'matched_at']