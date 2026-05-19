import time
from typing import Dict, Any, Callable, Optional, TypedDict

class AgentExecutionState(TypedDict, total=False):
    question: str
    context: Dict[str, Any]
    current_state: str
    metadata: Dict[str, Any]
    structured_response: Optional[Dict[str, Any]]
    ui_trigger: Optional[Dict[str, Any]]
    errors: list
    response_text: str

class ExecutionEngine:
    """Robust orchestration runtime for agent execution (Phase 13)."""
    def __init__(self, max_retries: int = 3, timeout_sec: int = 10):
        self.max_retries = max_retries
        self.timeout_sec = timeout_sec

    async def execute_with_recovery(self, agent_func: Callable, state: Any) -> Any:
        """Executes an agent with retries and timeout tracking."""
        import asyncio
        start_time = time.time()
        retries = 0

        while retries < self.max_retries:
            try:
                # Execution trace logging
                print(f"[TRACE] Executing {agent_func.__name__} (Attempt {retries + 1})")
                
                # Assume async execution
                result_state = await agent_func(state)
                
                latency = time.time() - start_time
                print(f"[TRACE] {agent_func.__name__} completed in {latency:.2f}s")
                
                # Append telemetry (Phase 17 concept integration)
                result_state.setdefault("metadata", {})["latency_ms"] = latency * 1000
                return result_state

            except Exception as e:
                retries += 1
                print(f"[WARN] Partial failure in {agent_func.__name__}: {str(e)}")
                if retries >= self.max_retries:
                    print(f"[ERROR] Agent {agent_func.__name__} failed after {self.max_retries} retries.")
                    state.setdefault("errors", []).append(f"Agent {agent_func.__name__} failed: {str(e)}")
                    # Fallback triggers for gracefully recovering state (Phase 18 tie-in)
                    state["response_text"] = "Failed to complete step. Switching to fallback."
                    return state
                time.sleep(1) # Simple backoff
