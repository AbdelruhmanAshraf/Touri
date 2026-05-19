import json
import asyncio
from typing import AsyncGenerator, Dict, Any

class StreamChunk(Dict[str, Any]):
    type: str
    content: str
    metadata: Dict[str, Any]

class WebSocketStreamer:
    """Handles Phase 12 Streaming AI Responses to Frontend WebSockets"""
    
    def __init__(self):
        self._typing = False

    async def stream_tokens(self, text_generator: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
        """Streams text chunks wrapped in UI progress indicators."""
        yield json.dumps({"type": "typing_indicator", "status": "active"})
        
        async for chunk in text_generator:
            yield json.dumps({
                "type": "token_chunk",
                "content": chunk,
                "metadata": {"timestamp": asyncio.get_event_loop().time()}
            })
            
        yield json.dumps({"type": "typing_indicator", "status": "inactive"})
        yield json.dumps({"type": "message_complete"})

    async def stream_structured_object(self, object_name: str, partial_data: Dict[str, Any]) -> str:
        """Progressively render structured entities (like native trip cards) as they build."""
        return json.dumps({
            "type": "progressive_object",
            "name": object_name,
            "data": partial_data
        })
