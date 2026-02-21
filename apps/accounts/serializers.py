"""
Serializers for user and profile data.
"""
from rest_framework import serializers
from .models import User, PlayerProfile


class PlayerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayerProfile
        fields = [
            'preferred_difficulty',
            'sound_enabled',
            'animations_enabled',
        ]


class UserSerializer(serializers.ModelSerializer):
    profile = PlayerProfileSerializer(read_only=True)
    
    
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'display_name',
            'name',
            'avatar',
            'is_online',
            'last_seen',
            'profile',
        ]
        read_only_fields = ['id', 'is_online', 'last_seen', 'name']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 'display_name']
    
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Passwords do not match.")
        return data
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        PlayerProfile.objects.create(user=user)
        return user