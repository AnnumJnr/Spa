"""
URL routing for game API.
"""
from django.urls import path
from . import views

app_name = 'game'

urlpatterns = [
    # Game state
    path('<uuid:game_id>/state/', views.game_state_view, name='game_state'),
    
    # Card actions
    path('<uuid:game_id>/play-card/', views.play_card_view, name='play_card'),
    path('<uuid:game_id>/stack/', views.stack_view, name='stack'),
]