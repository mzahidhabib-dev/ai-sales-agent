# AI Employee Platform — Phased Roadmap
### Phase Group 2: Premium / Cross-Cutting Features
### Phase Group 3: Deployment / Production Hardening

> **Instructions to the AI coding tool (Gemini / Antigravity):**
> This continues the roadmap from `ai-employee-platform-roadmap-phase-group-1.md`. Do not begin any Step below until every Step in Phase Group 1 is built and passes its Definition of Done. Treat every name, layer responsibility, schema field, and boundary in the Master Specification as **fixed**. Do not skip, merge, or reorder Steps. Every Cross-Cutting Service and Tech Stack item listed in Master Spec §5/§6 not already covered in Phase Group 1 appears exactly once below.

---

# PHASE GROUP 2 — Premium / Cross-Cutting Features

## Phase 5: Security & Tenant Isolation

**Step 5.1 — Secrets manager & credential encryption**
- Layer: Security (`platform/security`, §5, §11)
- Builds: centralized secrets store (env-based for now, structured for future vault swap); Gemini API key, Postgres creds, Redis creds all loaded from secrets manager — never hardcoded or committed.
- Depends on: 2.2 (AI Gateway), 1.1
- DoD: no credential exists in source code or version control; rotating a key requires no code change.

**Step 5.2 — RBAC**
- Layer: Security (`platform/security`)
- Builds: role definitions (e.g. owner, admin, viewer) enforced at the service layer for dashboard/API access.
- Depends on: 1.1
- DoD: a "viewer" role cannot trigger pipeline actions or edit Knowledge Layer config; verified with a negative test.

