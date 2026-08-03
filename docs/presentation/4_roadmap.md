# Touri — Execution Roadmap (Part 4)

---

# SECTION 5 — EXECUTION ROADMAP

---

## Build Order (Dependency-Driven)

The build order follows the dependency DAG strictly. Nothing is built before its dependencies are ready.

```
Phase 1 (Week 1-2): Foundation + LLM + Security
    │
    ├── P1: Foundation (FastAPI, Firebase, ChromaDB, config)
    ├── P4: LLM (Gemini/Gemma integration, system instruction)
    └── P8: Security (middleware stack, JWT auth)
    
Phase 2 (Week 3-4): RAG + Memory
    │
    ├── P2: RAG (document ingestion, vector store, query)
    └── P3: Memory (message persistence, preferences, summaries)

Phase 3 (Week 5-6): Graph & State + Router
    │
    ├── P5: Graph & State (LangGraph wiring, AgentState, ExecutionEngine)
    └── P6: Router (intent detection, gap analysis, follow-up questions)

Phase 4 (Week 7-8): Agents
    │
    └── P7: Agents (Travel Planner, Budget Specialist, Local Concierge, General Chat)

Phase 5 (Week 9-10): Routes + Integration
    │
    └── P9: Routes (REST endpoints, WebSocket, request/response models)

Phase 6 (Week 11): Frontend
    │
    └── P10: Frontend (React Native screens, AgentTracePanel, UI_TRIGGER)

Phase 7 (Week 12): Polish + Deploy
    │
    └── Load testing, security audit, production deploy
```

---

## Milestones

| Milestone | Week | Criteria | Verification |
|-----------|------|----------|-------------|
| M1: Server Alive | 2 | FastAPI boots, all services verified at startup, health check returns 200 | `curl /` returns `{"name":"Touri","phase":2}` |
| M2: RAG Ready | 4 | ChromaDB collection has 3,723+ docs, `query("Pyramids")` returns relevant results with relevance >0.5 | Run `check_backend.py` |
| M3: Memory Working | 4 | Messages persist to Firestore, preferences extracted, summary generated at 30+ messages | Check Firestore console |
| M4: LLM Responding | 2 | `generate_text("Hello")` returns coherent response in correct language | Unit test |
| M5: Graph Compiles | 6 | `build_graph()` returns compiled graph, `run_chat()` completes without error | Integration test |
| M6: Router Classifies | 6 | 95%+ accuracy on intent classification test set (100 labeled messages) | Test suite |
| M7: Agents Produce JSON | 8 | All 4 agents return valid structured JSON for their respective intents | Agent-specific tests |
| M8: Full Lifecycle | 10 | `POST /api/chat` with "Plan a 5-day trip to Luxor" returns complete ChatResponse with itinerary | E2E test |
| M9: WebSocket Streams | 10 | WebSocket connection receives typing_indicator, node_start, trace, progressive_object, message_complete | Manual + automated |
| M10: Frontend Renders | 11 | All 6 screens render, chat sends and receives, AgentTracePanel shows timeline | Manual QA |
| M11: Production Deploy | 12 | App deployed, load tested at 100 concurrent users, security audit passed | Deploy checklist |

---

## Weekly Sprint Plan

### Sprint 1 (Week 1-2): Foundation Sprint

**Goal**: Bootable server with all services connected.

