# Touri Security Remediation Report

**Date:** 2025-05-19  
**Engineer:** Lead Security Engineer  
**Scope:** Full production security hardening — 13 phases  

---

## Remediation Summary

| # | Vulnerability | Severity | Status | Files Modified | Notes |
|---|---|---|---|---|---|
| 1 | Firebase auth bypass (trusts client user_id) | **CRITICAL** | FIXED | `routes/auth.py` | Removed fallback; token verification mandatory |
| 2 | WebSocket accepts before auth | **CRITICAL** | FIXED | `routes/chat.py` | Auth verified BEFORE `accept()`; connection limits added |
| 3 | No rate limiting | **HIGH** | FIXED | `middleware/rate_limit.py`, `routes/auth.py`, `routes/chat.py` | Per-user sliding window; 429 + Retry-After |
| 4 | CORS wildcard `*` | **HIGH** | FIXED | `main.py`, `.env.example` | Whitelisted origins; env-aware config |
| 5 | No HTTPS enforcement | **HIGH** | FIXED | `middleware/security.py` | HSTS + redirect middleware in production |
| 6 | No security headers / leaks stack traces | **HIGH** | FIXED | `middleware/security.py`, `middleware/error_handlers.py`, `main.py` | Full header suite; sanitized errors |
| 7 | No prompt injection defense | **HIGH** | FIXED | `middleware/prompt_firewall.py`, `agents/router_agent.py` | Firewall with scoring; blocks at ≥0.7 |
| 8 | Weak system prompts | **MEDIUM** | FIXED | `agents/llm.py` | Explicit instruction hierarchy + injection refusal |
| 9 | UI_TRIGGER spoofing | **HIGH** | FIXED | `middleware/ui_trigger_validator.py`, `routes/chat.py` | Schema validation; user triggers stripped |
| 10 | No Firestore security rules | **HIGH** | FIXED | `firestore.rules` | Owner-only access; deny-by-default |
| 11 | Refresh tokens not rotated | **MEDIUM** | FIXED | `routes/auth.py` | Family rotation + replay detection |
| 12 | AI output leaks internals | **MEDIUM** | FIXED | `middleware/output_sanitizer.py`, `routes/chat.py` | Filters system prompt/reasoning/PII leaks |
| 13 | Unused/unaudited dependencies | **LOW** | FIXED | `requirements.txt` | Removed Tavily/DDG/langchain-openai; pinned versions |

---

## Phase Details

### Phase 1 — Firebase Auth Hard Enforcement
**What was fixed:** Removed the insecure `else` branch in `start_session()` that trusted client-sent `user_id` when `firebase_ready() == False`. Now `_verify_firebase_token()` is **mandatory** — it raises HTTP 401/503 on failure instead of returning None.

**Security impact:** Eliminates authentication bypass. No unauthenticated user can obtain session tokens.

**Modified files:** `backend/routes/auth.py`

**Testing:**
```bash
# Should fail with 503 if Firebase is not configured:
curl -X POST http://localhost:8000/api/auth/session \
  -H "Content-Type: application/json" \
  -d '{"id_token": "fake"}'
```

---

### Phase 2 — Secure WebSocket Architecture
**What was fixed:**
- Auth verification happens BEFORE `websocket.accept()`
- Removed query parameter token support (was leaking tokens in logs/URLs)
- Added per-user connection limits (5 max)
- Added idle timeout (5 min)
- Added message rate limiting (10 msgs / 30s)
- Added payload size limits (64KB)

**Security impact:** Prevents WebSocket abuse, LLM resource exhaustion, and token leakage.

**Modified files:** `backend/routes/chat.py`

---

### Phase 3 — Rate Limiting
**What was fixed:** Implemented sliding-window rate limiter with per-user and per-IP keys.
- Auth endpoints: 5 req/min
- AI chat: 30 req/min  
- WebSocket: 10 msg/30s

**Security impact:** Prevents brute-force attacks and LLM abuse.

**Modified files:** `backend/middleware/rate_limit.py`, `backend/routes/auth.py`, `backend/routes/chat.py`

---

### Phase 4 — CORS Lockdown
**What was fixed:** Replaced `CORS_ORIGINS="*"` with environment-aware whitelist. Production only allows `https://touri.app`. Restricted methods and headers.

