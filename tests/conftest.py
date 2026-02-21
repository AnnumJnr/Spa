"""
Pytest configuration and fixtures.
"""
import pytest
from django.contrib.auth import get_user_model
from apps.accounts.models import PlayerProfile

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )
    PlayerProfile.objects.create(user=user)
    return user


@pytest.fixture
def authenticated_client(client, user):
    """Create an authenticated client."""
    client.force_login(user)
    return client