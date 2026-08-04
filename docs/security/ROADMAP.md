# Touri Hardening & Optimization Roadmap

This roadmap lists immediate and future development sprints to enhance the security, performance, and architecture of the Touri concierge app.

## Phase 1: Immediate Remediation (Setted in this Audit)
- [x] **API Prompt Firewall Integration:** Call the prompt firewall at REST `/chat` and WebSocket `/chat/ws` entry points to neutralize attacks before routing to LLMs.
- [x] **CORS Wildcard Fix:** Ensure specific origin arrays are returned to prevent credential clashes.
- [x] **Dynamic Cookie Security:** Switch the HttpOnly cookie `secure` flag based on the `IS_PRODUCTION` environment.
- [x] **FastAPI Host Whitelist:** Add `TrustedHostMiddleware` to reject spoofed Host header payloads.
- [x] **Rules Hardening:** Lock direct client writes to chats/trips and validate types of client-writable persona records.

## Phase 2: Scaling & CI/CD Readiness (Next Sprint)
- [ ] **Redis Migration:** Replace in-memory dictionaries with a shared Redis instance for token revocation, rate-limiting, and family session identifiers.
- [ ] **CI/CD Security Scans:** Configure `pip-audit` and `npm audit` inside GitHub Actions to run on every pull request.
- [ ] **State Machine Logging:** Export agent state transitions to an external metrics dashboard (like Prometheus or Datadog) to audit flow patterns.

## Phase 3: Cost, Performance, & UX Tuning (Future)
- [ ] **Parallel Tool Execution:** Refactor `stream_mistral_chat` tool calls to run concurrently via `asyncio.gather` when multiple independent tools are detected.
- [ ] **Input Sanitization in Persona Profiles:** Pass `first_name`, `last_name`, and `extras` inputs through the prompt firewall before saving to Firestore, preventing profile-based memory poisoning.
- [ ] **Configurable Stream Delays:** Allow clients to pass `skip_animation: true` in the WebSocket handshake to bypass the artificial 8ms sleep typing delay for a faster interface.
