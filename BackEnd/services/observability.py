import time

class AnalyticsTracker:
    def __init__(self):
        self.events = []
    
    def track_latency(self, agent_name: str, latency_ms: float):
        self.events.append({"type": "latency", "agent": agent_name, "value": latency_ms, "timestamp": time.time()})
    
    def track_memory_hit(self, success: bool):
        self.events.append({"type": "memory_retrieval", "success": success, "timestamp": time.time()})
        
    def track_dropoff(self, state: str):
        self.events.append({"type": "funnel_dropoff", "state": state, "timestamp": time.time()})

analytics = AnalyticsTracker()
