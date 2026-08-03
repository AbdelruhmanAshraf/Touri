# Touri — System Architecture Presentation (Part 2: Flows & Diagrams)

---

## SLIDE 15 — AI Pipeline Flow

**Title**: The AI Pipeline — From Query to Structured Response
**Key Points** (10 stages):
1. **Language Detection**: Arabic character ratio >30% → AR mode for entire pipeline
2. **Memory Context Assembly**: Firestore → recent messages + conversation summary + travel preferences + key facts
3. **Intent Classification**: Regex heuristics (microseconds) → LLM fallback (with persona context)
4. **Gap Detection**: Cross-reference message + persona + stored prefs + chat history for missing fields
5. **RAG Retrieval**: Parallel ChromaDB queries by domain (attractions, hotels, restaurants, medical, events)
6. **Allergen/Dietary Filtering**: Post-retrieval keyword matching — strip unsafe results before LLM sees them
7. **Prompt Assembly**: System instruction + persona summary + memory context + RAG context + user message
8. **LLM Inference**: Gemma-4-26B-A4B-IT, temperature 0.4, streaming=False for structured output
9. **Response Parsing**: JSON extraction from code fences, thinking trace removal, markdown stripping
10. **UI Trigger Injection**: `---UI_TRIGGER---` marker + JSON payload for frontend modal sync

**Visual**: Vertical pipeline, 10 stages. Input→Processing→Output at each stage. Color gradient cool→warm.

---

## SLIDE 16 — LangGraph Orchestration Deep Dive

**Title**: LangGraph — State Machine Meets AI Agents
**Key Points**:
- `StateGraph(AgentState)` compiled once, cached with `@lru_cache(maxsize=1)`
- `set_entry_point("memory")` — always load context first
- `add_edge("memory", "router")` — deterministic transition
- `add_conditional_edges("router", _branch, {...})` — pure function maps intent→node
- Each specialist → END (no cycles in current architecture)
- `graph.astream(state, stream_mode="updates")` — yields per-node events
- Streaming events: `node_start` (label + status_msg), `trace` (agent steps), `node_end` (partial state), `final` (complete state)
- Governorate-branded: `[🧠 Cairo] Building your travel itinerary...`

**Visual**: Animated graph execution. State enters memory→enriched→router→intent set→conditional edge→planner→RAG→LLM→itinerary→END. Show state delta at each transition.

---

## SLIDE 17 — State Management Flow

**Title**: AgentState — The Single Source of Truth
**Key Points**:
- `AgentState` is a TypedDict with 25+ fields, threaded through every node
- **Input fields**: user_id, session_id, user_message, language
- **Derived fields**: intent, active_agent, user_persona, is_modify
- **Context fields**: memory_context, travel_preferences, chat_history, rag_context, web_context
- **Output fields**: response_text, itinerary, budget_breakdown, spots_json, suggestions
- **Observability**: agent_trace (List[AgentStep] — agent, action, tool, reasoning, result, timestamp)
- **State machine fields**: conversation_state, requirements_status, structured_questions

**State accumulation by node**:
| Node | Fields Added/Modified |
|------|----------------------|
| Memory | +memory_context, +travel_preferences, +chat_history, +conversation_state |
| Router | +intent, +active_agent, +user_persona, +structured_questions, +requirements_status |
| Planner | +itinerary, +rag_context, +response_text, +suggestions |
| Budget | +budget_breakdown, +response_text, +suggestions |
| Concierge | +spots_json, +rag_context, +response_text, +suggestions |

**Visual**: State accumulator — growing JSON object. At each node, highlight modified fields.

---

## SLIDE 18 — Memory Lifecycle

**Title**: Memory Lifecycle — Pre-Response → Post-Response → Cross-Session

**Phase 1 — Pre-Response (load_memory_into_state)**:
1. Load recent messages (last 20) from Firestore `users/{uid}/chats/{sid}/messages`
2. Load conversation summary from `users/{uid}/memory/conversation_summary`
3. Load travel preferences from `users/{uid}/travel_preferences/prefs`
4. Build key facts: favorite cities, dislikes, dietary, allergies, hotel prefs, transport prefs, travel style, spending behavior, rejected recommendations
5. Build previous plans summary from `generated_plans[-3:]`
6. If current session has <4 messages, load cross-session messages
7. Format for prompt injection with "DO NOT RE-ASK" directive
8. Load conversation state machine, increment turn counter

