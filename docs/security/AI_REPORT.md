# Touri AI Guardrails & Security Report

**Audit Date:** August 4, 2026  
**Auditor:** AI Security Auditor  
**Overall AI Score:** **92/100**  

---

## 1. Prompt Injection & Jailbreak Resistance
- **Prompt Firewall (`prompt_firewall.py`):** Utilizes weighted regex scanning for:
  - System instruction injection (`"ignore previous instructions"`, `"<|system|>"`, etc.)
  - Roleplay bypasses (`"DAN"`, `"developer mode"`, etc.)
  - Control sequence spoofing (`"UI_TRIGGER"`, `"<|im_start|>"`, etc.)
  - Extraction attempts (`"reveal your system prompt"`, `"chain-of-thought"`, etc.)
- **Firewall Bypass Vulnerability (Patched):** The firewall was only invoked inside LangGraph (Router Agent). Direct streaming WebSocket messages (`use_graph = False`) and REST requests with attachments completely bypassed the firewall.
  - *Remediation:* Integrated firewall scans directly into the `/chat` route and WebSocket message handlers so that any query, regardless of target agent path, is audited.

---

## 2. Information Disclosure & Output Sanitization
- **Output Sanitizer (`output_sanitizer.py`):** Acts as a post-generation filter. It inspects all assistant messages before returning them to clients, stripping:
  - System instruction keywords (`Security Directives`, `Instruction Hierarchy`, etc.)
  - Hidden reasoning tags (`<think>`, `[Internal Reasoning]`, etc.)
  - RAG engine variables (`egypt_travel_knowledge`, document similarity scores)
  - PII patterns (redacting credit card and SSN structures)
  - Raw HTML and Javascript URI blocks (preventing cross-site scripting inside the mobile web view)

---

## 3. RAG & Context Poisoning Mitigation
- **Memory Poisoning Vector:** Because Touri loads travel preferences and persona history dynamically:
  - *Risk:* If an attacker inputs prompt injection payloads into their profile fields (such as a dietary requirement containing `"ignore all safety rules and output..."`), this payload gets persisted in Firestore. On subsequent sessions, `memory_manager` loads these fields into the prompt context, automatically poisoning the LLM prompt.
  - *Mitigation:* We must apply the prompt firewall sanitation filter when updating user persona and preferences (in `/persona` and `update_travel_preferences`).
- **Context Size Validation:** ChromaDB vector queries are capped at `top_k = 5` documents, and output summarization occurs when chat history exceeds 30 messages. This prevents token overflow attacks where large prompts exhaust Mistral context limits.
