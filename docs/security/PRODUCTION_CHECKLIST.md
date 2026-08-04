# Touri Production Readiness Checklist

This checklist contains the necessary configuration and infrastructure settings to transition the Touri application from development to a secure, stable production environment.

## 1. Secrets & Environment Configuration
- [ ] **Enforce session JWT Secret:** Set `SESSION_JWT_SECRET` in `backend/.env`. Do NOT rely on the runtime fallback `secrets.token_urlsafe` which breaks session verification in multi-worker environments.
- [ ] **Configure Environment Variable:** Set `TOURI_ENV=production`. This disables FastAPI docs (`/docs`), validates CORS, and genericizes error logs.
- [ ] **API Keys Lockdown:** Verify that `MISTRAL_API_KEY` and `GEMINI_API_KEY` are not checked into Git.
- [ ] **Disable Debug Mode:** Ensure debug modes and stack traces are disabled in uvicorn options.

## 2. Infrastructure & Network Security
- [ ] **Reverse Proxy Timeout (Nginx / Cloudflare):** Set proxy read/write timeouts to at least `120s` to support long-running agent reasoning and slow-token streaming without connection closures.
- [ ] **WebSocket Proxying:** Enable `Upgrade` and `Connection` headers in the reverse proxy config to allow WebSocket connections.
- [ ] **Body Limit Sync:** Ensure reverse proxy body limits are configured to `25MB` to align with the backend's `RequestSizeLimitMiddleware` limit.
- [ ] **Enforce TLS 1.3:** Configure HTTPS listeners to enforce TLS 1.3 and HSTS headers.

## 3. Database & Storage Scaling
- [ ] **Firestore Index Deployment:** Deploy composite indexes from `firestore.indexes.json` via the Firebase Console or CLI.
- [ ] **Deploy Firestore Security Rules:** Verify that `firestore.rules` is updated to block client writes to `/trips` and `/chats`, and deployed to production.
- [ ] **Redis Backend Migration:** For horizontal scaling, modify `backend/routes/auth.py` and `backend/middleware/rate_limit.py` to use a shared Redis cache for `_revoked_tokens`, `_token_families`, and sliding rate limit windows.

## 4. Logging & Monitoring
- [ ] **PII Scrubbing:** Ensure Base64 image attachments or raw user phone numbers are not printed to backend server console logs.
- [ ] **Error Alerts:** Set up alerts (e.g. Sentry or CloudWatch) on the backend `touri.errors` logger to intercept rate-limit bypasses or firewall blocks.
- [ ] **pip-audit Scan:** Run `pip-audit` on the backend packages during the deployment pipeline to prevent CVE vulnerabilities.
