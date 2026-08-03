# Touri — Team Distribution & Visual Diagrams (Part 3)

---

# SECTION 2 — TEAM DISTRIBUTION

Each of the 10 engineering parts maps to one engineer. Below is the complete breakdown.

---

## Part 1 — Foundation Engineer

### Simple Explanation
This engineer sets up the "plumbing" — the server, database connections, and cloud services that everything else plugs into. They make sure the app starts up, connects to Firebase and ChromaDB, and can talk to Google's AI models.

### Professional Engineering Language
**Responsibility**: Infrastructure bootstrap, configuration management, service connectivity, startup verification, graceful degradation.

**Files/Modules Owned**:
- `backend/main.py` — FastAPI app factory, lifespan handler, CORS, route mounting
- `backend/config.py` — Pydantic v2 Settings with AliasChoices, env validation
- `backend/clients.py` — Shared HTTP/DB client factories
- `backend/.env.example` — Environment variable template
- `backend/check_backend.py` — Health check script

**Inputs**: Environment variables (`.env` file)
**Outputs**: Running FastAPI server, verified service connections (ChromaDB, Firebase, Gemini)
**APIs/Services**: Firebase Admin SDK, ChromaDB PersistentClient, Google Generative AI SDK
**Dependencies**: None (this is the root)
**Risks**: Missing API keys, ChromaDB path permissions, Firebase credential file not found
**Deliverables**: Bootable server with all services verified at startup, health check endpoint

---

## Part 2 — RAG Engineer

### Simple Explanation
This engineer builds the "knowledge brain" — they take all the Egypt travel data (CSV files with attractions, hotels, restaurants), convert it into AI-readable vectors, and store it so the AI can search it instantly when a user asks a question.

### Professional Engineering Language
**Responsibility**: Document ingestion pipeline, embedding model selection, vector store management, semantic search with domain filtering, relevance scoring.

**Files/Modules Owned**:
- `backend/rag/vector_store.py` — ChromaDB client, collection management, embedding function factory, query with relevance scoring
- `backend/rag/document_loader.py` — CSV/XLSX parser, Document model, batch loading
- `backend/rag/retriever.py` — High-level retrieval with source attribution formatting
- `backend/data/egypt_csv/` — Source data files
- `backend/data/chroma_db/` — Persistent vector store directory

**Inputs**: Raw CSV/XLSX files with Egypt travel data
**Outputs**: ChromaDB collection (`egypt_travel_knowledge`), `query()` function returning `[{id, text, metadata, distance, relevance}]`
**APIs/Services**: ChromaDB, Gemini Embedding API (`text-embedding-004`), SentenceTransformers
**Dependencies**: Part 1 (Foundation) — needs ChromaDB path and Gemini API key from config
**Risks**: Embedding model incompatibility on target OS, Gemini free-tier rate limits during ingestion, embedding function conflict on collection re-creation
**Deliverables**: Ingested and queryable vector store, `query()` function with domain filtering, auto-retry on rate limits, embedding backend fallback chain

---

## Part 3 — Memory Engineer

### Simple Explanation
This engineer builds the "memory" — so the AI remembers what users told it before. If a user says they're vegetarian in one conversation, the AI remembers that forever and never recommends steak houses. No forms, no quizzes — the AI learns from natural conversation.

### Professional Engineering Language
**Responsibility**: Message persistence with deduplication, travel preference extraction from natural language, conversation summarisation, cross-session context injection, state machine persistence, stale session cleanup.

**Files/Modules Owned**:
- `backend/services/memory_service.py` — `save_message()`, `get_recent_messages()`, `get_conversation_summary()`, `save_conversation_summary()`, `get_travel_preferences()`, `update_travel_preferences()`, `load_memory_context()`, `format_memory_for_prompt()`
- `backend/agents/memory_manager.py` — `load_memory_into_state()` (pre-response), `persist_exchange()` (post-response), `maybe_summarise()` (auto-trigger at 30+ messages)
- `backend/memory/conversation_store.py` — Firestore conversation state persistence
- `backend/memory/firebase_client.py` — Firebase connection status, DB getter
- `backend/memory/user_persona.py` — UserPersona model, CRUD operations