| Day | P1 (Foundation) | P4 (LLM) | P8 (Security) |
|-----|-----------------|----------|---------------|
| 1-2 | Project structure, `config.py` with Pydantic Settings, `.env` loading | Research Gemini/Gemma models, API key setup | Research security best practices for FastAPI |
| 3-4 | `main.py` with FastAPI app factory, lifespan handler, CORS | `get_llm()` LangChain wrapper, `get_gemini_model()` native SDK | `SecurityHeadersMiddleware`, `HTTPSRedirectMiddleware` |
| 5-6 | ChromaDB client setup, Firebase Admin SDK setup | `GLOBAL_SYSTEM_INSTRUCTION`, `detect_language()`, `lang_directive()` | `RequestSizeLimitMiddleware`, `RequestTimeoutMiddleware` |
| 7-8 | Health check endpoint, startup verification of all services | `clean_response()`, `safe_extract_text()`, bilingual helpers | JWT helpers, `install_security_middleware()` |
| 9-10 | Integration: wire all services together, test boot | Unit tests for LLM functions, test bilingual detection | Auth endpoints: session, refresh, logout, me |

**Deliverables**: Bootable server, LLM responding, security middleware active, auth endpoints working.

---

### Sprint 2 (Week 3-4): Data Sprint

**Goal**: RAG queryable, Memory persisting.

| Day | P2 (RAG) | P3 (Memory) |
|-----|----------|-------------|
| 1-2 | `document_loader.py`: CSV/XLSX parser, Document model | Firestore schema design: messages, summaries, preferences |
| 3-4 | `vector_store.py`: ChromaDB collection, embedding function factory | `save_message()` with dedup, `get_recent_messages()` |
| 5-6 | `ingest_egypt_dataset()`: batch ingestion, auto-retry on 429 | `get/save_conversation_summary()`, `get/update_travel_preferences()` |
| 7-8 | `query()` with domain filtering, relevance scoring | `load_memory_context()`, `format_memory_for_prompt()` |
| 9-10 | Embedding backend fallback chain, integration tests | `memory_manager.py`: `load_memory_into_state()`, `persist_exchange()`, `maybe_summarise()` |

**Deliverables**: RAG returns verified results, Memory persists and loads context, auto-summarisation works.

---

### Sprint 3 (Week 5-6): Orchestration Sprint

**Goal**: Graph compiles, Router classifies correctly.

| Day | P5 (Graph & State) | P6 (Router) |
|-----|---------------------|-------------|
| 1-2 | `AgentState` TypedDict, `AgentStep`, `Intent` types, `fresh_state()` | `_heuristic_intent()`: regex patterns for EN + AR |
| 3-4 | `build_graph()`: StateGraph with 7 nodes, edges, conditional edges | `_llm_intent()`: LLM classification with persona context |
| 5-6 | `run_chat()`: non-streaming invocation with ExecutionEngine | `_detect_gaps()`: cross-reference message + persona + prefs + history |
| 7-8 | `stream_chat()`: async generator, node labels, status messages | `_build_followup()`: bilingual question generation |
| 9-10 | Integration: graph compiles, runs end-to-end with mock agents | `route()` node: full pipeline with persona load, firewall, gap detection |

**Deliverables**: Compiled graph, Router with 95%+ intent accuracy, gap detection working, follow-up questions generated.

---

### Sprint 4 (Week 7-8): Agents Sprint

**Goal**: All 4 agents produce structured JSON.

| Day | Travel Planner | Budget Specialist | Local Concierge | General Chat |
|-----|---------------|-------------------|-----------------|--------------|
| 1-2 | `_gather_context()`: parallel ChromaDB queries | `_BUDGET_HEURISTICS`: 3 brackets | `_ALLERGEN_KEYWORDS`: 4 categories | Basic chat handler |
| 3-4 | Prompt template (EN + AR), JSON schema | Parallel ChromaDB pricing queries | `_gather()`: allergen-filtered retrieval | Off-topic redirection |
| 5-6 | `_extract_json()`, modify-mode addendum | Prompt template, JSON schema | Prompt template with SPOTS_JSON split | Integration with graph |
| 7-8 | `plan()` node: full pipeline | `calculate()` node: full pipeline | `recommend()` node: halal enforcement | Testing |
| 9-10 | UI_TRIGGER injection, suggestions, tests | UI_TRIGGER injection, suggestions, tests | UI_TRIGGER injection, suggestions, tests | Tests |

