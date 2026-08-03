# Touri — System Architecture Presentation (Part 1: Slides)

> YC Startup Engineering Review | Apple-Level Clarity | Enterprise Architecture Grade

---

## SLIDE 1 — Title

**Title**: Touri: Multi-Agent AI Travel Concierge for Egypt
**Subtitle**: Production-Grade RAG + LangGraph Orchestration + Persistent Memory
**Visual**: Dark teal→navy gradient. Centered Touri logo (pharaonic eye + compass). "YC Startup Engineering Review" badge top-right.
**Speaker Notes**: "I'm going to walk you through Touri — a production AI travel platform combining verified knowledge retrieval, multi-agent reasoning, and persistent user memory. This is engineered for production, not a prototype."

---

## SLIDE 2 — The Problem

**Title**: Why Generic AI Fails at Travel
**Key Points**:
1. LLMs hallucinate prices, hotel names, attraction details
2. No chatbot remembers you between sessions
3. Egypt tourism data fragmented across 100+ sources
4. Arabic-language travel AI virtually non-existent
5. Existing solutions: static databases or ungrounded chatbots

**Visual**: Split screen — ChatGPT with red X's on hallucinations vs Touri with green checks on verified facts. Animated red→green transition.
**Speaker Notes**: "Ask ChatGPT for a 5-day Cairo itinerary — it invents hotel names, guesses prices, forgets everything you told it yesterday. Travel needs verified, persistent, reasoning AI."

---

## SLIDE 3 — Architecture at a Glance

**Title**: System Architecture — 10 Interconnected Engineering Parts
**Key Points**:
1. Foundation (FastAPI + Firebase + ChromaDB)
2. RAG (vector retrieval over 3,723+ docs)
3. Memory (persistent cross-session preferences)
4. LLM (Gemini/Gemma with instruction hierarchy)
5. Graph & State (LangGraph orchestration)
6. Router (bilingual intent detection)
7. Agents (4 specialist AI agents)
8. Security (defense-in-depth, 10 security gates)
9. Routes (REST + WebSocket API)
10. Frontend (React Native/Expo, bilingual)

**Visual**: Layered diagram. Bottom: Foundation (gray). Middle: RAG+Memory+LLM+Security (blue). Upper-middle: Graph+Router+Agents (green). Top: Routes+Frontend (teal). Dependency arrows.
**Speaker Notes**: "10 interconnected parts. Each independently testable, clear interfaces, maps to one engineer's ownership."

---

## SLIDE 4 — Part 1: Foundation

**Title**: Foundation Layer — The Bedrock
**Key Points**:
- FastAPI async server with lifespan-managed startup verification
- Firebase Admin SDK (auth + Firestore persistence)
- ChromaDB PersistentClient (vector storage)
- Google Gemini API (LLM inference)
- SentenceTransformers (multilingual embeddings, EN+AR)
- Pydantic v2 settings with `.env` configuration
- Graceful degradation: Firebase down → in-memory fallback. Gemini quota → local ONNX

**Visual**: Four-box diagram. FastAPI center, connected to Firebase (top-right), ChromaDB (bottom-right), Gemini API (top-left), SentenceTransformers (bottom-left).
**Files**: `backend/main.py`, `backend/config.py`, `backend/clients.py`

---

## SLIDE 5 — Part 2: RAG

**Title**: RAG Pipeline — Verified Egypt Knowledge at Query Time
**Key Points**:
- 3,723+ documents across 5 domains: attractions, hotels, restaurants, medical, events
- Multilingual embeddings via Gemini `text-embedding-004` or SentenceTransformers
- Cosine similarity search with domain filtering (`where={"domain": "restaurant"}`)
- Relevance scoring: distance → [0,1] mapping
- Batch ingestion (50 docs/batch) with auto-retry on 429 rate limits
- Embedding backend auto-selection: Gemini → SentenceTransformers → ONNX fallback

**Visual**: Pipeline: CSV/XLSX → Document Loader → Embedding Model → ChromaDB. Query side: User Query → Embed → Cosine Search → Top-K → LLM Context.
**Files**: `backend/rag/vector_store.py`, `backend/rag/document_loader.py`

---

## SLIDE 6 — Part 3: Memory