**Inputs**: User messages + assistant responses (from graph execution)
**Outputs**: `MemoryContext` (recent_messages, cross_session_messages, conversation_summary, travel_preferences, key_facts), formatted prompt string with "DO NOT RE-ASK" directive
**APIs/Services**: Firestore (`users/{uid}/chats/{sid}/messages`, `users/{uid}/memory/conversation_summary`, `users/{uid}/travel_preferences/prefs`)
**Dependencies**: Part 1 (Foundation) — needs Firebase connection
**Risks**: Firestore write latency, large message volumes triggering excessive summarisation, preference extraction false positives
**Deliverables**: Complete memory lifecycle (pre-response load → post-response persist → cross-session injection), auto-summarisation at 30+ messages, in-memory fallback when Firebase unavailable

---

## Part 4 — LLM Engineer

### Simple Explanation
This engineer connects the app to Google's AI models (Gemini/Gemma). They write the "system prompt" — the rules the AI must follow — and make sure the AI responds in the right language (English or Arabic), never reveals its internal instructions, and always stays focused on Egypt travel.

### Professional Engineering Language
**Responsibility**: LLM client factory (dual LangChain + native SDK), system instruction hierarchy, bilingual detection and routing, response cleaning pipeline, model caching, multimodal handler.

**Files/Modules Owned**:
- `backend/agents/llm.py` — `get_llm()` (LangChain wrapper, LRU-cached), `get_gemini_model()` (native SDK), `GLOBAL_SYSTEM_INSTRUCTION`, `detect_language()`, `safe_extract_text()`, `clean_response()`, `lang_directive()`, `t()` (bilingual helper)
- `backend/agents/gemini_chat.py` — Multimodal handler (images, audio, PDFs), hard-pins Gemini-2.5-Flash

**Inputs**: User messages, language preference, multimodal attachments
**Outputs**: LLM instances (cached), cleaned response text, detected language
**APIs/Services**: Google AI Studio API (Gemma-4-26B-A4B-IT, Gemini-2.5-Flash)
**Dependencies**: Part 1 (Foundation) — needs Gemini API key from config
**Risks**: API key rotation, model deprecation, rate limiting, instruction hierarchy bypass via sophisticated prompt injection
**Deliverables**: Cached LLM factory, hardened system instruction with non-negotiable security directives, bilingual detection (>30% AR chars → AR mode), response cleaning pipeline (strip thinking traces, markdown, artifacts)

---

## Part 5 — Graph & State Engineer

### Simple Explanation
This engineer builds the "nervous system" — the flowchart that decides which AI agent handles each user request. They define the shared "state" (all the information that flows between agents) and wire everything together so the Memory → Router → Specialist pipeline works seamlessly.

### Professional Engineering Language
**Responsibility**: LangGraph StateGraph compilation, AgentState TypedDict definition, node wiring (edges + conditional edges), streaming event emission, ExecutionEngine integration, bilingual node labeling.

**Files/Modules Owned**:
- `backend/agents/graph.py` — `build_graph()` (compiled StateGraph), `run_chat()` (sync invocation), `stream_chat()` (async generator), `_branch()` (conditional routing function)
- `backend/agents/state.py` — `AgentState` TypedDict (25+ fields), `AgentStep` TypedDict, `Intent` Literal type, `fresh_state()` factory, `make_step()` helper
- `backend/services/agent_execution_engine.py` — `ExecutionEngine` class with `execute_with_recovery()`

