"""
Scoring calculation engine.
Handles end-of-set bonus calculations.
"""
from typing import List, Optional, Tuple
from .card import Card
from .state import GameState, SetState, RoundState
from .constants import Scoring, Rank


class ScoringEngine:
    """Calculates scores at end of set."""
    
    @staticmethod
    def calculate_set_score(
        game_state: GameState,
        set_state: SetState,
        winning_player_id: int
    ) -> int:
        """
        Calculate the score for winning a set.
        
        Args:
            game_state: Current game state
            set_state: Completed set state
            winning_player_id: Player who won the set
        
        Returns:
            Total score to award (base + bonuses)
        """
        # Get the winner's last played cards
        last_cards = ScoringEngine._get_last_played_cards(
            set_state,
            winning_player_id
        )
        
        if not last_cards:
            return Scoring.BASE_WIN
        
        # Check for bonuses based on last card(s)
        bonus = ScoringEngine._calculate_bonus(last_cards)
        
        return bonus if bonus > Scoring.BASE_WIN else Scoring.BASE_WIN
    
    @staticmethod
    def check_steal_bonus(
        set_state: SetState,
        final_round: RoundState,
        winning_player_id: int
    ) -> int:
        """
        Check if steal bonus applies.
        
        Steal bonus: 7 offsets 6 on the LAST card of Round 5.
        
        Args:
            set_state: Completed set state
            final_round: The final round (Round 5)
            winning_player_id: Player who won
        
        Returns:
            Additional bonus points (0 or 1)
        """
        if final_round.round_index != 4:  # Not final round
            return 0
        
        # Get all plays in final round
        plays = final_round.plays
        if len(plays) < 2:
            return 0
        
        # Check if winner's last card was a 7
        winner_play = None
        for play in plays:
            if play.player_id == winning_player_id:  # Fixed: use .player_id
                winner_play = play
                break
        
        if not winner_play or winner_play.card.rank != Rank.SEVEN:  # Fixed: use .card.rank
            return 0
        
        # Check if any previous card in this round was a 6
        for play in plays:
            if play.player_id != winning_player_id:  # Fixed: use .player_id
                if play.card.rank == Rank.SIX:  # Fixed: use .card.rank
                    # Check if the 7 was played after the 6 (offset)
                    plays_list = list(plays)
                    six_index = plays_list.index(play)
                    seven_index = plays_list.index(winner_play)
                    
                    if seven_index > six_index:
                        return Scoring.STEAL_BONUS
        
        return 0
    
    @staticmethod
    def _get_last_played_cards(
        set_state: SetState,
        player_id: int,
        count: int = 2
    ) -> List[Card]:
        """
        Get the last N cards played by a player across all rounds.
        
        Args:
            set_state: Set state
            player_id: Player to check
            count: Number of last cards to retrieve (default 2)
        
        Returns:
            List of last cards played (most recent last)
        """
        played_cards = []
        
        # Iterate through rounds in reverse order
        for round_state in reversed(set_state.rounds):
            play = round_state.get_play_by_player(player_id)
            if play:
                played_cards.insert(0, play.card)  # Fixed: use .card instead of ["card"]
                if len(played_cards) >= count:
                    break
        
        return played_cards
    
    @staticmethod
    def _calculate_bonus(last_cards: List[Card]) -> int:
        """
        Calculate bonus based on last card(s).
        
        Bonus hierarchy (highest to lowest):
        - Last two = 6,6: +6
        - Last two = 6,7 (any order): +5
        - Last two = 7,7: +4
        - Last card = 6: +3
        - Last card = 7: +2
        - Otherwise: +1 (base)
        
        Args:
            last_cards: List of last played cards (most recent last)
        
        Returns:
            Bonus points
        """
        if not last_cards:
            return Scoring.BASE_WIN
        
        last_card = last_cards[-1]
        
        # Check last two cards bonuses
        if len(last_cards) >= 2:
            second_last = last_cards[-2]
            
            # Both 6s
            if last_card.rank == Rank.SIX and second_last.rank == Rank.SIX:
                return Scoring.LAST_TWO_SIXES
            
            # 6 and 7 (any order)
            if ({last_card.rank, second_last.rank} == {Rank.SIX, Rank.SEVEN}):
                return Scoring.LAST_SIX_SEVEN
            
            # Both 7s
            if last_card.rank == Rank.SEVEN and second_last.rank == Rank.SEVEN:
                return Scoring.LAST_TWO_SEVENS
        
        # Check last card bonuses
        if last_card.rank == Rank.SIX:
            return Scoring.LAST_SIX
        
        if last_card.rank == Rank.SEVEN:
            return Scoring.LAST_SEVEN
        
        # Base win
        return Scoring.BASE_WIN