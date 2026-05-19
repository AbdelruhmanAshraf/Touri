from enum import Enum
from typing import List, Dict, Any, Optional

class ConversationState(str, Enum):
    ONBOARDING = "onboarding"
    COLLECTING_REQUIREMENTS = "collecting_requirements"
    DESTINATION_SELECTION = "destination_selection"
    PLANNING = "planning"
    BUDGETING = "budgeting"
    CONCIERGE = "concierge"
    REFINING = "refining"
    COMPLETED = "completed"

class StateMachine:
    def __init__(self):
        self.transitions = {
            ConversationState.ONBOARDING: [ConversationState.COLLECTING_REQUIREMENTS],
            ConversationState.COLLECTING_REQUIREMENTS: [ConversationState.DESTINATION_SELECTION, ConversationState.ONBOARDING],
            ConversationState.DESTINATION_SELECTION: [ConversationState.PLANNING, ConversationState.COLLECTING_REQUIREMENTS],
            ConversationState.PLANNING: [ConversationState.BUDGETING, ConversationState.DESTINATION_SELECTION, ConversationState.REFINING],
            ConversationState.BUDGETING: [ConversationState.CONCIERGE, ConversationState.PLANNING],
            ConversationState.REFINING: [ConversationState.PLANNING, ConversationState.CONCIERGE],
            ConversationState.CONCIERGE: [ConversationState.COMPLETED, ConversationState.REFINING],
            ConversationState.COMPLETED: [ConversationState.ONBOARDING]
        }
    
    def can_transition(self, current_state: ConversationState, next_state: ConversationState) -> bool:
        return next_state in self.transitions.get(current_state, [])
    
    def get_next_logical_state(self, current_state: ConversationState) -> ConversationState:
        if current_state in self.transitions and self.transitions[current_state]:
            return self.transitions[current_state][0]
        return current_state