**Inputs**: user_id, session_id, user_message, language, chat_history
**Outputs**: Complete AgentState with response_text, itinerary/budget/spots, agent_trace
**APIs/Services**: LangGraph, LangChain
**Dependencies**: Parts 2, 3, 4 (RAG, Memory, LLM) — graph nodes import from all three
**Risks**: Graph compilation errors, state type mismatches, conditional edge routing to non-existent nodes, streaming event ordering
**Deliverables**: Compiled and cached StateGraph, typed AgentState, streaming event generator, ExecutionEngine with retry/recovery (max 3 retries, 1s backoff)

---

## Part 6 — Router Engineer

### Simple Explanation
This engineer builds the "traffic controller" — the agent that reads every user message and decides: "Is this person asking for a trip plan? A budget? Restaurant recommendations? Or do I need to ask them more questions first?" It works in both English and Arabic.

### Professional Engineering Language
**Responsibility**: Two-pass intent detection (regex heuristics + LLM classification), persona loading and injection, gap detection with cross-referencing (message + persona + stored prefs + chat history), smart follow-up question generation, prompt firewall integration, conversation state machine transitions.

**Files/Modules Owned**:
- `backend/agents/router_agent.py` — `route()` node, `_heuristic_intent()`, `_llm_intent()`, `_detect_gaps()`, `_build_followup()`, `_load_persona()`
- `backend/services/requirement_engine.py` — `detect_missing_fields()`, `build_questions_for_gaps()`
- `backend/services/conversation_state.py` — `ConversationState` model, `determine_next_state()`, `REQUIRED_FIELDS`
- `backend/services/state_machine.py` — `StateMachine` class, `ConversationState` enum

**Inputs**: User message, UserPersona, TravelPreferences, chat_history
**Outputs**: intent (5 values), active_agent label, structured_questions (QuestionSet), response_text (follow-up questions when needs_info), requirements_status
**APIs/Services**: Firestore (persona load), LLM (intent classification fallback), prompt_firewall
**Dependencies**: Parts 3, 4, 5 (Memory, LLM, Graph & State)
**Risks**: Incorrect intent classification leading to wrong agent dispatch, gap detection false negatives (missing critical info but not detected), bilingual regex coverage gaps
**Deliverables**: Intent classifier (regex fast path + LLM fallback), gap detector with 4-field cross-referencing, bilingual follow-up question generator, state machine transition logic

---

## Part 7 — Agents Engineer(s)

### Simple Explanation
These engineers build the "specialists" — the AI agents that actually do the work. One builds the travel planner (creates day-by-day itineraries), one builds the budget calculator (estimates costs), one builds the local concierge (recommends restaurants and hidden gems), and one handles general conversation.

### Professional Engineering Language
**Responsibility**: Specialist agent nodes with RAG retrieval, LLM prompt engineering, structured JSON output parsing, UI_TRIGGER injection, personalization engine integration, recommendation ranking, modify-mode support.

**Files/Modules Owned**:
- `backend/agents/travel_planner.py` — `plan()` node, `_gather_context()` (4 parallel ChromaDB queries), `_persona_summary()`, modify-mode addendum
- `backend/agents/budget_specialist.py` — `calculate()` node, `_BUDGET_HEURISTICS` (3 brackets), parallel ChromaDB pricing queries
- `backend/agents/local_concierge.py` — `recommend()` node, `_gather()` (allergen-filtered), `_ALLERGEN_KEYWORDS` (4 categories), halal enforcement
- `backend/agents/general_chat.py` — General conversation handler
- `backend/services/personalization.py` — `PersonalizationEngine`
- `backend/services/recommendation_ranker.py` — `RecommendationRanker`

**Inputs**: AgentState (with intent, persona, memory_context, user_message)
**Outputs**: AgentState enriched with structured output (itinerary/budget_breakdown/spots_json), response_text with UI_TRIGGER, suggestions
**APIs/Services**: ChromaDB (RAG), Gemini/Gemma (LLM)
**Dependencies**: Parts 2, 3, 4, 5 (RAG, Memory, LLM, Graph & State)
**Risks**: LLM returning malformed JSON, RAG returning irrelevant context, allergen filter false negatives, budget heuristics outdated
**Deliverables**: 4 independently testable agent nodes, each producing structured JSON, with UI_TRIGGER injection for frontend sync

