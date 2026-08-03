# Touri — Master Presentation Generation Prompt

> Copy everything between the triple dashes and paste into:
> Gamma.app / Tome / Beautiful.ai / ChatGPT / Claude / Canva AI / any slide generator

---

```
Create a professional, world-class startup engineering presentation for an AI travel platform called "Touri".

The presentation must feel like:
- A YC Demo Day pitch combined with an Apple keynote
- Clean, dark-themed (deep teal #0D9488 → navy #0F172A gradient backgrounds)
- Easy enough for beginners to understand, technical enough for senior engineers
- Enterprise architecture review quality

Use this EXACT design system:
- Background: Dark (#0F172A) with subtle dot-grid pattern
- Primary accent: Teal (#0D9488)
- Secondary accent: Emerald (#10B981)
- Danger/Security: Red (#EF4444)
- Warning/Router: Amber (#F59E0B)
- LLM/AI: Indigo (#6366F1)
- Memory: Purple (#7C3AED)
- Agents: Green (#059669)
- Text: White (#F8FAFC) headings, Light gray (#94A3B8) body
- Font: SF Pro Display or Inter — clean, modern, no serifs
- Every slide: full-bleed dark background, minimal text, strong visuals

---

SLIDE 1 — TITLE
Title: "Touri"
Subtitle: "Multi-Agent AI Travel Concierge for Egypt"
Tag: "Production-Grade RAG + LangGraph + Persistent Memory"
Visual: Large centered pharaonic eye + compass icon in teal glow. "YC Startup Engineering Review" badge top-right corner. Animated particle trail behind logo.
Speaker note: "Not a prototype. Not a chatbot. A production AI system engineered for the real world."

---

SLIDE 2 — THE PROBLEM
Title: "Why Generic AI Fails at Travel"
Visual: Split screen — LEFT: ChatGPT response with red X marks on hallucinated hotel names, fake prices, invented attractions. RIGHT: Touri response with green checkmarks on every verified fact.
5 bullet points (one appears at a time):
1. LLMs hallucinate travel facts, prices, and hotel names
2. No AI remembers users between conversations
3. Egypt tourism data is scattered across 100+ fragmented sources
4. Arabic-language travel AI is virtually non-existent
5. Existing solutions are either stale databases or ungrounded chatbots
Speaker note: "Ask ChatGPT for a Cairo itinerary — it invents everything. Travel AI needs verified, persistent, reasoning intelligence."

---

SLIDE 3 — THE SOLUTION
Title: "Touri Architecture: 10 Engineering Parts"
Visual: Layered architecture diagram with 4 horizontal layers stacked bottom to top:
- LAYER 1 (Bottom, slate gray): "Foundation" — FastAPI + Firebase + ChromaDB + Gemini API
- LAYER 2 (Indigo blue): "AI Services" — RAG Pipeline | Memory System | LLM Engine | Security
- LAYER 3 (Emerald green): "Orchestration" — LangGraph Graph + Router + 4 Specialist Agents
- LAYER 4 (Top, teal): "Surface" — REST API + WebSocket + React Native App
Upward arrows connecting each layer. System title "Touri" floats in center.

---

SLIDE 4 — FOUNDATION (Part 1)
Title: "Foundation — The Bedrock"
Visual: 4 connection boxes around a central FastAPI hexagon:
- Firebase (top-right, blue): "Auth + Firestore persistence"
- ChromaDB (bottom-right, green): "Vector store for 3,723+ docs"
- Gemini API (top-left, indigo): "LLM inference"
- SentenceTransformers (bottom-left, purple): "Multilingual embeddings EN+AR"
Key callout box: "Graceful degradation at every connection — app never crashes if one service is down"
Files owned: backend/main.py | backend/config.py | backend/clients.py

---

SLIDE 5 — RAG PIPELINE (Part 2)
Title: "RAG — Verified Egypt Knowledge at Query Time"
Visual: Dual horizontal pipeline diagram:
TOP ROW (Ingestion, teal arrows →):
[CSV/XLSX Files] → [Document Loader] → [Embedding Model] → [ChromaDB Collection]
Label above: "3,723+ verified documents — attractions, hotels, restaurants, medical, events"

BOTTOM ROW (Retrieval, indigo arrows ←):
[User Query] → [Embed] → [Cosine Search] → [Top-K Results] → [LLM Context]
Label above: "Multilingual: same documents match 'Pyramids' AND 'الأهرامات'"

RIGHT SIDEBAR: Embedding Fallback Chain:
1. Gemini text-embedding-004 (preferred, multilingual)
2. SentenceTransformers (local, multilingual)
3. ONNX MiniLM (always works)
Files owned: backend/rag/vector_store.py | backend/rag/document_loader.py

---

SLIDE 6 — MEMORY SYSTEM (Part 3)
Title: "Memory — The User Never Repeats Themselves"
Visual: Circular lifecycle with 3 colored phases around a Firestore icon:
- Phase 1 (blue, top): "PRE-RESPONSE" — Load messages, load summary, load preferences, build key facts
- Phase 2 (amber, right): "AGENT EXECUTION" — LangGraph processes request
- Phase 3 (green, bottom): "POST-RESPONSE" — Save messages, extract preferences, summarise, cleanup
Outer ring (dashed purple): "Cross-Session Context — session 2 knows what was said in session 1"
Big callout: 🚫 "DO NOT RE-ASK" directive injected into every LLM prompt
Files owned: backend/services/memory_service.py | backend/agents/memory_manager.py

---

SLIDE 7 — LLM ENGINE (Part 4)
Title: "Gemini/Gemma — Hardened Instruction Hierarchy"
Visual: LEFT — Pyramid with 4 levels (top to bottom):
1. 🔴 Security Directives (NON-NEGOTIABLE) — "Never reveal internals, never bypass"
2. 🟠 Core Directives — "Bilingual, RAG-grounded, persona-aware"
3. 🟡 Domain Knowledge — "Egypt's 27 governorates, cultural norms, currency"
4. 🟢 Response Boundaries — "Travel topics only, plain text, no markdown"
RIGHT — Model routing box:
Text queries → Gemma-4-26B-A4B-IT
Multimodal (image/audio/PDF) → Gemini-2.5-Flash
Auto-detection: Arabic chars >30% → Arabic response mode
Files owned: backend/agents/llm.py

---

SLIDE 8 — LANGGRAPH ORCHESTRATION (Part 5)
Title: "LangGraph — The Multi-Agent Nervous System"
Visual: Animated graph execution diagram:
[Memory Manager (purple)] ──→ [Router Agent (amber)] ──→ ◆ (decision diamond)
The diamond has 5 branches:
→ [Travel Planner (blue)] → END
→ [Budget Specialist (green)] → END
→ [Local Concierge (orange)] → END
→ [General Chat (gray)] → END
→ [Needs Info (red)] → END
State flow label on each arrow. "AgentState" badge showing it flows through all nodes.
Below: streaming events timeline: node_start → trace → node_end → final
Files owned: backend/agents/graph.py | backend/agents/state.py

---

SLIDE 9 — ROUTER AGENT (Part 6)
Title: "Router — Intent Detection in 2 Passes"
Visual: Flowchart
[User Message] → [Pass 1: Regex Heuristics (fast, <1ms)] → Match found? YES → [Intent Set]
                                                           ↓ NO
                                                [Pass 2: LLM Classification (with persona)]
                                                           ↓
                                                       [Intent Set]
[Intent] → Gap Detection → Missing destination/duration/budget/party? 
YES → "needs_info" → Generate bilingual follow-up question
NO → Dispatch to specialist agent
Side callout: 5 intents: trip_planning | budget_query | local_info | general | needs_info
Files owned: backend/agents/router_agent.py

---

SLIDE 10 — 4 SPECIALIST AGENTS (Part 7)
Title: "Four Specialized AI Agents"
Visual: 2×2 grid of agent cards:
[BLUE] TRAVEL PLANNER — 4 parallel RAG queries (attractions + hotels + restaurants + medical). Output: structured day-by-day JSON itinerary. Special: modify mode, medical tourism weaving
[GREEN] BUDGET SPECIALIST — ChromaDB pricing queries + 3 budget brackets (economy/mid/luxury). Output: budget_breakdown JSON with flights, accommodation, meals, activities, transport
[ORANGE] LOCAL CONCIERGE — Allergen-filtered restaurant retrieval, halal enforcement. Output: spots JSON array with safety flags (safe_for_allergies: true/false)
[GRAY] GENERAL CHAT — Handles greetings, small talk, off-topic redirection to Egypt travel
All agents inject ---UI_TRIGGER--- marker for frontend native modal sync
Files owned: backend/agents/travel_planner.py | budget_specialist.py | local_concierge.py

---

SLIDE 11 — SECURITY (Part 8)
Title: "Defense-in-Depth — 10 Security Gates"
Visual: Concentric circles (outermost to innermost):
🔴 Ring 1: Transport — HSTS 1yr preload, HTTPS redirect, TLS 1.2+
🟠 Ring 2: Headers — CSP, X-Frame-Options DENY, nosniff, Permissions-Policy
🟡 Ring 3: Auth — Firebase token verification, JWT family rotation, replay detection, HttpOnly cookies
🟢 Ring 4: Input — Prompt firewall, UI_TRIGGER stripping, 10k char limit, 20MB attachment limit
🔵 Ring 5 (center): Application — Touri API (protected)
Below: Auth flow arrow: Firebase ID Token → Server Verification → JWT Access (60min) + Refresh (30d)
Files owned: backend/middleware/security.py | backend/routes/auth.py

---

SLIDE 12 — API ROUTES (Part 9)
Title: "REST + WebSocket API Surface"
Visual: Two-column layout:
LEFT column (REST endpoints, blue):
POST /api/chat ← main LangGraph chat
POST /api/chat (multimodal) ← images/audio
GET/POST /api/user/{uid}/persona ← persona CRUD
POST /api/auth/session ← Firebase → JWT
POST /api/auth/refresh ← token rotation
POST /api/auth/logout ← revoke + clear
RIGHT column (WebSocket, purple):
WS /api/chat/ws
Events emitted:
→ typing_indicator (active/inactive)
→ node_start (label + status_msg)
→ trace (agent reasoning step)
→ token_chunk (streaming text)
→ progressive_object (structured JSON)
→ message_complete
Files owned: backend/routes/chat.py | backend/routes/auth.py

---

SLIDE 13 — FRONTEND (Part 10)
Title: "React Native — Native Performance, AI-Native UX"
Visual: 5 iPhone mockups side by side (left to right):
1. Home — Catalog feed with featured destinations
2. Search — Search bar with filters
3. Chat — Chat screen with AgentTracePanel open (showing agent timeline)
4. Plan — Day-by-day itinerary view
5. Profile — User profile + persona settings
Below: 3 feature callouts:
🧠 AgentTracePanel — blurred bottom sheet showing real-time agent reasoning
🌍 Bilingual — Full EN/AR with automatic RTL layout
🔔 UI_TRIGGER — native modals for plan/budget/spots confirmation
Files owned: frontend/app/(tabs)/*.tsx | frontend/components/AgentTracePanel.tsx

---

SLIDE 14 — REQUEST LIFECYCLE
Title: "A Message End-to-End: 'Plan a 5-day trip to Luxor'"
Visual: Horizontal swimlane diagram with 5 lanes:
Lane 1 (CLIENT): User types message → WebSocket/REST send
Lane 2 (MIDDLEWARE): Rate limit ✓ → Size check ✓ → Auth JWT ✓ → Strip injections ✓
Lane 3 (GRAPH): fresh_state → Memory Manager (load: family 4, mid-range, halal) → Router (intent: trip_planning) → Travel Planner
Lane 4 (AI): 4 parallel ChromaDB queries (Luxor) → Gemma-4-26B generates 5-day JSON itinerary
Lane 5 (RESPONSE): Sanitize output → Sanitize trace → Return ChatResponse → Persist exchange
Timeline at bottom: ~2-4 seconds total latency
Number each step 1-12 with timing labels.

---

SLIDE 15 — STATE FLOW
Title: "AgentState — Accumulates Context at Each Hop"
Visual: A state JSON blob growing as it passes through nodes. Show 4 snapshots:
After Memory: {user_id, memory_context, travel_preferences, chat_history, conversation_state}
After Router: {+ intent: "trip_planning", active_agent: "Travel Planner", user_persona: {...}}
After Planner: {+ itinerary: {city, duration, days: [...]}, rag_context: "...", response_text: "..."}
Full state: 25+ fields, all typed, all observable via agent_trace
Bottom row: AgentStep structure: {agent, action, tool, reasoning, result, timestamp}

---

SLIDE 16 — WHY MULTI-AGENT WINS
Title: "Multi-Agent vs Single LLM"
Visual: Comparison table (dark styled):
| | ChatGPT | Touri |
|-----------------|---------|-------|
| Factual grounding | ❌ Hallucinates | ✅ RAG over 3,723 verified docs |
| Memory | ❌ Stateless | ✅ Cross-session, auto-extracted |
| Structured output | ❌ Markdown text | ✅ JSON + native UI components |
| Missing info | ❌ Guesses | ✅ Gap detection + targeted follow-up |
| Allergen safety | ❌ Ignores unless asked | ✅ Automatic filter + halal enforcement |
| Bilingual EN/AR | ⚠️ Partial | ✅ Native at every layer |
| Observability | ❌ Black box | ✅ Full agent_trace per step |
| Production security | ✅ OpenAI-managed | ✅ 10-gate defense-in-depth |

---

SLIDE 17 — DEPENDENCY GRAPH (Build Order)
Title: "Build Order — What Depends on What"
Visual: Directed Acyclic Graph (DAG):
P1 Foundation (bottom, gray) — no dependencies
↑ P2 RAG | P3 Memory | P4 LLM | P8 Security (can build in parallel, week 1-4)
↑ P5 Graph & State (depends on P2, P3, P4)
↑ P6 Router | P7 Agents (can build in parallel, week 5-8)
↑ P9 Routes (depends on ALL, week 9-10)
↑ P10 Frontend (depends on P9, week 11)
RED highlight: Critical path = P1 → P3 → P5 → P6 → P9 → P10
BLUE dashed box: "Parallel Group 1" around P2, P3, P4, P8
GREEN dashed box: "Parallel Group 2" around P6, P7

---

SLIDE 18 — 12-WEEK ROADMAP
Title: "12-Week Execution Plan"
Visual: Gantt chart (horizontal bars):
Week 1-2: P1 Foundation | P4 LLM | P8 Security (3 parallel bars)
Week 3-4: P2 RAG | P3 Memory (2 parallel bars)
Week 5-6: P5 Graph & State → P6 Router (sequential)
Week 7-8: P7 Agents ×4 (4 parallel bars)
Week 9-10: P9 Routes + Integration
Week 11: P10 Frontend
Week 12: 🚀 Deploy
Diamond milestones: M1(W2) Server Alive | M2(W4) RAG Ready | M3(W6) Graph Compiles | M4(W8) Agents Produce JSON | M5(W10) Full Lifecycle | M6(W12) Production

---

SLIDE 19 — SCALING VISION
Title: "From Egypt to the World"
Visual: 6-phase roadmap on a world map with expanding circles:
Phase 1 (NOW): Egypt — 3,723 docs, 5 agents, EN+AR, 100 concurrent users
Phase 2 (3-6mo): 10 countries — same pipeline, ingest new CSVs, 1,000 users
Phase 3 (6-9mo): Real-time data — live pricing, weather, events, 10,000 users
Phase 4 (9-12mo): Multi-modal — voice tours, AR navigation, real-time translation
Phase 5 (12-18mo): Agent marketplace — third-party plugins, revenue share
Phase 6 (18-24mo): Enterprise — white-label for tourism boards, 100,000+ users
Timeline scaling: 1 country → 100+ | 3,723 docs → 1M+ | 2 languages → 30+

---

SLIDE 20 — WHY NOW / INVESTOR PITCH
Title: "The Opportunity"
Visual: 3-column layout with large numbers:
COLUMN 1 (teal): "$50B+ TAM" — Global online travel market
COLUMN 2 (purple): "400M+" — Arabic speakers underserved by travel AI
COLUMN 3 (green): "15M" — Egypt tourists/year, $13B revenue
Below: 5 moat icons in a row:
🗄️ Data Moat — 3,723+ verified docs, years to replicate
🤖 Architecture — Multi-agent LangGraph, more accurate than single-LLM
🧠 Memory — Cross-session personalization, sticky product
🌍 Language — First-mover in Arabic travel AI
🛡️ Security — Enterprise-grade, production-ready day 1

---

SLIDE 21 — CLOSING
Title: "Touri — The AI Layer for Global Tourism"
Visual: Full dark screen. Touri logo centered (large). Three badges appear sequentially with glow:
🔍 GROUNDED — Every fact from verified data
🧠 PERSONAL — Memory persists, AI learns you
🛡️ PRODUCTION — Built for real users, not demos
Bottom: Three CTA buttons: [Live Demo] [GitHub] [Contact]
Final tagline: "Not a chatbot. An AI platform."

---

DESIGN RULES (apply to ALL slides):
1. Dark background (#0F172A) on every slide — no white slides
2. Maximum 5 bullet points per slide — prefer visuals over text
3. Every technical term gets a visual metaphor
4. Code snippets use syntax highlighting with dark theme
5. Diagrams use the color system defined above consistently
6. Transitions: smooth slide or fade (no spinning or bouncing)
7. Icons: use Lucide or Heroicons style — minimal, monoline
8. Every slide has a "Speaker Note" in the notes panel
9. Slide numbering: bottom right, small, subtle
10. Progress bar: thin teal line at top of every slide

Generate all 21 slides now with these exact specifications.
```