**Title**: Persistent Memory — The User Never Repeats Themselves
**Key Points**:
- Firestore-backed message persistence with content-hash deduplication
- Travel preferences auto-extracted from natural conversation (no forms)
- Rolling conversation summaries triggered at 30+ messages
- Cross-session context injection for new conversations
- "DO NOT RE-ASK" enforcement directive injected into LLM prompts
- Periodic stale session cleanup every ~50 exchanges
- In-memory fallback when Firebase unavailable

**Visual**: Timeline: Session 1 (messages + extracted prefs) → Firestore → Session 2 (injected context). Show MemoryContext model: recent_messages, cross_session_messages, conversation_summary, travel_preferences, key_facts.
**Files**: `backend/services/memory_service.py`, `backend/agents/memory_manager.py`

---

## SLIDE 7 — Part 4: LLM

**Title**: LLM Engine — Gemini/Gemma with Instruction Hierarchy
**Key Points**:
- Primary: Gemma-4-26B-A4B-IT via Google AI Studio
- Dual interface: LangChain wrapper (graph nodes) + native SDK (streaming/multimodal)
- Global system instruction: non-negotiable security directives at top
- Bilingual detection: Arabic character ratio >30% → AR mode
- Response cleaning: strip thinking traces, markdown, internal artifacts
- LRU-cached model instances for efficiency
- Multimodal path hard-pins Gemini-2.5-Flash (images, audio, PDFs)

**Visual**: Left: Instruction Hierarchy pyramid (Security Directives → Core Directives → Domain Knowledge → Response Boundaries). Right: Model routing (Text→Gemma-4, Multimodal→Gemini-2.5-Flash).
**Files**: `backend/agents/llm.py`, `backend/agents/gemini_chat.py`

---

## SLIDE 8 — Part 5: Graph & State

**Title**: LangGraph — The Multi-Agent Nervous System
**Key Points**:
- `StateGraph(AgentState)` — typed state flows through all 7 nodes
- Entry: Memory → Router → Conditional Branch → Specialist → END
- Nodes: memory, router, planner, budget, concierge, general, needs_info
- Streaming: yields node_start, trace, node_end, final events
- ExecutionEngine wraps graph with retry/recovery (max 3 retries)
- Bilingual node labels + governorate-branded status messages

**Visual**: Graph: [Memory]→[Router]→diamond→[Planner]/[Budget]/[Concierge]/[General]/[Needs Info]→END. Animated token flow. Color-coded nodes.
**Files**: `backend/agents/graph.py`, `backend/agents/state.py`, `backend/services/agent_execution_engine.py`

---

## SLIDE 9 — Part 6: Router

**Title**: Router — Intent Detection + Smart Follow-Up
**Key Points**:
- Two-pass intent detection: fast regex heuristics → LLM fallback
- 5 intents: trip_planning, budget_query, local_info, general, needs_info
- Persona-aware: loads Firestore UserPersona before classification
- Gap detection: identifies missing destination, duration, budget, party size
- Sets needs_info when critical fields absent → generates conversational follow-up
- Prompt firewall integration for injection detection
- Bilingual: regex patterns cover both EN and AR keywords

**Visual**: Flowchart: User Message → Regex Heuristics → Match? Yes→Intent. No→LLM Classification (with persona context)→Intent. Side panel: gap detection logic.
**Files**: `backend/agents/router_agent.py`

---

## SLIDE 10 — Part 7: Agents

**Title**: Four Specialized AI Agents
**Key Points**:

| Agent | Primary Tool | Output | Special Feature |
|-------|-------------|--------|-----------------|
| Travel Planner | ChromaDB (4 parallel queries) | Structured day-by-day JSON itinerary | Modify mode, medical tourism weaving |
| Budget Specialist | ChromaDB + heuristics | budget_breakdown JSON | 3 budget brackets (economy/mid/luxury) |
| Local Concierge | ChromaDB (allergen-filtered) | spots JSON array | Halal enforcement, allergen keyword filter |
| General Chat | LLM only | Friendly text | Off-topic redirection to Egypt travel |

**Visual**: 2×2 grid. Each quadrant: agent icon, tool, output schema, sample response snippet. Color-coded: Planner=blue, Budget=green, Concierge=orange, General=gray.
**Files**: `backend/agents/travel_planner.py`, `backend/agents/budget_specialist.py`, `backend/agents/local_concierge.py`, `backend/agents/general_chat.py`

