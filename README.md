# Touri 🧳 — Multi-Agent AI Travel System

> **Production-grade AI travel planner for Egypt** built on LangGraph-orchestrated multi-agent architecture with Firebase memory, ChromaDB RAG, and a React + TypeScript premium frontend.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (React + TypeScript + Vite)                   │
│  Chat UI · Agent Trace Panel · EN/AR Localization       │
└─────────────────────┬───────────────────────────────────┘
                      │ REST + WebSocket
┌─────────────────────▼───────────────────────────────────┐
│  FastAPI Backend (Port 8000)                            │
│                                                         │
│  ┌─────────────┐                                        │
│  │ Router Agent│ ← Classifies intent, loads persona     │
│  └──────┬──────┘                                        │
│         ├──── trip_planning ──► Travel Planner Agent    │
│         ├──── budget_query  ──► Budget Specialist Agent │
│         └──── local_info   ──► Local Concierge Agent   │
│                                                         │
│  Tools: City Analysis · Weather · Itinerary             │
│         Budget Calculator · Restaurant Finder           │
│         Web Search (DuckDuckGo) · RAG Search           │
│                                                         │
│  Memory: Firebase Firestore (User Persona)              │
│  RAG:    ChromaDB + sentence-transformers               │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Configure API Keys

```bash
cd backend
cp .env.example .env
# Edit .env and add your keys:
# GROQ_API_KEY=gsk_...
# OPENWEATHER_API_KEY=...   (optional)
# Firebase config           (optional — falls back to in-memory)
```

### 2. Start Backend

```bash
cd backend
pip install -r requirements.txt
python start.py
# → http://localhost:8000
# → API docs: http://localhost:8000/docs
```

### 3. Start Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Send a message through the multi-agent system |
| `GET`  | `/api/user/{id}/persona` | Get user memory/preferences |
| `POST` | `/api/user/{id}/persona` | Update user preferences |
| `GET`  | `/api/user/{id}/history` | Get conversation history |
| `WS`   | `/ws/chat/{id}` | Streaming WebSocket chat |
| `GET`  | `/health` | Service health check |

## Grading Criteria Alignment

| Criterion | Implementation |
|-----------|----------------|
| ✅ Multi-Agent System | Router + Travel Planner + Budget Specialist + Local Concierge |
| ✅ Router Agent | Intent classification → delegation with full trace |
| ✅ Traceable interactions | Agent Trace Panel in UI (step-by-step decisions) |
| ✅ Advanced Memory | Firebase Firestore User Persona (persistent across sessions) |
| ✅ RAG Pipeline | ChromaDB + travel guides + dataset indexing |
| ✅ Live Web Search | DuckDuckGo integration with smart routing |
| ✅ Premium Custom UI | Apple-style React + TypeScript, NOT Gradio/Streamlit |
| ✅ **Bilingual EN/AR** | Full i18n, RTL layout, Arabic agent prompts (+2 marks) |

## Project Structure

```
Touri/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings
│   ├── start.py             # Startup script
│   ├── agents/
│   │   ├── router_agent.py  # Orchestrator
│   │   ├── travel_planner.py
│   │   ├── budget_specialist.py
│   │   └── local_concierge.py
│   ├── tools/               # Agent tools
│   ├── memory/              # Firebase + User Persona
│   ├── rag/                 # ChromaDB vector store
│   └── data/
│       ├── datasets/        # CSV data files
│       └── travel_guides/   # Markdown guides for RAG
└── frontend/
    └── src/
        ├── components/
        │   ├── Chat/        # ChatWindow, MessageBubble, InputBar
        │   ├── AgentTrace/  # TracePanel (grading criterion)
        │   ├── Itinerary/   # ItineraryCard
        │   └── Layout/      # Sidebar, LanguageToggle
        ├── hooks/           # useChat
        ├── services/        # API client
        └── i18n/            # EN + AR translations
```