---

## Part 8 — Security Engineer

### Simple Explanation
This engineer builds the "castle walls" — everything that protects the app from attacks. They make sure only real users can access the app, block hackers from injecting malicious prompts, encrypt all data in transit, and ensure the app follows security best practices.

### Professional Engineering Language
**Responsibility**: Security middleware stack (headers, HTTPS redirect, size limiting, timeout), JWT auth with family-based refresh token rotation, prompt injection firewall, output sanitization, rate limiting, CORS whitelist, production hardening.

**Files/Modules Owned**:
- `backend/middleware/security.py` — `SecurityHeadersMiddleware`, `HTTPSRedirectMiddleware`, `RequestSizeLimitMiddleware`, `RequestTimeoutMiddleware`, `install_security_middleware()`
- `backend/middleware/prompt_firewall.py` — `analyze_prompt()`, injection pattern detection
- `backend/middleware/output_sanitizer.py` — `sanitize_output()`, `sanitize_agent_trace()`, `clean_response()`
- `backend/middleware/rate_limit.py` — Token bucket rate limiter
- `backend/middleware/error_handlers.py` — Sanitized error responses (no stack traces)
- `backend/routes/auth.py` — JWT minting, verification, refresh rotation, logout, replay detection

**Inputs**: HTTP requests, Firebase ID tokens
**Outputs**: Security headers, sanitized responses, JWT tokens (access + refresh)
**APIs/Services**: Firebase Admin SDK (token verification), PyJWT (token minting)
**Dependencies**: Part 1 (Foundation)
**Risks**: JWT secret exposure, refresh token replay attacks, prompt injection bypass, rate limit misconfiguration
**Deliverables**: 10-gate security pipeline, JWT auth with family rotation and replay detection, prompt firewall, output sanitizer, production-hardened configuration

---

## Part 9 — Routes Engineer

### Simple Explanation
This engineer builds the "doors" — the API endpoints that the mobile app talks to. They connect the chat, auth, and catalog systems together, handle WebSocket connections for real-time streaming, and make sure every request gets routed to the right place.

### Professional Engineering Language
**Responsibility**: REST endpoint definitions (chat, auth, catalog, persona), WebSocket handler with streaming integration, request validation (Pydantic models), response serialization, background task scheduling, multimodal request branching.

**Files/Modules Owned**:
- `backend/routes/chat.py` — `POST /api/chat` (text + multimodal branches), `WS /api/chat/ws` (streaming), persona CRUD endpoints, `ChatRequest`/`ChatResponse` models
- `backend/routes/auth.py` — Session creation, token refresh, logout, current user
- `backend/routes/catalog.py` — Place catalog, search, categories, place detail

**Inputs**: HTTP/WebSocket requests (validated by Pydantic models)
**Outputs**: JSON responses (ChatResponse, auth tokens, catalog data), WebSocket events
**APIs/Services**: LangGraph (chat), Firebase (auth), ChromaDB (catalog search)
**Dependencies**: ALL previous parts (1-8)
**Risks**: Route path conflicts, WebSocket connection leaks, response serialization errors, background task failures
**Deliverables**: Complete REST API surface, WebSocket streaming endpoint, request validation, response serialization, background trip generation trigger

---

## Part 10 — Frontend Engineer

### Simple Explanation
This engineer builds the mobile app that users actually see and touch. They create the chat screen, the itinerary viewer, the search page, and the profile settings. They make it work in both English and Arabic, with smooth animations and a beautiful design.

