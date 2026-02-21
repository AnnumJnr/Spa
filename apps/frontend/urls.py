"""
URL routing for frontend views.
"""
from django.urls import path
from . import views

app_name = 'frontend'

urlpatterns = [
    # Home
    path('', views.home_view, name='home'),
    
    # Auth pages
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    
    # Game modes
    path('modes/', views.game_modes_view, name='game_modes'),
    path('quick-match/', views.quick_match_view, name='quick_match'),
    path('multiplayer/', views.multiplayer_lobby_view, name='multiplayer'),
    path('create-room/', views.create_room_view, name='create_room'),
    path('join/<str:room_code>/', views.join_room_view, name='join_room'),
    path('practice/', views.practice_setup_view, name='practice'),
    
    # Game
    path('game/<uuid:game_id>/', views.game_table_view, name='game_table'),
    
    # Stats
    path('stats/', views.stats_dashboard_view, name='stats'),
]