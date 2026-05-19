#!/usr/bin/env python3
"""
Touri — Backend startup script.
Sets up Python path and launches the FastAPI server.
"""
import sys
from pathlib import Path

# Add backend to Python path so imports work correctly
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(Path(__file__).parent)],
    )
