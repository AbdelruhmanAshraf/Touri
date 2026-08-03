# Touri 🧳 — Multi-Agent AI Travel Companion for Egypt

Touri is a production-grade, bilingual (English/Arabic) AI travel companion app designed for exploring Egypt. It features a **React Native (Expo)** mobile application, a **FastAPI** backend orchestrating a **LangGraph multi-agent flow**, persistent session memories in **Firebase Firestore**, and semantic search indexing powered by **ChromaDB**.

Developed for deployment, Touri stands out as a showcase portfolio project demonstrating advanced LLM orchestration, secure API architectures, and polished mobile engineering.

---

## 🏗️ Architecture Overview

Touri coordinates multiple AI agents to handle specialized travel planning tasks, using a strict state machine routing system to ensure coherent conversations.

```
┌─────────────────────────────────────────────────────────┐
│              Touri React Native (Expo) Client           │
│   Discover Catalog · Live Trip Plan · Agent Trace UI    │
└─────────────────────┬───────────────────────────────────┘
                      │ REST + WebSocket Streaming
┌─────────────────────▼───────────────────────────────────┐
│               FastAPI Multi-Agent Server                │
│                                                         │
│   ┌─────────────┐                                       │
│   │ Router Agent│ ◄── Classifies Intent, Evaluates State  │
│   └──────┬──────┘                                       │
│          ├──── Planning ──────► Travel Planner Agent     │
│          ├──── Budgeting ─────► Budget Specialist Agent  │
│          ├──── Local Concierge ► Local Concierge Agent   │
│          └──── General Chat ──► General Chat Agent      │
│                                                         │
│   Database:  ChromaDB (Local RAG) + Firebase Firestore  │
│   Firewall:  Jailbreak / Injection & UI Spoofing Shield │
└─────────────────────────────────────────────────────────┘
```

---

## 🌟 Key Features

*   **LangGraph Multi-Agent Routing**: User prompts are parsed by a Router Agent that determines the current state and delegates to specialized sub-agents (Travel Planner, Budget Specialist, Local Concierge, or General Chat).
*   **Agent Trace Panel**: Users can view the step-by-step reasoning, tool invocations, and agent hops in real-time right from the chat UI—perfect for showcasing AI transparency.
*   **Bilingual EN/AR Support**: Complete localization with instant soft RTL (Right-to-Left) layout transitions, Arabic prompts, and localized LLM system instructions.
*   **Interactive Discover Catalog**: Features current local events, popular attractions, top-rated hotels, and authentic Egyptian food suggestions.
*   **Dynamic Itinerary Checklist & Budget Tracker**: Once an agent builds a trip, the app synchronizes a custom day-by-day checklist, marking completed events and calculating remaining budget in real-time.
*   **Enterprise-Grade Security Firewall**: Built-in backend protections filtering prompt injections, system prompt leaks, PII exposure, and UI trigger spoofing.
*   **Multimodal Chat Capabilities**: Supports uploading images, voice note recordings, and document attachments for rich contextual assistant answers.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend Client** | React Native, Expo SDK 54, Expo Router, TypeScript, Reanimated, i18next |
| **Backend API** | FastAPI, Python 3.12, Uvicorn, Pydantic, WebSockets |
| **Orchestration** | LangGraph, LangChain, Google Generative AI (`gemma-4-26b-a4b-it` / Gemini) |
| **RAG & Search** | ChromaDB (Vector Store), Sentence Transformers (`paraphrase-multilingual-MiniLM-L12-v2`) |
| **Database & Auth** | Firebase Admin SDK, Firestore Database, Firebase Authentication |

---

## 🚀 Quick Start Guide

### 1. Backend Server Setup

Ensure Python 3.12+ is installed.

```bash
# Navigate to backend
cd backend

# Create virtual environment and activate
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Open .env and add your GEMINI_API_KEY, SESSION_JWT_SECRET, and Firebase credentials
```

Run the backend server using the startup script:
```bash
python start.py
```
*   **REST API**: `http://localhost:8000`
*   **API Docs**: `http://localhost:8000/docs`

---

### 2. Frontend Client Setup

Ensure Node.js 18+ is installed.

```bash
# Navigate to frontend
cd frontend

# Install packages
npm install

# Configure environment variables
cp .env.example .env
# Set your Firebase API details and target backend URL (EXPO_PUBLIC_API_BASE_URL)
```

Run the client:
```bash
npm start
```
*   *Note: The `npm start` script automatically increases system file descriptors (`ulimit -n 65536`) to prevent Metro watch limit crashes.*
*   Press `w` to run in a web browser, `i` to launch in iOS Simulator, or `a` for Android.

---

## 📂 Project Structure

```
Touri/
├── backend/                  # FastAPI Backend Server
│   ├── agents/               # LangGraph nodes and agent definitions
│   ├── data/                 # Local CSV datasets and Chroma database
│   ├── memory/               # Semantic and Firestore memory integration
│   ├── middleware/           # Security firewall, rate limiter, and sanitizers
│   ├── rag/                  # ChromaDB document loader and retriever
│   ├── routes/               # FastAPI route controllers (Auth, Chat, Catalog)
│   ├── schemas/              # Pydantic schemas and UI Trigger schemas
│   ├── services/             # State machine and websocket streamer
│   ├── tools/                # Travel planning, weather, and budget tools
│   ├── check_backend.py      # Self-repair diagnostic pipeline
│   └── main.py               # Application entrypoint
│
├── frontend/                 # React Native Mobile App
│   ├── app/                  # Expo Router tabs and modal screens
│   ├── components/           # Custom avatars, trace panels, and timelines
│   ├── config/               # Firebase app initialisation
│   ├── constants/            # Design system colors and governorates
│   ├── hooks/                # Firebase Auth and profile hooks
│   ├── i18n/                 # English/Arabic locale dictionaries
│   ├── services/             # Axios and WebSocket API clients
│   └── theme/                # Flat 2D layout and styling tokens
│
└── docs/                     # Technical documentation & Presentations
    ├── architecture_plan.md  # System FSM integration plans
    ├── presentation/         # Product pitch slides and flows
    ├── security/             # Vulnerability checklists and remediation reports
    └── troubleshooting/      # Firebase auth setup notes
```

---

## 📄 Documentation index

For deep dives into architectural plans, security reports, and presentation decks:
*   [Architecture Integration Plan](file:///Users/abdelruhamanelfekky/Desktop/Touri/docs/architecture_plan.md)
*   [Security Hardening Checklist](file:///Users/abdelruhamanelfekky/Desktop/Touri/docs/security/security_checklist.md)
*   [Security Remediation Report](file:///Users/abdelruhamanelfekky/Desktop/Touri/docs/security/security_remediation_report.md)
*   [Product Slides & Roadmaps](file:///Users/abdelruhamanelfekky/Desktop/Touri/docs/presentation/1_slides.md)
*   [Firebase Authentication Troubleshooting Guide](file:///Users/abdelruhamanelfekky/Desktop/Touri/docs/troubleshooting/firebase_auth_troubleshooting.md)