### Professional Engineering Language
**Responsibility**: React Native/Expo app with file-based routing, tab navigation, bilingual UI (i18next + RTL), AgentTracePanel (real-time agent reasoning display), UI_TRIGGER parsing for native modals, WebSocket client, Firebase Auth integration, place detail modal.

**Files/Modules Owned**:
- `frontend/app/_layout.tsx` — Root layout, Firebase init, i18n init, language detection from persona
- `frontend/app/(tabs)/chat.tsx` — Chat screen with message list, input, AgentTracePanel toggle
- `frontend/app/(tabs)/index.tsx` — Home feed (catalog)
- `frontend/app/(tabs)/search.tsx` — Search screen
- `frontend/app/(tabs)/plan.tsx` — Itinerary/plan viewer
- `frontend/app/(tabs)/profile.tsx` — User profile + persona settings
- `frontend/app/itinerary.tsx` — Full itinerary detail view
- `frontend/app/place.tsx` — Place detail modal
- `frontend/app/onboarding.tsx` — Onboarding flow
- `frontend/components/AgentTracePanel.tsx` — Blurred bottom sheet with agent timeline
- `frontend/components/ScreenHeader.tsx` — Reusable header
- `frontend/services/api.ts` — API client (REST + WebSocket)

**Inputs**: API responses (ChatResponse, catalog data, persona data)
**Outputs**: Rendered UI, user interactions → API calls
**APIs/Services**: Touri REST API, Touri WebSocket, Firebase Auth
**Dependencies**: Part 9 (Routes) — needs complete API surface
**Risks**: WebSocket reconnection handling, RTL layout edge cases, UI_TRIGGER parsing failures, performance with large chat histories
**Deliverables**: 6-screen React Native app, bilingual UI with RTL, AgentTracePanel, UI_TRIGGER modal system, WebSocket streaming integration

---

# SECTION 4 — VISUAL DIAGRAM IDEAS

---

## Diagram 1: System Architecture Overview

**What it should contain**:
- 4 horizontal layers: Foundation (bottom), AI Services (middle), Orchestration (upper-middle), Surface (top)
- Foundation layer: FastAPI box, Firebase box, ChromaDB box, Gemini API box
- AI Services layer: RAG Pipeline box, Memory Service box, LLM Engine box, Security Middleware box
- Orchestration layer: LangGraph box (containing 7 sub-nodes: Memory, Router, Planner, Budget, Concierge, General, Needs Info)
- Surface layer: REST Routes box, WebSocket box, React Native Frontend box

**Arrows**:
- Foundation → AI Services: "provides infrastructure" (upward arrows)
- AI Services → Orchestration: "provides capabilities" (upward arrows)
- Orchestration → Surface: "exposes API" (upward arrows)
- Surface → Orchestration: "user requests" (downward arrows)
- Within Orchestration: Memory→Router→Specialist (left-to-right flow)

