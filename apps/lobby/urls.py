"""
URL routing for lobby API.
"""
from django.urls import path
from . import views

app_name = 'lobby'

urlpatterns = [
    # Room management
    path('rooms/create/', views.create_room_view, name='create_room'),
    path('rooms/<uuid:room_id>/join/', views.join_room_view, name='join_room'),
    path('rooms/<uuid:room_id>/leave/', views.leave_room_view, name='leave_room'),
    path('rooms/<uuid:room_id>/start/', views.start_room_view, name='start_room'),
    path('rooms/<str:room_code>/', views.room_detail_view, name='room_detail'),
    
    # Matchmaking
    path('matchmaking/enter/', views.enter_matchmaking_view, name='enter_matchmaking'),
    path('matchmaking/leave/', views.leave_matchmaking_view, name='leave_matchmaking'),
]