---

## SLIDE 11 — Part 8: Security

**Title**: Defense-in-Depth — 10 Security Gates
**Key Points**:
1. **Transport**: HSTS (1yr, preload), HTTPS redirect, TLS 1.2+
2. **Headers**: CSP, X-Frame-Options DENY, X-Content-Type-Options nosniff, Permissions-Policy
3. **Auth**: Firebase ID token verification (never trust client user_id), JWT access+refresh with family rotation, replay detection, HttpOnly/Secure/SameSite cookies
4. **Input**: Prompt firewall, UI_TRIGGER stripping, message limit 10k chars, attachment limit 20MB
5. **Output**: Response sanitization, trace sanitization, server header removal
6. **Rate Limiting**: Auth 5/min, AI chat configurable
7. **Production**: OpenAPI docs disabled, CORS whitelist, no stack traces

**Visual**: Concentric rings: Transport→Headers→Auth→Input Validation→Application. Each ring labeled with controls.
**Files**: `backend/middleware/security.py`, `backend/middleware/prompt_firewall.py`, `backend/routes/auth.py`

---

## SLIDE 12 — Part 9: Routes

**Title**: API Surface — REST + WebSocket
**Key Points**:
- `POST /api/chat` — Main chat (LangGraph multi-agent)
- `POST /api/chat` (multimodal) — Image/audio/PDF via Gemini native
- `WS /api/chat/ws` — Streaming with typing indicators + progressive objects
- `GET/POST /api/user/{uid}/persona` — Persona CRUD
- `POST /api/auth/session` — Firebase token → JWT cookies
- `POST /api/auth/refresh` — Token rotation with replay detection
- `POST /api/auth/logout` — Revoke + clear cookies
- `GET /api/auth/me` — Current user from cookie or Bearer header
- `GET /api/catalog/*` — Place catalog, search, categories

**Visual**: API map grouped by domain (Chat, Auth, Catalog, Persona). Each shows method, path, auth, rate limit, response shape.
**Files**: `backend/routes/chat.py`, `backend/routes/auth.py`, `backend/routes/catalog.py`

---

## SLIDE 13 — Part 10: Frontend

**Title**: React Native Frontend — Native Performance, AI-Native UX
**Key Points**:
- Expo Router with file-based routing (6 screens)
- Tab navigation: Home, Search, Chat, Plan, Profile
- AgentTracePanel: real-time blurred bottom sheet showing agent reasoning timeline
- Bilingual UI with i18next (EN/AR + RTL layout)
- Firebase Auth integration
- WebSocket client for streaming responses
- UI_TRIGGER parsing: scans response for `---UI_TRIGGER---` marker, spawns native modals
- Place detail modal with native sheet presentation

**Visual**: iPhone mockup array: 5 screens side-by-side. Home→Search→Chat (trace panel open)→Plan (itinerary)→Profile.
**Files**: `frontend/app/_layout.tsx`, `frontend/app/(tabs)/*.tsx`, `frontend/components/AgentTracePanel.tsx`

---

## SLIDE 14 — Request Lifecycle

**Title**: What Happens When You Send a Message
**Key Points** (end-to-end trace):
1. User types "Plan a 5-day trip to Luxor" in React Native chat
2. API client POSTs to `/api/chat` with Bearer token
3. FastAPI middleware: rate limit → size validation → CORS → security headers
4. Auth dependency: verify JWT → extract user_id
5. Route handler: strip UI_TRIGGER injection → validate message length
6. Branch: multimodal? → native Gemini. Text? → LangGraph
7. LangGraph: fresh_state → Memory Manager (load prefs: family of 4, mid-range, halal) → Router (intent: trip_planning) → Travel Planner
8. Travel Planner: 4 parallel ChromaDB queries (Luxor attractions, hotels, restaurants) → Gemma-4 generates structured 5-day JSON
9. ExecutionEngine wraps each node with retry/recovery
10. Response: sanitize output → sanitize trace → return ChatResponse
11. Post-response: persist_exchange (save messages, extract prefs, update summary)
12. Total latency: ~2-4 seconds

**Visual**: Horizontal swimlane: Client, Network, Middleware, Auth, Route, Graph, Agents, RAG, LLM, Memory. Timeline left→right.
