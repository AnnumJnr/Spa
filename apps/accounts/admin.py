"""
Admin configuration for accounts app.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, PlayerProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'display_name', 'is_online', 'created_at']
    list_filter = ['is_online', 'is_staff', 'is_superuser']
    search_fields = ['username', 'email', 'display_name']
    ordering = ['-created_at']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Profile', {'fields': ('display_name', 'avatar', 'is_online', 'last_seen')}),
    )


@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'preferred_difficulty', 'sound_enabled', 'animations_enabled']
    list_filter = ['preferred_difficulty', 'sound_enabled', 'animations_enabled']
    search_fields = ['user__username', 'user__email']