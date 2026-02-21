"""
WebSocket routing configuration.
"""
from django.urls import path

# Import consumers
from apps.lobby.consumer import LobbyConsumer
from apps.game.consumers.game_consumer import GameConsumer

websocket_urlpatterns = [
    # Lobby WebSocket
    path('ws/lobby/room/<uuid:room_id>/', LobbyConsumer.as_asgi()),
    path('ws/lobby/<str:mode>/', LobbyConsumer.as_asgi()),
    
    # Game WebSocket
    path('ws/game/<uuid:game_id>/', GameConsumer.as_asgi()),
]