**Phase 2 — Post-Response (persist_exchange)**:
1. Save user message with content_hash dedup
2. Save assistant response (truncated at 10k chars)
3. Extract preferences from exchange (keyword + pattern matching)
4. Save generated plan reference if itinerary was created
5. Auto-summarise if session >30 messages
6. Update conversation state machine (transition based on intent)
7. Periodic stale session cleanup (every ~50 exchanges)

**Phase 3 — Cross-Session**:
- When new session has <4 messages, inject messages from previous sessions
- Ensures continuity: "From previous conversations: [User]: I prefer boutique hotels..."

**Visual**: Circular lifecycle: Pre-Response → Agent Execution → Post-Response → (next request) Pre-Response. Firestore icon center.

---

## SLIDE 19 — RAG Retrieval Lifecycle

**Title**: RAG Lifecycle — Ingest → Store → Retrieve → Ground

**Ingestion Phase**:
1. Source: CSV/XLSX files in `backend/data/egypt_csv/`
2. Document Loader: parse into `Document(id, text, metadata{domain, country, file, type})`
3. Embedding: auto-select backend (Gemini text-embedding-004 → SentenceTransformers paraphrase-multilingual-MiniLM-L12-v2 → Chroma ONNX MiniLM)
4. Batch upsert: 50 docs/batch into ChromaDB PersistentClient
5. Collection: `egypt_travel_knowledge` at `backend/data/chroma_db/`
6. Metadata: domain, version, embedding_model stored on collection

**Retrieval Phase**:
1. Query text → embed with same model
2. Cosine similarity search with optional `where` filter (domain, country)
3. Top-K results with distance scores
4. Relevance mapping: `relevance = max(0, 1 - distance/2)` → [0,1]
5. Filter: only include results with distance < 0.8
6. Format with source attribution: `[Source: luxor_attractions.csv]\n{doc_text}`
7. Inject into LLM prompt with instruction: "use this; do not invent facts"

**Embedding Backend Fallback Chain**:
```
Gemini text-embedding-004 (multilingual, cloud)
  ↓ fails (no API key / quota)
SentenceTransformers (multilingual, local, needs torch)
  ↓ fails (Intel Mac / no torch)
Chroma ONNX MiniLM (English-only, always works)
```

**Visual**: Two-directional pipeline. Left→right: Ingestion. Right→left: Retrieval. Fallback chain as vertical sidebar.

---

## SLIDE 20 — Agent Execution Lifecycle

**Title**: Agent Execution — Retry, Recovery, Fallback

**ExecutionEngine.execute_with_recovery()**:
```
1. Start timer
2. Log: [TRACE] Executing {agent_name} (Attempt {n})
3. Call agent_func(state) — async
4. On success:
   - Log latency: [TRACE] {agent_name} completed in {t}s
   - Append telemetry to state.metadata.latency_ms
   - Return enriched state
5. On failure:
   - Increment retry counter
   - Log: [WARN] Partial failure in {agent_name}: {error}
   - If retries < max_retries (3): sleep 1s, goto 2
   - If retries exhausted:
     - Log: [ERROR] Agent {agent_name} failed after {max} retries
     - Append error to state.errors
     - Set state.response_text = "Failed to complete step. Switching to fallback."
     - Return degraded state
```

**OfflineFallback.get_fallback_itinerary(destination)**:
- Returns pre-cached static itinerary for major destinations (Cairo, Luxor, Alexandria, Aswan, Hurghada)
- Used when Travel Planner fails after all retries
- Ensures user never sees a crash or 500 error

**WebSocket path**:
- On agent exception: stream fallback data via WebSocketStreamer instead of crashing connection
- Progressive object streaming with structured JSON

**Visual**: State machine: Start→Execute→Success? Yes→Return+telemetry. No→Retries<Max? Yes→Backoff→Execute. No→Log error→Inject fallback→Return degraded.

---

## SLIDE 21 — Security Layer Flow

**Title**: Security Flow — Every Request, Every Layer

**10 Security Gates (in order)**:

| # | Gate | What It Does | On Failure |
|---|------|-------------|------------|
| 1 | RequestTimeoutMiddleware | Logs requests >120s | Warning only (uvicorn enforces actual timeout) |
| 2 | RequestSizeLimitMiddleware | Rejects bodies >25MB | 413 Payload Too Large |
| 3 | SecurityHeadersMiddleware | Injects HSTS, CSP, X-Frame-Options, etc. | Always applied |
| 4 | HTTPSRedirectMiddleware | 301 redirect HTTP→HTTPS (production only) | Redirect |
| 5 | CORS Middleware | Validates Origin against whitelist | Block request |
| 6 | Rate Limiter | Token bucket: auth 5/min, chat configurable | 429 Too Many Requests |
| 7 | Auth Dependency | Verify JWT (cookie or Bearer) → check revocation → extract user_id | 401 Unauthorized |
| 8 | Route Handler | Strip UI_TRIGGER from input, validate message ≤10k chars, attachment ≤20MB | 400 Bad Request |
| 9 | Prompt Firewall | Regex + heuristic injection detection before LLM | Block, return safe guidance |
| 10 | Output Sanitizer | Clean response text, sanitize trace, remove server headers | Always applied |

**Auth Token Flow**:
1. Client signs in with Firebase → gets Firebase ID token
2. POSTs to `/api/auth/session` with ID token
3. Server verifies ID token with Firebase Admin SDK (NEVER trusts client user_id)
4. Server mints: `touri_access` (60min) + `touri_refresh` (30 days, family rotation)
5. Both set as HttpOnly, Secure, SameSite=Lax cookies
6. Access token also returned in JSON body for mobile SecureStore
7. Refresh rotates both tokens with replay detection (revoke entire family on mismatch)

**Visual**: Vertical stack of 10 gates. Animated request flowing down. Auth flow as side panel.

---

## SLIDE 22 — Frontend/Backend Communication

**Title**: Client-Server Communication — REST + WebSocket

**REST Flow** (`POST /api/chat`):
```
Client                          Server
  |                               |
  |-- POST {message, session_id}-->|
  |   Authorization: Bearer <jwt>  |
  |                               |-- Verify JWT
  |                               |-- LangGraph execution
  |                               |-- Sanitize output
  |<-- ChatResponse JSON ---------|
  |   {message, agent, intent,    |
  |    itinerary, budget, spots,  |
  |    suggestions, agent_trace}  |
```

**WebSocket Flow** (`WS /api/chat/ws`):
```
Client                          Server
  |                               |
  |== WebSocket Connect ==========>|
  |                               |-- Accept
  |-- {user_id, message} -------->|
  |<-- {type: "typing_indicator", |
  |     status: "active"} --------|
  |<-- {type: "node_start",       |
  |     node: "router",           |
  |     label: "Router Agent",    |
  |     status_msg: "Analyzing..."}|
  |<-- {type: "trace", step: {...}}|
  |<-- {type: "token_chunk",      |
  |     content: "I'm generating.."}|
  |<-- {type: "progressive_object",|
  |     object_type: "TripPlan",  |
  |     data: {...}} -------------|
  |<-- {type: "message_complete", |
  |     session_id: "..."} -------|
```

**UI_TRIGGER Parsing**:
```
response_text = "Here's your plan!\n\n---UI_TRIGGER---\n{\"ui_trigger\":\"show_popup\",\"type\":\"plan\",\"payload\":{...}}"

Frontend:
1. Check for "---UI_TRIGGER---" marker
2. Split text: display_part | trigger_json
3. JSON.parse(trigger_json)
4. If ui_trigger === "show_popup" && type === "plan":
   → Show native itinerary confirmation modal
5. If type === "budget":
   → Show budget breakdown modal
6. If type === "spots":
   → Show "Save these spots?" modal
```

**Visual**: Split diagram. Left: REST (single arrow). Right: WebSocket (persistent, multiple events). Bottom: UI_TRIGGER parsing flow.

---

## SLIDE 23 — Dependency Graph

**Title**: Build Order & Dependencies