**Colors/Theme**:
- Foundation: Slate gray (#475569)
- AI Services: Indigo blue (#4338CA)
- Orchestration: Emerald green (#047857)
- Surface: Teal (#0D9488)
- Background: Dark (#0F172A) with subtle grid
- Text: White (#F8FAFC) for headings, Light gray (#94A3B8) for labels

**Animation Ideas**:
- On load: layers slide in from bottom (Foundation first, then AI, then Orchestration, then Surface)
- On "Request Lifecycle" click: a glowing dot traces the path: Frontend→Routes→Graph→Router→Planner→RAG→LLM→back
- Hover on any box: subtle scale-up + glow + tooltip with description
- Data flow arrows: animated dashed lines with particles flowing in direction

---

## Diagram 2: LangGraph Agent Execution Flow

**What it should contain**:
- 7 nodes arranged as a directed graph (not linear — branching)
- Entry node: "Memory Manager" (leftmost)
- "Router" node (center-left)
- Diamond decision node after Router (5 branches)
- 5 target nodes: Travel Planner, Budget Specialist, Local Concierge, General Chat, Needs Info (right side)
- END node (rightmost)
- Each node shows: agent name, primary tool icon, brief description

**Arrows**:
- Memory → Router: solid arrow, labeled "enriched state"
- Router → Diamond: solid arrow, labeled "intent set"
- Diamond → each specialist: conditional arrows, labeled with intent value
- Each specialist → END: solid arrow, labeled "final state"
- Router → Needs Info (when gaps detected): dashed arrow, labeled "missing fields"

**Colors/Theme**:
- Memory: Purple (#7C3AED)
- Router: Amber (#D97706)
- Decision diamond: White outline
- Travel Planner: Blue (#2563EB)
- Budget Specialist: Green (#059669)
- Local Concierge: Orange (#EA580C)
- General Chat: Gray (#6B7280)
- Needs Info: Red (#DC2626)
- END: Dark gray circle

**Animation Ideas**:
- Live demo mode: show a real message flowing through the graph
- Node activation: each node glows when "active" in the flow
- State preview: clicking a node shows the AgentState JSON at that point
- Streaming simulation: nodes light up sequentially with timing matching real latency

---

## Diagram 3: Memory Lifecycle

**What it should contain**:
- Circular flow with 3 main phases
- Center: Firestore icon (database)
- Phase 1 (top): "Pre-Response" — 4 sub-steps (Load Messages, Load Summary, Load Preferences, Build Context)
- Phase 2 (right): "Agent Execution" — LangGraph icon
- Phase 3 (bottom): "Post-Response" — 5 sub-steps (Save Messages, Extract Preferences, Save Plan, Summarise, Update State)
- Outer ring: "Cross-Session Context" — arrows connecting different session markers

**Arrows**:
- Pre-Response → Agent Execution: "injects memory_context"
- Agent Execution → Post-Response: "returns final state"
- Post-Response → Pre-Response: "next request" (curved arrow around the circle)
- All phases ↔ Firestore: bidirectional arrows (read/write)

**Colors/Theme**:
- Pre-Response: Cool blue (#3B82F6)
- Agent Execution: Warm amber (#F59E0B)
- Post-Response: Emerald (#10B981)
- Firestore: Google Cloud blue (#4285F4)
- Cross-Session ring: Dashed purple (#8B5CF6)

**Animation Ideas**:
- Continuous rotation: the 3-phase cycle rotates slowly
- Data particles: small dots flow from Firestore → Pre-Response, and from Post-Response → Firestore
- Session markers: small circles on the outer ring representing different sessions, connected by dashed lines
- Click on any phase: expands to show detailed sub-steps

---

## Diagram 4: RAG Pipeline

**What it should contain**:
- Two parallel pipelines: Ingestion (top, left→right) and Retrieval (bottom, right→left)
- Ingestion: CSV/XLSX icons → Document Loader (gear icon) → Embedding Model (brain icon) → ChromaDB (database icon)
- Retrieval: User Query (speech bubble) → Embed (same brain icon) → Cosine Search (magnifying glass) → Top-K Results (document stack) → LLM Context (robot icon)
- Sidebar: Embedding Backend Fallback Chain (vertical: Gemini → ST → ONNX)

**Arrows**:
- Ingestion: solid arrows left→right, labeled with data volume
- Retrieval: solid arrows right→left, labeled with latency
- Fallback chain: downward arrows with "on failure" labels

**Colors/Theme**:
- Ingestion: Teal (#14B8A6)
- Retrieval: Indigo (#6366F1)
- ChromaDB: Green (#22C55E) — central, connects both pipelines
- Fallback chain: Amber (#F59E0B) — warning color

**Animation Ideas**:
- Ingestion: documents flow through pipeline, counter increments to 3,723
- Retrieval: query enters, embedding sparkles, search beam scans ChromaDB, results highlight
- Fallback: chain lights up sequentially when triggered
- Relevance scores: appear as percentage badges on results

---

## Diagram 5: Security Defense-in-Depth

**What it should contain**:
- 5 concentric rings (outermost → innermost)
- Ring 1 (outer): Transport Security — HSTS, HTTPS redirect, TLS
- Ring 2: Header Security — CSP, X-Frame-Options, X-Content-Type-Options, Permissions-Policy
- Ring 3: Auth Layer — JWT verification, refresh rotation, replay detection
- Ring 4: Input Validation — Prompt firewall, size limits, UI_TRIGGER stripping
- Ring 5 (center): Application — Touri API
- Each ring shows specific controls as small labeled badges

**Arrows**:
- Incoming request arrow from outside → pierces through all rings → reaches center
- Each ring has a "gate" icon where the arrow passes through
- Outgoing response arrow from center → back through rings (headers added)

**Colors/Theme**:
- Ring 1: Red (#EF4444) — critical
- Ring 2: Orange (#F97316) — high
- Ring 3: Amber (#F59E0B) — medium-high
- Ring 4: Yellow (#EAB308) — medium
- Ring 5: Green (#22C55E) — protected
- Background: Dark (#1E293B)

**Animation Ideas**:
- Rings appear from outside in, building the defense
- Attack simulation: red particles try to penetrate, get blocked at various rings
- Request trace: a green dot successfully navigates all rings
- Click on any ring: expands to show detailed control descriptions

---

## Diagram 6: Frontend/Backend Communication

**What it should contain**:
- Left: iPhone mockup (React Native app)
- Center: Two parallel channels (REST arrow + WebSocket persistent connection)
- Right: Server (FastAPI)
- REST channel: single request→response arrow pair
- WebSocket channel: persistent pipe with multiple event bubbles flowing both ways
- Below: UI_TRIGGER parsing flow (response_text → regex split → JSON.parse → native modal)

**Arrows**:
- REST: solid arrow right (request), solid arrow left (response)
- WebSocket: bidirectional pipe with event labels (typing_indicator, node_start, trace, token_chunk, progressive_object, message_complete)
- UI_TRIGGER: text block → split icon → JSON icon → modal icon

**Colors/Theme**:
- REST: Blue (#3B82F6)
- WebSocket: Purple (#8B5CF6)
- UI_TRIGGER: Green (#10B981)
- iPhone: Dark frame with screen content
- Server: Dark box with FastAPI logo

**Animation Ideas**:
- REST: request arrow flies right, pause, response arrow flies left
- WebSocket: events pulse through the pipe continuously
- UI_TRIGGER: text scrolls, marker highlights, JSON expands, modal pops up
- Latency display: timer showing ms for each channel

---

## Diagram 7: Dependency DAG

**What it should contain**:
- 10 nodes arranged in a directed acyclic graph (DAG)
- P1 at bottom (no incoming edges)
- P2, P3, P4, P8 in row above P1 (each has edge from P1)
- P5 above them (edges from P2, P3, P4)
- P6, P7 above P5 (P6: edges from P3, P4, P5; P7: edges from P2, P3, P4, P5)
- P9 above all (edges from P1-P8)
- P10 at top (edge from P9)
- Critical path highlighted: P1→P3→P5→P6→P9→P10

**Arrows**:
- Dependency arrows: "depends on" (pointing downward)
- Critical path: thicker, red arrows
- Parallel groups: dashed boundary boxes around {P2,P3,P4,P8} and {P6,P7}

**Colors/Theme**:
- Critical path nodes: Red border
- Parallel group 1: Blue dashed boundary
- Parallel group 2: Green dashed boundary
- Other nodes: Gray
- Background: White or light gray

**Animation Ideas**:
- Build order simulation: nodes appear in dependency order (P1 first, then parallel group, etc.)
- Critical path pulse: red glow travels up the critical path
- Click on any node: shows its dependencies and dependents
- Timeline sync: clicking a node highlights its position on the Gantt chart