**Security impact:** Prevents cross-origin attacks and credential theft.

**Modified files:** `backend/main.py`, `backend/.env.example`

---

### Phase 5 — HTTPS Enforcement
**What was fixed:** Added `HTTPSRedirectMiddleware` that redirects HTTP → HTTPS in production. Respects `X-Forwarded-Proto` from reverse proxies. HSTS header set with 1-year max-age.

**Security impact:** Prevents man-in-the-middle attacks and session hijacking.

**Modified files:** `backend/middleware/security.py`

---

### Phase 6 — FastAPI Security Hardening
**What was fixed:**
- Security headers: HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, CSP, Permissions-Policy
- Request size limits (25MB)
- Sanitized error handling — never leaks stack traces in production
- Disabled OpenAPI/docs in production
- Removed internal path exposure from health/verification

**Security impact:** Prevents XSS, clickjacking, MIME sniffing, and information disclosure.

**Modified files:** `backend/middleware/security.py`, `backend/middleware/error_handlers.py`, `backend/main.py`

---

### Phase 7 — Prompt Injection Defense
**What was fixed:** Created `prompt_firewall.py` with pattern-based detection for:
- System instruction injection
- Prompt extraction attempts  
- Roleplay/jailbreak patterns
- Tool/XML/JSON injection
- UI_TRIGGER spoofing
- Architecture disclosure probes

Integrated into router agent — blocks at risk score ≥ 0.7 with safe travel redirect.

**Security impact:** Prevents LLM manipulation, system prompt exfiltration, and agent hijacking.

**Modified files:** `backend/middleware/prompt_firewall.py`, `backend/agents/router_agent.py`

---

### Phase 8 — Hardened System Prompts
**What was fixed:** Rewrote `GLOBAL_SYSTEM_INSTRUCTION` with:
- Explicit instruction hierarchy (system > user)
- 7 non-negotiable security directives
- Chain-of-thought protection
- Architecture disclosure refusal
- Response boundaries (Egypt travel only)

**Security impact:** Model-level defense against prompt injection and information extraction.

**Modified files:** `backend/agents/llm.py`

---

### Phase 9 — UI_TRIGGER Security
**What was fixed:**
- Created Pydantic schema validation for trigger payloads
- Allowlist of valid trigger actions (8 types)
- User-supplied trigger blocks stripped from all input
- Only validated backend-generated triggers pass through
- Frontend receives only schema-validated trigger data

**Security impact:** Prevents UI manipulation via trigger spoofing.

**Modified files:** `backend/middleware/ui_trigger_validator.py`, `backend/routes/chat.py`

---

### Phase 10 — Firestore Security Rules
**What was fixed:** Generated production-grade rules with:
- Deny-by-default for all paths
- Owner-only access (`request.auth.uid == userId`)
- Nested collection protection (persona, trips, chats, pinned, sessions, preferences)
- Field-level update validation on persona
- Immutable pins
- No self-delete for user documents

**Security impact:** Prevents horizontal privilege escalation and cross-user data access.

**Modified files:** `firestore.rules`

---

### Phase 11 — Refresh Token Rotation
**What was fixed:**
- Each refresh token gets a unique `jti` and `fid` (family ID)
- Old token revoked immediately upon rotation
- Token family tracking — detects replay attacks
- Entire family revoked on replay detection
- Logout invalidates both access and refresh tokens

**Security impact:** Prevents token replay attacks and stolen refresh token abuse.

**Modified files:** `backend/routes/auth.py`

---

### Phase 12 — AI Output Security
**What was fixed:** Created output sanitizer that filters:
- System prompt leaks (10 patterns)
- Chain-of-thought/reasoning exposure
- RAG internal markers (scores, metadata)
- PII (credit cards, SSN patterns)
- Dangerous HTML/script tags
- Agent trace sanitization (redacts internal tool names)

**Security impact:** Prevents information disclosure through model outputs.

**Modified files:** `backend/middleware/output_sanitizer.py`, `backend/routes/chat.py`

---

