# Touri Architecture Integration Guide (Phases 9-20)

This document outlines the conceptual integration path for the newly generated modular services into the core `Touri` system.

## 1. State Machine Integration (`backend/services/state_machine.py`)
- **Current logic**: Conversations loosely flow based on pure LLM direction.
- **New logic**: `ConversationState` must be persisted in Firebase.
- **Action**: Update `backend/memory/conversation_store.py` to save `current_state`. Inject `StateMachine().get_next_logical_state()` inside `backend/agents/router_agent.py` to strictly govern valid tool availability per state.

## 2. Recommendation & Personalization (`backend/services/personalization.py` + `backend/services/recommendation_ranker.py`)
- **Current logic**: Relying on LangChain raw outputs.
- **New logic**: The `travel_planner.py` agent generates candidate activities/hotels. Before returning to user, route through `PersonalizationEngine` and `RecommendationRanker`.
- **Action**: Wrap final structured entity yields inside `backend/agents/travel_planner.py` with bounding criteria (e.g. `rank_hotels()`).

## 3. Streaming and UI Triggers (`backend/services/websocket_streamer.py` + `backend/schemas/ui_triggers.py`)
- **Current logic**: Sync request-response JSON or basic chips.
- **New logic**: Async websockets pushing type updates (`typing_indicator`, `progressive_object`).
- **Action**: Modify FastAPI `backend/routes/chat.py` to use `WebSocket` endpoints instead of standard HTTP POST. Render `UITrigger` components using React Native components on the frontend (`frontend/components`).

## 4. Execution & Offline Recovery (`backend/services/agent_execution_engine.py` + `backend/services/offline_fallback.py`)
- **Current logic**: Crashes result in 500 API errors.
- **New logic**: `ExecutionEngine` wraps node calls in `backend/agents/graph.py` to retry Langchain/Gemini calls. Fallback injected if retries exhaust.
- **Action**: Use `execute_with_recovery` in Langgraph node definitions. Catch edge cases with `get_fallback_itinerary()`.