```
                    ┌──────────┐
                    │ P10      │
                    │ Frontend │
                    └────┬─────┘
                         │ depends on
                    ┌────┴─────┐
                    │ P9       │
                    │ Routes   │
                    └────┬─────┘
                         │ depends on ALL below
        ┌───────────┬────┴─────┬───────────┐
        │           │          │           │
   ┌────┴────┐ ┌────┴────┐ ┌───┴────┐ ┌───┴────┐
   │ P6      │ │ P7      │ │ P5     │ │ P8     │
   │ Router  │ │ Agents  │ │ Graph  │ │Security│
   └────┬────┘ └───┬──┬──┘ └──┬──┬──┘ └───┬────┘
        │          │  │       │  │        │
        └──────────┴──┼───────┘  │        │
                      │          │        │
           ┌──────────┴──────────┴────────┴───┐
           │          │          │            │
      ┌────┴────┐ ┌───┴───┐ ┌───┴───┐   ┌───┴────┐
      │ P2      │ │ P3    │ │ P4    │   │ P1     │
      │ RAG     │ │ Memory│ │ LLM   │   │ Found. │
      └────┬────┘ └───┬───┘ └───┬───┘   └────────┘
           │          │         │
           └──────────┴─────────┘
                      │
                 depends on
                      │
                 ┌────┴────┐
                 │ P1      │
                 │ Found.  │
                 └─────────┘
```

**Critical Path** (highlighted): P1 → P3 → P5 → P6 → P9 → P10
**Parallelizable**: P2, P3, P4, P8 (all depend only on P1)

---

## SLIDE 24 — Execution Roadmap

**Title**: 12-Week Execution Plan

| Week | Part(s) | Activity | Parallel? |
|------|---------|----------|-----------|
| 1-2 | P1, P4, P8 | Foundation setup, LLM integration, Security middleware | Yes (3 engineers) |
| 3-4 | P2, P3 | RAG ingestion pipeline, Memory service + Firestore schema | Yes (2 engineers) |
| 5-6 | P5, P6 | LangGraph wiring, Router agent with intent detection | Sequential (P5→P6) |
| 7-8 | P7 | All 4 agents: Planner, Budget, Concierge, General | Yes (4 engineers) |
| 9-10 | P9 | Routes integration, end-to-end testing, WebSocket streaming | 1-2 engineers |
| 11 | P10 | Frontend core screens, AgentTracePanel, UI_TRIGGER handling | 2 engineers |
| 12 | All | Polish, load testing, security audit, deploy | Full team |

**Milestones**:
- Week 2: FastAPI boots, ChromaDB connected, Gemini responding
- Week 4: RAG returns verified results, Memory persists and loads
- Week 6: Graph compiles, Router classifies correctly
- Week 8: All 4 agents produce structured JSON
- Week 10: Full request lifecycle working end-to-end
- Week 12: Production deploy

**Critical Blockers**:
1. Gemini API key availability (mitigation: fallback models)
2. Firebase service account setup (mitigation: in-memory fallback)
3. ChromaDB embedding model compatibility on target OS (mitigation: ONNX fallback)

---

## SLIDE 25 — Why This Architecture Wins

**Title**: Competitive Moat — Why Touri is Defensible

**1. Verified Data Moat**
- 3,723+ manually curated Egypt documents — not scraped, not generated
- Competitors can't replicate without years of curation
- Each document has verified source attribution

**2. Multi-Agent > Single-LLM**
- Specialized agents outperform general-purpose models on domain tasks
- Travel Planner: 4 parallel RAG queries, structured JSON output
- Budget Specialist: heuristic pricing models as fallback
- Local Concierge: allergen filtering, halal enforcement
- Router: smart gap detection prevents hallucination

**3. Memory = Retention**
- Users who don't repeat themselves stay longer
- Cross-session continuity builds trust
- Auto-extracted preferences improve over time
- "DO NOT RE-ASK" directive prevents annoying repetition

**4. Bilingual Native**
- 400M+ Arabic speakers underserved by travel AI
- Full EN/AR support at every layer: embeddings, prompts, UI, RTL layout
- Language auto-detection from message content

**5. Production-Ready from Day 1**
- Defense-in-depth security (10 gates)
- ExecutionEngine with retry/recovery
- Offline fallback for every critical path
- Graceful degradation at every layer

**6. Future Scaling Vision**
- Add new countries by ingesting new CSVs (same pipeline)
- Add new agents by registering in graph (same orchestration)
- Horizontal scaling: Redis for token store, multiple ChromaDB instances
- Multi-modal expansion: voice-guided tours, AR navigation, real-time translation