**Deliverables**: 4 agent nodes, each producing valid structured JSON with UI_TRIGGER injection.

---

### Sprint 5 (Week 9-10): Integration Sprint

**Goal**: Full request lifecycle working end-to-end.

| Day | P9 (Routes) |
|-----|-------------|
| 1-2 | `ChatRequest`/`ChatResponse` Pydantic models |
| 3-4 | `POST /api/chat`: text branch (LangGraph), multimodal branch (Gemini native) |
| 5-6 | `WS /api/chat/ws`: WebSocket handler with streaming events |
| 7-8 | Persona CRUD endpoints, catalog endpoints |
| 9-10 | End-to-end tests: full lifecycle for each intent, WebSocket streaming tests |

**Deliverables**: Complete API surface, all endpoints tested, WebSocket streaming working.

---

### Sprint 6 (Week 11): Frontend Sprint

**Goal**: All screens render, chat works end-to-end.

| Day | P10 (Frontend) |
|-----|----------------|
| 1-2 | Expo Router setup, tab navigation, Firebase init, i18n setup |
| 3-4 | Chat screen: message list, input, API client integration |
| 5-6 | AgentTracePanel: bottom sheet with timeline, streaming event handling |
| 7-8 | UI_TRIGGER parsing: modal system for plan/budget/spots confirmation |
| 9-10 | Remaining screens: Home, Search, Plan, Profile, Place detail, Onboarding |

**Deliverables**: 6-screen React Native app, bilingual UI, AgentTracePanel, UI_TRIGGER modals.

---

### Sprint 7 (Week 12): Polish & Deploy Sprint

**Goal**: Production-ready deployment.

| Day | Activity | Owner |
|-----|----------|-------|
| 1-2 | Load testing: 100 concurrent users, measure latency percentiles | P1 + P9 |
| 3-4 | Security audit: OWASP Top 10 check, dependency scan, secret scan | P8 |
| 5-6 | Bug fixes from testing, performance optimization | All |
| 7-8 | Documentation: API docs, deployment guide, runbooks | P1 + P9 |
| 9-10 | Production deploy, monitoring setup, on-call rotation | P1 + P8 |

**Deliverables**: Production deployment, load test report, security audit report, documentation.

---

## Critical Blockers

| Blocker | Impact | Mitigation | Owner |
|---------|--------|------------|-------|
| Gemini API key not provisioned | Blocks P4 (LLM), P2 (RAG embeddings) | Request key day 0. Fallback: local SentenceTransformers for embeddings, open-source model for LLM | P4 |
| Firebase service account not configured | Blocks P3 (Memory), P8 (Auth) | Request service account day 0. Fallback: in-memory stores for development | P1 |
| ChromaDB embedding model incompatible with target OS | Blocks P2 (RAG) | Auto-detect OS, fallback to ONNX MiniLM (always works) | P2 |
| LangGraph version incompatibility with LangChain | Blocks P5 (Graph) | Pin versions in `requirements.txt`, test in CI before merging | P5 |
| Firestore free-tier quota exceeded during testing | Blocks P3 (Memory) | Use in-memory fallback for dev, batch test writes, monitor quota | P3 |
| iOS/Android build issues with Expo | Blocks P10 (Frontend) | Test on both platforms from week 11 day 1, use Expo EAS Build | P10 |

---

## Parallelizable Tasks

### Can Run Simultaneously (no shared dependencies):

| Group | Parts | When |
|-------|-------|------|
| Group A | P1, P4, P8 | Weeks 1-2 |
| Group B | P2, P3 | Weeks 3-4 |
| Group C | P7 (all 4 agents) | Weeks 7-8 |

### Must Run Sequentially:

