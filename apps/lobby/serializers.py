"""
Serializers for lobby models.
"""
from rest_framework import serializers
from .models import GameRoom, RoomPlayer


class RoomPlayerSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='display_name', read_only=True)
    
    class Meta:
        model = RoomPlayer
        fields = [
            'id',
            'user',
            'display_name',
            'is_bot',
            'bot_difficulty',
            'status',
            'is_ready',
            'joined_at'
        ]


class GameRoomSerializer(serializers.ModelSerializer):
    players = RoomPlayerSerializer(source='room_players', many=True, read_only=True)
    current_player_count = serializers.IntegerField(read_only=True)
    can_start = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = GameRoom
        fields = [
            'id',
            'mode',
            'room_code',
            'target_score',
            'max_players',
            'status',
            'host',
            'players',
            'current_player_count',
            'can_start',
            'countdown_started_at',
            'countdown_duration',
            'created_at'
        ]