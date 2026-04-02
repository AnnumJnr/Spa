"""
Frontend template views.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout


def home_view(request):
    """Landing page - accessible to everyone."""
    # Don't auto-redirect authenticated users, let them see the homepage
    return render(request, 'home.html')


def login_view(request):
    """Login page."""
    if request.user.is_authenticated:
        return redirect('frontend:game_modes')
    return render(request, 'accounts/login.html')


def register_view(request):
    """Registration page."""
    if request.user.is_authenticated:
        return redirect('frontend:game_modes')
    return render(request, 'accounts/register.html')


def logout_view(request):
    """Logout user."""
    logout(request)
    return redirect('frontend:home')


@login_required
def profile_view(request):
    """User profile page."""
    return render(request, 'accounts/profile.html')


def game_modes_view(request):
    """Game mode selection page."""
    return render(request, 'lobby/game_modes.html')


def quick_match_view(request):
    """Quick match waiting screen."""
    return render(request, 'lobby/quick_match.html')


def multiplayer_lobby_view(request):
    """Multiplayer lobby."""
    return render(request, 'lobby/multiplayer_lobby.html')


def create_room_view(request):
    """Private room creation."""
    return render(request, 'lobby/create_room.html')


def join_room_view(request, room_code):
    """Join room by code."""
    return render(request, 'lobby/join_room.html', {
        'room_code': room_code
    })


def practice_setup_view(request):
    """Practice mode setup."""
    return render(request, 'lobby/practice_setup.html')


def game_table_view(request, game_id):
    """Main game interface - accessible to guests and authenticated users."""
    from apps.game.models import Game, GamePlayer
    from apps.game.utils import get_or_create_guest_identity
    
    try:
        game = Game.objects.get(id=game_id)
    except Game.DoesNotExist:
        return redirect('frontend:game_modes')
    
    # Get or create guest identity
    is_guest, user, session_guest_name = get_or_create_guest_identity(request)
    
    # Get guest name from URL query string (for private room invites)
    url_guest_name = request.GET.get('guest_name', '')
    
    # Determine the guest name to use
    if is_guest:
        guest_name = url_guest_name if url_guest_name else session_guest_name
    else:
        guest_name = ''
    
    # Find player in this game
    if is_guest:
        player = game.players.filter(
            is_guest=True,
            guest_name=guest_name
        ).first()
    else:
        player = game.players.filter(user=user).first()
    
    if not player:
        return redirect('frontend:game_modes')
    
    # Determine game type for stack visibility
    is_private_room = False
    if hasattr(game, 'room') and game.room:
        is_private_room = game.room.mode == 'private'
    
    context = {
        'game_id': str(game_id),
        'player_id': str(player.id),
        'guest_name': guest_name if is_guest else '',
        'is_guest': is_guest,
        'is_private_room': is_private_room,
        'is_practice': game.is_practice,
    }
    return render(request, 'game/table.html', context)

@login_required
def stats_dashboard_view(request):
    """Player statistics."""
    return render(request, 'stats/dashboard.html')


def room_lobby_view(request, room_code):
    """Private room waiting lobby."""
    from apps.lobby.models import GameRoom, RoomPlayer
    from apps.game.utils import get_or_create_guest_identity

    try:
        room = GameRoom.objects.get(room_code=room_code.upper())
    except GameRoom.DoesNotExist:
        return redirect('frontend:game_modes')

    if room.status == GameRoom.STATUS_IN_PROGRESS and room.game:
        return redirect('frontend:game_table', game_id=room.game.id)

    if room.status == GameRoom.STATUS_FINISHED:
        return redirect('frontend:game_modes')
    
    is_guest = not request.user.is_authenticated
    
    # Get guest name from various sources
    guest_name = ''
    
    if is_guest:
        # Try to get guest name from session first
        session_guest_name = request.session.get('lobby_guest_name', '')
        if session_guest_name:
            guest_name = session_guest_name
            print(f" Guest name found in session: {guest_name}")
        
        # If not in session, try to find from database
        if not guest_name:
            # Look for any active guest player in this room
            room_player = room.room_players.filter(
                status=RoomPlayer.STATUS_ACTIVE,
                user__isnull=True,
                is_bot=False
            ).first()
            if room_player and room_player.guest_name:
                guest_name = room_player.guest_name
                # Store in session for future use
                request.session['lobby_guest_name'] = guest_name
                request.session.modified = True
                print(f" Guest name retrieved from database: {guest_name}")
        
        # If we still don't have a guest name, check if there's a cookie
        if not guest_name:
            guest_name = request.COOKIES.get('lobby_guest_name', '')
            if guest_name:
                print(f" Guest name found in cookie: {guest_name}")
                # Store in session
                request.session['lobby_guest_name'] = guest_name
                request.session.modified = True
    
    # For authenticated users, ensure we have their info
    if not is_guest:
        print(f" Authenticated user: {request.user.username}")
    
    print(f" Rendering room lobby - is_guest: {is_guest}, guest_name: '{guest_name}'")
    
    context = {
        'room_code': room.room_code,
        'room_id': str(room.id),
        'target_score': room.target_score,
        'max_players': room.max_players,
        'is_guest': is_guest,
        'guest_name': guest_name or '',
    }
    return render(request, 'lobby/room_lobby.html', context)