| Sequence | Parts | Why |
|----------|-------|-----|
| Foundation → RAG/Memory/LLM/Security | P1 → P2,P3,P4,P8 | Infrastructure must exist first |
| RAG+Memory+LLM → Graph | P2,P3,P4 → P5 | Graph imports from all three |
| Graph → Router | P5 → P6 | Router is a graph node |
| Graph+Router → Agents | P5,P6 → P7 | Agents are graph nodes |
| All → Routes | P1-P8 → P9 | Routes wire everything |
| Routes → Frontend | P9 → P10 | Frontend consumes API |

---

## Testing Stages

### Stage 1: Unit Tests (per part, continuous)

| Part | Test Focus | Tools |
|------|-----------|-------|
| P1 | Config loading, service connections, health check | pytest, pytest-asyncio |
| P2 | Document loading, embedding, query relevance, fallback chain | pytest, ChromaDB test collection |
| P3 | Message CRUD, preference extraction, summarisation, context assembly | pytest, Firestore emulator |
| P4 | Language detection, response cleaning, system instruction compliance | pytest |
| P5 | Graph compilation, state flow, conditional routing, streaming events | pytest, LangGraph test utilities |
| P6 | Intent classification accuracy, gap detection, follow-up generation | pytest, labeled test set |
| P7 | JSON output validity, schema compliance, allergen filtering, halal enforcement | pytest, JSON Schema validation |
| P8 | Header injection, JWT lifecycle, firewall detection, sanitization | pytest, httpx |
| P9 | Endpoint responses, validation errors, WebSocket events | pytest, httpx, websockets |
| P10 | Component rendering, navigation, i18n, UI_TRIGGER parsing | Jest, React Native Testing Library |

### Stage 2: Integration Tests (cross-part, weeks 9-10)

- Memory → Router → Planner: full graph execution with real Firestore + ChromaDB
- Auth → Chat: authenticated request lifecycle
- WebSocket: connection, streaming events, disconnection handling
- Multimodal: image upload → Gemini processing → response

### Stage 3: End-to-End Tests (full system, week 10-11)

- "Plan a 5-day trip to Luxor" → complete ChatResponse with valid itinerary
- "What's the budget for Cairo?" → complete budget_breakdown
- "Recommend restaurants in Alexandria" → allergen-filtered spots
- Arabic query → Arabic response with correct RAG grounding
- Session continuity: message in session 1, context available in session 2

### Stage 4: Load Tests (week 12)

- 100 concurrent WebSocket connections
- 50 req/s to `/api/chat`
- Measure: p50, p95, p99 latency
- Measure: error rate under load
- Measure: Firestore read/write latency under load

### Stage 5: Security Tests (week 12)

- OWASP Top 10 automated scan
- Prompt injection test suite (50+ known injection patterns)
- JWT replay attack simulation
- Rate limit enforcement verification
- Dependency vulnerability scan (`pip-audit`, `npm audit`)

---

## Deployment Stages

### Stage 1: Development (local, weeks 1-10)
- FastAPI: `uvicorn main:app --reload`
- ChromaDB: local PersistentClient
- Firestore: emulator or dev project
- Frontend: `npx expo start`

### Stage 2: Staging (cloud, week 11)
- FastAPI: Google Cloud Run or Railway
- ChromaDB: persistent volume
- Firestore: staging project
- Frontend: Expo EAS Update (staging channel)
- CI/CD: GitHub Actions on merge to `staging`

### Stage 3: Production (cloud, week 12)
- FastAPI: Google Cloud Run (min 2 instances, auto-scale)
- ChromaDB: persistent volume with backups
- Firestore: production project with backups
- Frontend: App Store + Google Play via Expo EAS Submit
- Monitoring: Sentry for errors, Cloud Monitoring for infra
- CI/CD: GitHub Actions on merge to `main` (with approval gate)

### Rollback Plan:
- Backend: Cloud Run revisions — instant rollback to previous revision
- Frontend: Expo EAS Update — revert to previous update
- Database: Firestore backups — point-in-time recovery
- ChromaDB: volume snapshots — restore previous snapshot
