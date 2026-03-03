"""
Game state transitions: lead changes, round progression.
Now includes stack interruption.
"""
from typing import Optional, List
from .state import GameState, SetState, RoundState
from .card import Card
from .rules import RuleEngine
from .stack import StackManager


class TransitionEngine:
    """Handles state transitions during gameplay."""
    
    @staticmethod
    def change_lead(
        game_state: GameState,
        set_state: SetState,
        new_lead_player_id: int
    ) -> None:
        """
        Change the lead player.
        
        Args:
            game_state: Current game state
            set_state: Current set state
            new_lead_player_id: New lead player ID
        """
        game_state.lead_player_id = new_lead_player_id
        set_state.lead_player_id = new_lead_player_id
    
    @staticmethod
    def advance_round(
        set_state: SetState,
        new_lead_player_id: int
    ) -> Optional[RoundState]:
        """
        Advance to the next round.
        
        Args:
            set_state: Current set state
            new_lead_player_id: Lead player for next round
        
        Returns:
            New RoundState or None if set is complete
        """
        print(f"\n=== ADVANCE ROUND ===")
        print(f"Current round index: {set_state.current_round_index}")
        print(f"Total rounds: 5")
        print(f"New lead player: {new_lead_player_id}")
        
        # Mark current round as resolved
        current_round = set_state.get_current_round()
        if current_round:
            current_round.resolved = True
            print(f"Marked round {current_round.round_index} as resolved")
        
        # Move to next round
        set_state.advance_round()
        print(f"Advanced to round index: {set_state.current_round_index}")
        
        # Check if set is complete
        if set_state.is_complete():
            print("Set is complete - ending set")
            set_state.status = "ended"
            return None
        
        # Create new round
        print(f"Creating new round with lead player {new_lead_player_id}")
        new_round = RoundState(
            round_index=set_state.current_round_index,
            lead_player_id=new_lead_player_id
        )
        set_state.rounds.append(new_round)
        print(f"Created round {new_round.round_index}")
        print(f"=== END ADVANCE ROUND ===\n")
        
        return new_round
    
    @staticmethod
    def rotate_lead_for_new_set(game_state: GameState) -> int:
        """
        Rotate lead to next player clockwise for a new set.
        
        Args:
            game_state: Current game state
        
        Returns:
            New lead player ID
        """
        print(f"\n=== ROTATING LEAD FOR NEW SET ===")
        print(f"Current lead: {game_state.lead_player_id}")
        
        # Get next player using the improved method
        new_lead = game_state.get_next_player(game_state.lead_player_id)
        
        # SAFETY CHECK: Ensure we have a valid lead
        if new_lead == 0 or new_lead is None:
            print(f"ERROR: Invalid new lead {new_lead}, using first active player")
            active_players = game_state.get_active_players()
            new_lead = active_players[0] if active_players else 1
            print(f"Fallback lead: {new_lead}")
        
        game_state.lead_player_id = new_lead
        print(f"New lead: {new_lead}")
        print("=== END ROTATE LEAD ===\n")
        
        return new_lead
    
    @staticmethod
    def process_round_completion(
        game_state: GameState,
        set_state: SetState,
        round_state: RoundState
    ) -> dict:
        """
        Process all checks when a round completes (all players played).
        Now includes stack interruption.
        """
        print("\n=== PROCESS ROUND COMPLETION ===")
        print(f"Round index: {round_state.round_index}")
        print(f"Current lead before processing: {set_state.lead_player_id}")
        
        results = {
            'fouls': None,
            'offset': None,
            'round_advanced': False,
            'set_ended': False
        }
        
        # Check for fouls
        foul_result = RuleEngine.check_fouls(set_state, round_state)
        results['fouls'] = foul_result
        
        if foul_result.has_fouls():
            print(f"Fouls detected: {foul_result.fouling_players}")
            RuleEngine.apply_foul_penalties(
                game_state,
                set_state,
                foul_result.fouling_players
            )
            
            if foul_result.set_ended:
                print("Set ended due to fouls")
                results['set_ended'] = True
                return results
        
# Determine who won the round (player with highest card of lead suit)
        round_winner = round_state.lead_player_id  # Start with initial lead player
        highest_card = None
        
        print(f"Determining round winner from {len(round_state.plays)} plays...")
        for play in round_state.plays:
            print(f"  Player {play.player_id} played {play.card}")
            if play.card.suit == round_state.lead_suit:
                if highest_card is None or play.card.value > highest_card.value:
                    highest_card = play.card
                    round_winner = play.player_id
                    print(f"    → New highest card! Winner now: {round_winner}")
        
        print(f"🏆 Round winner: {round_winner} with {highest_card}")
        
        # CRITICAL FIX: The round winner BECOMES the new lead (not the next player)
        # In Spa, whoever plays the highest card of the lead suit becomes the new lead
        next_lead = round_winner
        print(f"➡️ Next lead: {next_lead} (the round winner)")
        
        # Update lead in both game state and set state
        TransitionEngine.change_lead(
            game_state,
            set_state,
            next_lead
        )
        print(f"✓ Lead updated to player {next_lead}")
        
        # Check for offsets (for tracking and stack interruption)
        # This tracks who offset whom during the round
        final_lead_player = round_state.lead_player_id
        final_lead_card = None

        for play in round_state.plays:
            player_id = play.player_id
            card = play.card
            
            offset_result = RuleEngine.check_offset(
                current_lead_player_id=final_lead_player,
                current_lead_card=final_lead_card,
                player_id=player_id,
                played_card=card
            )
            
            if offset_result.offset_occurred:
                print(f"  Offset detected: player {player_id} with {card}")
                final_lead_player = offset_result.new_lead_player_id
                final_lead_card = offset_result.offsetting_card
                results['offset'] = offset_result
                
                # Check if stack should be interrupted
                if set_state.stack_state and not set_state.stack_state.interrupted:
                    # If the offset player is NOT the stack owner, interrupt the stack
                    if final_lead_player != set_state.stack_state.owner_player_id:
                        from .stack import StackManager
                        StackManager.interrupt_stack(
                            set_state,
                            final_lead_player,
                            round_state.round_index
                        )
                        print(f"  ⚡ Stack interrupted by player {final_lead_player}")
        
        # Advance to next round with the round winner as lead
        print(f"Advancing to next round with lead {next_lead}")
        next_round = TransitionEngine.advance_round(set_state, next_lead)
        results['round_advanced'] = True
        
        if next_round is None:
            print("Set ended - no next round")
            results['set_ended'] = True
        else:
            print(f"Next round created: {next_round.round_index} with lead {next_round.lead_player_id}")
        
        print("=== END PROCESS ROUND COMPLETION ===\n")
        
        return results
        
    @staticmethod
    def determine_set_winner(set_state: SetState) -> Optional[int]:
        """
        Determine the winner of a completed set.
        
        In multiplayer, if only one player remains active, they win.
        Otherwise, the final lead wins.
        
        Args:
            set_state: Completed set state
        
        Returns:
            Winning player ID or None
        """
        if len(set_state.active_players) == 1:
            return set_state.active_players[0]
        
        return set_state.lead_player_id