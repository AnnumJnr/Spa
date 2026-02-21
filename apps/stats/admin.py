"""
Admin configuration for stats models.
"""
from django.contrib import admin
from .models import CompetitiveStats, PracticeStats


@admin.register(CompetitiveStats)
class CompetitiveStatsAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_games', 'games_won', 'win_rate', 'current_win_streak']
    search_fields = ['user__username']
    readonly_fields = ['created_at', 'updated_at']
    
    def win_rate(self, obj):
        return f"{obj.win_rate:.1f}%"


@admin.register(PracticeStats)
class PracticeStatsAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_games', 'games_won']
    search_fields = ['user__username']
    readonly_fields = ['created_at', 'updated_at']