**Step 5.3 — Tenant isolation enforcement**
- Layer: Security (`platform/security`, §9)
- Builds: query/service-level enforcement (not just UI-level) that every read/write is scoped to `tenant_id`; middleware or decorator pattern applied across SDK calls.
- Depends on: 1.1, 2.1
- DoD: a cross-tenant query attempt (tenant A trying to read tenant B's data) is blocked and logged, not just filtered client-side.

**Step 5.4 — PII masking**
- Layer: Security (`platform/security`)
- Builds: PII detection/masking applied to Decision Card `reason[]`/`result` fields and Audit logs before storage or display, where applicable (e.g. personal phone numbers, emails redacted in logs though retained encrypted in core tables).
- Depends on: 2.5, 2.7
- DoD: a test Decision Card containing PII is stored with masked values in the Audit log view, unmasked only in the authorized core record.

**Step 5.5 — Prompt-injection protection**
- Layer: Security (`platform/security`)
- Builds: input sanitization/guardrails on any AI Gateway call that includes untrusted external content (e.g. scraped company research text) before it's interpolated into a prompt.
- Depends on: 2.2, 3.4 (ResearchAgent)
- DoD: a test prompt-injection payload embedded in scraped research content does not alter agent behavior or leak instructions.

**Step 5.6 — Webhook verification**
- Layer: Security (`platform/security`), n8n
- Builds: signature/secret verification on all n8n-facing webhooks (inbound triggers).
- Depends on: 1.4
- DoD: an unsigned/forged webhook request is rejected.

---

## Phase 6: Full Memory

**Step 6.1 — Memory schema**
- Layer: Memory (`platform/memory`, §5)
- Builds: Postgres tables for per-contact and per-tenant memory: past conversations, objections raised, preferred follow-up time, buying stage, decision-maker changes.
- Depends on: 1.1
- DoD: schema supports storing and retrieving a full contact history keyed by tenant_id + contact_id.

**Step 6.2 — Memory read/write via SDK**
- Layer: Memory, Platform SDK
- Builds: `sdk.memory.get(contact_id)` / `sdk.memory.update(contact_id, ...)` exposed through Platform SDK only (agents never touch the table directly).
- Depends on: 6.1, 2.1
- DoD: PersonalizationAgent and FollowUpAgent can read prior memory to adjust tone/timing, and write new memory after each interaction.

**Step 6.3 — Wire Memory into existing agents**
- Layer: Business Agent Layer
- Builds: retrofit `ResearchAgent`, `PersonalizationAgent`, `FollowUpAgent` to consult and update Memory (e.g. don't repeat a previously-handled objection).
- Depends on: 6.2, 3.4, 3.6, 3.7
- DoD: a second pipeline run for the same contact reflects awareness of the first run's outcome (e.g. adjusted follow-up cadence).

---

## Phase 7: Approval Engine & Confidence Engine

**Step 7.1 — Confidence Engine**
- Layer: Confidence Engine (`platform/confidence`, §5)
- Builds: threshold logic reading `confidence` from each Decision Card; if below threshold (per Knowledge Layer config), sets `approval_required = true` and blocks auto-execution.
- Depends on: 2.5, 2.3
- DoD: a low-confidence ScoringAgent or PersonalizationAgent output is correctly flagged `approval_required = true` and does not proceed automatically.

**Step 7.2 — Approval Engine**
- Layer: Approval (`platform/approval`, §5)
- Builds: human-in-the-loop gate before: sending email, scheduling meeting, changing CRM/opportunities, deleting records. Publishes `approval.requested`; on human response, publishes `approval.granted` or `approval.rejected`.
- Depends on: 7.1, 2.6
- DoD: a flagged action pauses the LangGraph node (using checkpoint/resume from 3.1) until an approval decision is recorded; granting resumes execution, rejecting halts it.

**Step 7.3 — Approval UI (dashboard)**
- Layer: Dashboard (Event Bus subscriber)
- Builds: minimal approve/reject UI surfacing pending `approval.requested` items from the dashboard built in 4.2.
- Depends on: 7.2, 4.2
- DoD: a human can approve/reject a pending action from the dashboard, and the pipeline resumes/halts accordingly.

**Step 7.4 — Wire Approval into send_email / update_crm / book_meeting**
- Layer: Business Agent Layer, Tool Gateway
- Builds: `PersonalizationAgent`, `FollowUpAgent`, `MeetingAgent` route through Approval Engine before calling `send_email`, `update_crm`, or `check_calendar_availability`-driven bookings, when `approval_required = true`.
- Depends on: 7.2, 3.6, 3.7, 3.8
- DoD: this closes the flagged Phase Group 1 gap — no email sends or CRM/meeting changes happen fully unattended when confidence is low.

---

## Phase 8: Full Audit Trail & Replay Engine

**Step 8.1 — Full Audit trail**
- Layer: Audit (`platform/audit`, §5, §11)
- Builds: expand the bare log (2.7) into a full prompt → model → output → validation → decision trail per action, queryable by tenant/agent/date range, with a dashboard viewer.
- Depends on: 2.7, 4.2
- DoD: for any Decision Card, the full trail (raw prompt, raw model output, validation result, final decision) is retrievable and viewable.

**Step 8.2 — Replay Engine**
- Layer: Replay (`platform/replay`, §5)
- Builds: one-click re-run of any past workflow using logged inputs from Audit (8.1); writes a new Decision Card with `replay_id` linking back to the original.
- Depends on: 8.1, 2.5
- DoD: replaying a past ScoringAgent run produces a new Decision Card with `replay_id` set, using identical logged inputs.

---

## Phase 9: Evaluation Engine

**Step 9.1 — Evaluation logging**
- Layer: Evaluation (`platform/evaluation`, §5, §10)
- Builds: continuous scoring hooks for research quality, lead-score quality, personalization quality, prompt quality, meeting rate, reply rate, hallucination rate — logged only (per §10, auto-tuning is explicitly deferred backlog, not built here).
- Depends on: 2.5, 8.1
- DoD: each pipeline run produces evaluation metrics stored and queryable per agent/prompt version.

---

## Phase 10: Full Observability

**Step 10.1 — LangSmith tracing**
- Layer: Observability (`platform/observability`, §5, §6)
- Builds: LangGraph graph execution traced end-to-end via LangSmith.
- Depends on: 3.1
- DoD: any pipeline run is fully traceable node-by-node in LangSmith.

**Step 10.2 — Prometheus metrics**
- Layer: Observability
- Builds: request/workflow/agent/API call counters, latencies, error rates exported as Prometheus metrics.
- Depends on: 4.1
- DoD: Prometheus scrape endpoint exposes metrics for queue depth, worker throughput, agent latency, AI Gateway call counts.

**Step 10.3 — Grafana dashboards**
- Layer: Observability
- Builds: Grafana dashboards visualizing Prometheus metrics (pipeline throughput, error rates, per-agent latency).
- Depends on: 10.2
- DoD: a Grafana dashboard shows live pipeline health.

**Step 10.4 — Structured logging**
- Layer: Observability
- Builds: consistent structured (JSON) logs across n8n triggers, Workers, Business Agent Layer, Gateways.
- Depends on: 1.4, 1.5, 2.1
- DoD: a single request/job is traceable across all layers via a shared correlation/trace ID in logs.

---

## Phase 11: Cost Engine

**Step 11.1 — Cost Engine**
- Layer: Cost Engine (`platform/cost`, §5)
- Builds: aggregates `cost_usd` from Decision Cards into cost per lead, cost per meeting, cost per customer, cost by model, token usage, and trend views.
- Depends on: 2.5, 4.2 (dashboard)
- DoD: dashboard surfaces cost-per-meeting and cost-by-model figures pulled from real Decision Card data.

---

## Phase 12: Multi-Provider AI Gateway with Fallback

**Step 12.1 — Add OpenAI + Anthropic + OpenRouter providers**
- Layer: AI Gateway (`platform/ai_gateway`, §6)
- Builds: extend the Gemini-only implementation (2.2) to a provider-agnostic interface with OpenAI, Anthropic, and OpenRouter adapters behind the same `generate()` signature.
- Depends on: 2.2
- DoD: switching provider via config alone (no agent code changes) produces valid structured output from at least two non-Gemini providers.

**Step 12.2 — Fallback & retry logic**
- Layer: AI Gateway
- Builds: automatic fallback to a secondary provider on rate-limit/error from the primary; retry policy with backoff.
- Depends on: 12.1
- DoD: forcing a primary-provider failure results in a successful fallback completion with no pipeline interruption.

---

## Phase 13: Tool Gateway — MCP Client Full Wiring

**Step 13.1 — MCP Client implementation**
- Layer: MCP Client (§5)
- Builds: full client for talking to internal/external MCP servers on behalf of Tool Gateway (not exposed directly to Business Agent Layer).
- Depends on: 2.4
- DoD: Tool Gateway can route a capability call through MCP Client to at least one real MCP server.

**Step 13.2 — Wire MCP servers identified for launch**
- Layer: Tool Gateway, MCP Client
- Builds: connect whichever MCP servers are confirmed available (resolve Master Spec §13 open question #5 with the owner before this Step); each new capability exposed via Tool Gateway using capability-naming convention (not implementation names).
- Depends on: 13.1
- DoD: at least one previously-stubbed capability now resolves through a real MCP server instead of a stub.

---

## Phase 14: Knowledge Layer Expansion

**Step 14.1 — Expand config coverage**
- Layer: Knowledge Layer (`platform/knowledge`, §5)
- Builds: add playbooks, objection-handling scripts, additional per-tenant company config beyond the Phase Group 1 minimum (ICP, scoring rubric, templates, cadence).
- Depends on: 2.3
- DoD: PersonalizationAgent and FollowUpAgent can pull objection-handling scripts from Knowledge Layer rather than relying on generic AI Gateway prompting alone.

*(Note: Admin UI for Knowledge Layer remains explicitly deferred per Master Spec §10 — flat YAML/JSON files continue to be edited directly, not built here.)*

---

## Phase 15: Full Event Bus — Remaining Subscribers

**Step 15.1 — Analytics subscriber**
- Layer: Event Bus subscribers (§8)
- Builds: Analytics subscriber consuming the full event stream for reporting/trend analysis (explicitly allowed to lag Phase Group 1 per §8 note).
- Depends on: 2.6
- DoD: Analytics subscriber correctly ingests all 14 event types without missing any.

**Step 15.2 — Full Audit subscriber**
- Layer: Event Bus subscribers, Audit
- Builds: Audit becomes a proper Event Bus subscriber (not just a direct write from Decision Card creation), decoupling it per the architecture diagram in §4.
- Depends on: 8.1, 2.6
- DoD: disabling direct audit writes and relying solely on the event subscription still produces complete audit trails.

**Step 15.3 — Daily Executive Report generator**
- Layer: Event Bus subscriber
- Builds: daily digest (dashboard + email, per confirmed Open Question #6) summarizing pipeline activity: prospects found, meetings booked, cost, reply rate.
- Depends on: 15.1, 11.1, 9.1
- DoD: a scheduled daily report is generated and delivered via email and visible on the dashboard.

---

# PHASE GROUP 3 — Deployment / Production Hardening

> Do not begin until all of Phase Group 2 is built and reviewed.

## Phase 16: Containerization

**Step 16.1 — Dockerize each service**
- Layer: Deployment (§6, §11)
- Builds: Dockerfiles for Workers, n8n (or documented official image usage), Platform SDK/Gateway services, Dashboard.
- Depends on: all Phase Group 1 & 2 services functional
- DoD: each service builds and runs as a standalone container locally.

**Step 16.2 — Docker Compose orchestration**
- Layer: Deployment
- Builds: `docker-compose.yml` wiring Postgres, Redis, n8n, Workers, Gateways, Dashboard together with correct networking and volume persistence.
- Depends on: 16.1
- DoD: `docker-compose up` brings up the full stack and a manual pipeline trigger runs end-to-end.

## Phase 17: Production Host Setup

**Step 17.1 — Ubuntu VM provisioning**
- Layer: Deployment
- Builds: VM provisioned with Docker/Docker Compose installed, firewall rules configured.
- Depends on: 16.2
- DoD: Compose stack runs on the VM, reachable only via intended ports.

**Step 17.2 — Reverse Proxy (Nginx) + HTTPS**
- Layer: Deployment (§6 — confirmed Nginx)
- Builds: Nginx reverse-proxying Dashboard/API/n8n webhook endpoints; TLS via Let's Encrypt (free, fits "no paid" constraint).
- Depends on: 17.1
- DoD: all public endpoints served over HTTPS; HTTP requests redirect to HTTPS.

**Step 17.3 — Production secrets management**
- Layer: Security, Deployment
- Builds: production-grade secrets injection (env files excluded from images/VCS, or a lightweight secrets tool) replacing local dev secrets from 5.1.
- Depends on: 5.1, 17.1
- DoD: no secret exists in the Docker image layers or repo; verified via image inspection.

## Phase 18: Load & Failure Testing

**Step 18.1 — Testing bar per §11**
- Layer: all layers
- Builds: test suite covering, for every feature: happy path, edge cases, API failures, duplicate execution, rate limits, bad data, large datasets, recovery after interruption.
- Depends on: 16.2, 17.2
- DoD: each pipeline stage has passing tests for all eight categories above; failures produce `workflow.failed` events (4.3), not silent errors or data corruption.

**Step 18.2 — Recovery/interruption testing**
- Layer: Workers, Business Agent Layer, Queue
- Builds: forced-kill tests on Workers mid-pipeline; verify LangGraph checkpoint/resume (3.1) and Queue redelivery correctly recover in-flight jobs.
- Depends on: 18.1
- DoD: killing a Worker mid-run and restarting results in the job resuming from its last checkpoint, not restarting or being lost.

## Phase 19: Documentation & Production Readiness

**Step 19.1 — Documentation**
- Layer: all layers
- Builds: setup/runbook docs (env vars, deployment steps, how to add a new tenant, how to edit Knowledge Layer configs, how to interpret Decision Cards/Audit trail).
- Depends on: 17.2, 18.1
- DoD: a person unfamiliar with the codebase can follow the docs to deploy the stack from scratch.

**Step 19.2 — Final production readiness review**
- Layer: all layers, owner sign-off
- Builds: checklist review against Master Spec §11 (Reliable / Observable / Recoverable / Scalable / Explainable / Secure / Measurable) for every feature built across all three Phase Groups.
- Depends on: 19.1, 18.2
- DoD: owner confirms each §11 criterion is met; system is declared production-ready.

---

## Not In This Roadmap (any Phase Group)

Per Master Spec §10, these remain backlog items regardless of Phase Group completion — do not build without a new explicit owner request:

| Deferred item | Build trigger |
|---|---|
| Multi-channel outreach (LinkedIn, WhatsApp, phone) | Owner requests channel #2 |
| CRM data-hygiene bot | Owner flags dirty CRM as blocking |
| SDR coaching AI | Owner hires human reps alongside AI |
| Continuous buying-intent monitoring (always-on polling) | Owner wants proactive re-engagement |
| Full auto-tuning learning loop | Enough volume to have signal |
| Kubernetes / autoscaling infra | Load requires it |
| Admin UI for Knowledge Layer | Non-technical staff need to edit configs |

---

*End of Phase Groups 2 & 3. Combined with `ai-employee-platform-roadmap-phase-group-1.md`, this covers the entire Master Specification: every layer in §5, every tech stack item in §6, the full §7 Decision Card schema, all 14 §8 events, and the §10 backlog explicitly carried forward rather than silently dropped.*
