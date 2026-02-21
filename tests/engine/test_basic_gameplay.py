"""
Basic gameplay tests for the engine.
"""
import pytest
from apps.game.engine.card import Card, Deck
from apps.game.engine.constants import Suit, Rank
from apps.game.engine.state import GameState, SetState, RoundState, PlayerState
from apps.game.engine.validator import CardValidator
from apps.game.engine.rules import RuleEngine


def test_deck_creation():
    """Test deck has 32 cards."""
    deck = Deck()
    assert len(deck) == 32


def test_card_comparison():
    """Test card value comparison."""
    card1 = Card(Suit.SPA, Rank.SEVEN)
    card2 = Card(Suit.SPA, Rank.KING)
    
    assert card2.is_higher_than(card1)
    assert not card1.is_higher_than(card2)


def test_foul_detection():
    """Test foul detection when player doesn't follow suit."""
    # Create a simple set state
    set_state = SetState(
        set_id="test",
        active_players=[1, 2],
        lead_player_id=1
    )
    
    # Create hands
    from apps.game.engine.card import Hand
    set_state.hands[1] = Hand([
        Card(Suit.SPA, Rank.KING),
        Card(Suit.YET, Rank.SEVEN)
    ])
    set_state.hands[2] = Hand([
        Card(Suit.SPA, Rank.SIX),  # Has Spa
        Card(Suit.KALO, Rank.EIGHT)
    ])
    
    # Create round with plays
    round_state = RoundState(
        round_index=0,
        lead_player_id=1,
        lead_suit=Suit.SPA
    )
    round_state.add_play(1, Card(Suit.SPA, Rank.KING))
    round_state.add_play(2, Card(Suit.KALO, Rank.EIGHT))  # Foul: has Spa but played Kalo
    
    # Check fouls
    foul_result = RuleEngine.check_fouls(set_state, round_state)
    
    assert foul_result.has_fouls()
    assert 2 in foul_result.fouling_players


def test_offset_detection():
    """Test offset when higher card of same suit is played."""
    offset_result = RuleEngine.check_offset(
        current_lead_player_id=1,
        current_lead_card=Card(Suit.SPA, Rank.SEVEN),
        player_id=2,
        played_card=Card(Suit.SPA, Rank.KING)
    )
    
    assert offset_result.offset_occurred
    assert offset_result.new_lead_player_id == 2


def test_no_offset_different_suit():
    """Test no offset when different suit is played."""
    offset_result = RuleEngine.check_offset(
        current_lead_player_id=1,
        current_lead_card=Card(Suit.SPA, Rank.SEVEN),
        player_id=2,
        played_card=Card(Suit.YET, Rank.KING)  # Different suit
    )
    
    assert not offset_result.offset_occurred


if __name__ == "__main__":
    pytest.main([__file__, "-v"])