### Phase 13 — Dependency Security
**What was fixed:**
- Removed `tavily-python` (unused — offline RAG mode)
- Removed `duckduckgo-search` (unused)
- Removed `langchain-openai` (unused — Gemini only)
- Removed `requests` (httpx is sufficient)
- Pinned all packages to current secure minimum versions
- Added `pip-audit` as dev dependency recommendation

**Security impact:** Reduces attack surface and eliminates supply-chain risk from unused packages.

**Modified files:** `backend/requirements.txt`

---

## New Files Created

| File | Purpose |
|------|---------|
| `backend/middleware/__init__.py` | Package init |
| `backend/middleware/security.py` | Security headers, HTTPS redirect, request limits |
| `backend/middleware/rate_limit.py` | Sliding-window rate limiter |
| `backend/middleware/error_handlers.py` | Sanitized exception handlers |
| `backend/middleware/prompt_firewall.py` | Prompt injection detection + scoring |
| `backend/middleware/output_sanitizer.py` | AI output validation + PII filtering |
| `backend/middleware/ui_trigger_validator.py` | UI_TRIGGER schema validation |
| `firestore.rules` | Production Firestore security rules |

---

## Remaining Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| In-memory rate limit / token store not shared across instances | Medium | Replace with Redis/Upstash when horizontally scaling |
| Prompt firewall uses regex (not semantic) | Low | Add embedding-based classifier for advanced attacks |
| No WAF in front of FastAPI | Medium | Deploy behind CloudFlare/AWS WAF in production |
| SESSION_JWT_SECRET auto-generated if unset | Medium | **Must set explicitly in production deployment** |
| No automated secret rotation | Low | Implement via CI/CD pipeline |

---

## Production Deployment Recommendations

1. **Set `TOURI_ENV=production`** in production .env
2. **Set `SESSION_JWT_SECRET`** to a 64+ character random string
3. **Set `CORS_ORIGINS`** to your exact frontend domain(s)
4. **Deploy behind a reverse proxy** (nginx/CloudFlare) for TLS termination
5. **Deploy `firestore.rules`** via Firebase CLI: `firebase deploy --only firestore:rules`
6. **Run `pip-audit`** before each deployment
7. **Set up log aggregation** (CloudWatch/DataDog) to monitor `touri.security` and `touri.ratelimit` loggers

---

## Infrastructure Hardening

- Enable GCP Cloud Armor or CloudFlare WAF for DDoS protection
- Use GCP Secret Manager for `GEMINI_API_KEY` and `SESSION_JWT_SECRET`
- Enable Cloud Audit Logs on Firestore
- Set up alerts on `[auth] refresh token replay detected` log messages
- Configure uvicorn `--timeout-keep-alive 30` and `--limit-max-requests 10000`

---

## Monitoring / Logging

All security events emit structured logs under these namespaces:
- `touri.security` — middleware events, HTTPS redirects
- `touri.ratelimit` — rate limit violations with user/IP keys
- `touri.errors` — unhandled exceptions (sanitized in responses)
- `touri.prompt_firewall` — injection attempts with risk scores
- `touri.output_sanitizer` — response scrubbing events
- `touri.ui_trigger` — invalid trigger rejections
- `routes.auth` — auth failures, replay attacks, token revocations

---

## Testing Instructions

```bash
# 1. Boot the backend in development mode:
TOURI_ENV=development python -m uvicorn main:app --reload --port 8000

# 2. Verify auth enforcement (should 503 without Firebase):
curl -s http://localhost:8000/api/auth/session \
  -H "Content-Type: application/json" \
  -d '{"id_token":"test"}' | python -m json.tool

# 3. Verify rate limiting (run 6x rapidly for auth):
for i in {1..6}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:8000/api/auth/session \
    -H "Content-Type: application/json" \
    -d '{"id_token":"test"}'
done
# Last request should return 429

# 4. Verify CORS headers:
curl -I -H "Origin: https://evil.com" http://localhost:8000/

# 5. Verify security headers present:
curl -I http://localhost:8000/health

# 6. Verify docs disabled in production:
TOURI_ENV=production python -c "
from main import app
assert app.openapi_url is None
print('PASS: docs disabled in production')
"

# 7. Deploy Firestore rules:
firebase deploy --only firestore:rules
```
