# AI Employee Platform — Phased Roadmap
### Phase Group 1: Working Core Product (MVP Pipeline)

> **Instructions to the AI coding tool (Gemini / Antigravity):**
> This roadmap is generated from the attached/referenced Master Specification (`ai-employee-platform-master-spec.md`). Treat every name, layer responsibility, schema field, and boundary in that spec as **fixed**. Do not propose alternative architectures, naming, or scope. Follow the Steps below **in order** — each Step lists its dependencies. Do not skip a Step or merge two Steps together. When a Step's Definition of Done is not met, stop and flag it rather than proceeding to the next Step.
>
> **This file covers Phase Group 1 ONLY.** Do not begin Phase Group 2 (premium/cross-cutting features) or Phase Group 3 (deployment/hardening) work until Phase Group 1 is fully built, tested against its Definitions of Done, and explicitly approved by the project owner.

---

## Open Questions — Resolved / Confirmed Before Phase 1

| # | Question | Decision |
|---|---|---|
| 1 | Queue implementation | **Redis Streams** |
| 2 | LLM provider (v1) | **Gemini (free tier)** |
| 3 | Reverse proxy | **Nginx** (Phase Group 3 only) |
| 4 | Single-tenant vs multi-tenant onboarding | **Single active tenant in practice**; schema remains multi-tenant-ready per spec §9 |
| 5 | MCP servers at launch | **None — stubbed/skipped in Phase Group 1**, revisit in Phase Group 2 |
| 6 | Daily Executive Report format | **Dashboard + email**, both from day one |
| 7 | CRM (GHL alternative) | **Direct Postgres implementation** (`opportunities` + `pipeline_stage` tables) instead of GoHighLevel — deviation from spec §6, approved by project owner to keep v1 free/no external CRM dependency. GHL (or HubSpot Free / Twenty CRM) remains a possible future swap-in behind the same `update_crm()` capability if a real CRM UI is ever needed. |

⚠️ **Flagged tradeoff, not yet resolved:** Phase Group 1 as scoped has **no Approval Engine or Confidence Engine**, meaning outreach emails and calendar bookings will be sent/created fully automatically with no human gate. This is allowed by the sequencing rule (those are Phase Group 2 items), but for a pipeline sending real emails to real prospects, consider adding a manual "pause before send" toggle even in Phase Group 1. Flag this to the owner before wiring `send_email()` live.

---

## Phase 1: Infrastructure Foundation

**Step 1.1 — PostgreSQL multi-tenant schema (baseline)**
- Layer: PostgreSQL (§6)
- Builds: `tenant_id` on every table from migration 1. Core tables: `tenants`, `prospects`, `decision_makers`, `companies`, `decision_cards`, `events`, `opportunities`, `pipeline_stage` (enum/lookup: `prospecting → contacted → meeting_booked → handed_off`), `handoffs`.
- Depends on: none
- Definition of Done: migrations run clean; every table has `tenant_id` FK; seed one tenant row.

**Step 1.2 — Redis setup (cache + queue backing)**
- Layer: Redis (§6)
- Builds: Redis instance running locally/Docker, used both as cache and as backing for Queue.
- Depends on: none
- Definition of Done: Redis reachable, basic SET/GET test passes.

**Step 1.3 — Queue (Redis Streams)**
- Layer: Queue (§4, §5)
- Builds: Redis Streams-based queue: one stream per pipeline stage, consumer group per Worker type.
- Depends on: 1.2
- Definition of Done: a test job can be pushed to a stream and read back by a dummy consumer.

**Step 1.4 — n8n setup (plumbing only)**
- Layer: n8n (§5 — "zero business logic allowed here")
- Builds: n8n instance running; one workflow: cron/webhook trigger → HTTP POST → pushes job onto Queue (1.3). No AI/business logic inside n8n itself.
- Depends on: 1.3
- Definition of Done: manually triggering the n8n workflow results in a job appearing on the Queue.

**Step 1.5 — Workers skeleton**
- Layer: Workers (§5 — "stateless, horizontally scalable")
- Builds: Python worker process that pulls jobs off the Queue, logs them, acks them. No LangGraph invocation yet.
- Depends on: 1.3
- Definition of Done: worker consumes a test job end-to-end from n8n → Queue → Worker log line.

---

## Phase 2: Platform SDK & Gateways (minimum viable)

**Step 2.1 — Platform SDK skeleton**
- Layer: Platform SDK (§4, §5 — "the ONLY module Business Agent Layer may import")
- Builds: `platform/sdk` module exposing a single entrypoint object/class the agents will call (e.g. `sdk.ai.generate(...)`, `sdk.tools.call(...)`, `sdk.knowledge.get(...)`). No implementation yet — just the interface contract.
- Depends on: none (parallel to Phase 1)
- Definition of Done: SDK importable, methods raise `NotImplementedError`, signatures match what agents will need per §5 contract (no business-domain concepts inside SDK).

**Step 2.2 — AI Gateway (Gemini only)**
- Layer: AI Gateway (`platform/ai_gateway`, §5, §6, §12)
- Builds: wraps Gemini free-tier API call behind a single `generate(prompt, schema=None)` function. Includes rate-limit handling (Gemini free tier has strict RPM limits), structured output enforcement (JSON schema validation on Gemini response), prompt-version tag pass-through (logged, not yet formally stored).
- Depends on: 2.1
- Definition of Done: a test prompt through AI Gateway returns validated structured JSON; rate-limit backoff verified with a burst test.

**Step 2.3 — Knowledge Layer (flat config files)**
- Layer: Knowledge Layer (`platform/knowledge`, §5, §12)
- Builds: YAML/JSON files for: ICP definition, scoring rubric, outreach message templates/tone, follow-up cadence rules. Loaded via `sdk.knowledge.get(key, tenant_id)`.
- Depends on: 2.1
- Definition of Done: all 7 pipeline agents can pull their required config value from Knowledge Layer, not hardcoded.

**Step 2.4 — Tool Gateway (minimum tools only)**
- Layer: Tool Gateway (`platform/tool_gateway`, §5, §12)
- Builds: capability-named functions only for what the MVP pipeline needs: `find_prospect`, `find_decision_maker`, `research_company`, `send_email`, `check_calendar_availability`, `update_crm`. **`update_crm` writes directly to Postgres `opportunities`/`pipeline_stage` tables** (see Open Questions #7 — deviation from spec's GHL default, owner-approved). Tool Gateway decides local-tool vs REST; MCP path stubbed/skipped per Phase Group 1 rule.
- Depends on: 2.1
- Definition of Done: each capability callable via Tool Gateway returns a typed result; `update_crm` correctly writes/updates a row in `opportunities`.

**Step 2.5 — Basic Decision Cards**
- Layer: Decision Cards (`platform/decision_cards`, §7)
- Builds: full schema from §7 as a Postgres table + a `record_decision(...)` function callable from SDK. Every field present: `decision_id, tenant_id, agent_name, action, result, confidence, reason[], sources[], model, prompt_version, cost_usd, duration_seconds, approved, approval_required, timestamp, replay_id`.
- Depends on: 1.1, 2.1
- Definition of Done: calling `record_decision(...)` inserts a row with all fields populated (`approved`/`replay_id` nullable as spec allows).

**Step 2.6 — Basic Event Bus**
- Layer: Event Bus (`platform/events`, §5, §8)
- Builds: the full v1 event list from §8 (`prospect.found, decision_maker.found, research.completed, score.completed, buying_signal.detected, outreach.generated, email.sent, followup.triggered, meeting.booked, crm.updated, approval.requested, approval.granted, approval.rejected, workflow.failed`) as publishable event types; simple pub/sub over Redis. No subscribers wired yet except a log-to-table subscriber.
- Depends on: 1.1, 1.2
- Definition of Done: publishing any of the 14 §8 events writes a row to an `events` table with tenant_id, event_type, payload, timestamp.

**Step 2.7 — Basic Audit (bare log-to-table)**
- Layer: Audit (`platform/audit`, §5)
- Builds: every Decision Card write (2.5) also writes an audit row: prompt → model → output → validation result → decision. Just a table insert, no UI/trail viewer yet.
- Depends on: 2.5
- Definition of Done: for a test agent action, one Decision Card row + one corresponding Audit row exist.

---

## Phase 3: Business Agent Layer (LangGraph) — pipeline agents

**Step 3.1 — LangGraph state machine skeleton**
- Layer: Business Agent Layer (`business-agents/sales`, §3, §4, §5, §12)
- Builds: LangGraph graph with 7 nodes matching §3 exactly: `ProspectAgent → DecisionMakerAgent → ResearchAgent → ScoringAgent → PersonalizationAgent → FollowUpAgent → MeetingAgent`, each currently a no-op pass-through node. Checkpoint/resume enabled (LangGraph native).
- Depends on: 2.1
- Definition of Done: graph runs start to finish with dummy input, checkpoints visible between nodes, resumable after forced interruption.

**Step 3.2 — ProspectAgent**
- Layer: Business Agent Layer / `ProspectAgent`
- Builds: calls `sdk.tools.find_prospect()` (2.4) using ICP from Knowledge Layer (2.3); records Decision Card; publishes `prospect.found`.
- Depends on: 3.1, 2.4, 2.3, 2.5, 2.6
- Definition of Done: given a tenant + ICP config, agent returns a list of prospects; Decision Card + event both fire.

**Step 3.3 — DecisionMakerAgent**
- Builds: calls `sdk.tools.find_decision_maker()`; records Decision Card; publishes `decision_maker.found`.
- Depends on: 3.2
- Definition of Done: given a prospect company, returns decision-maker contact; card + event fire.

**Step 3.4 — ResearchAgent**
- Builds: calls `sdk.tools.research_company()`; uses AI Gateway to summarize research via Gemini; records Decision Card; publishes `research.completed`.
- Depends on: 3.3, 2.2
- Definition of Done: given a company, returns structured research summary; card + event fire.

**Step 3.5 — ScoringAgent**
- Builds: applies scoring rubric from Knowledge Layer (2.3) + AI Gateway reasoning; records Decision Card (includes `confidence`, `reason[]`); publishes `score.completed` and, if signal detected, `buying_signal.detected`.
- Depends on: 3.4
- Definition of Done: given research output, returns a numeric score + reasons; both events fire correctly based on rubric thresholds.

**Step 3.6 — PersonalizationAgent**
- Builds: generates outreach message via AI Gateway using message templates/tone from Knowledge Layer; records Decision Card; publishes `outreach.generated`, then calls `sdk.tools.send_email()` and publishes `email.sent`.
- Depends on: 3.5, 2.2, 2.3, 2.4
- Definition of Done: given a scored lead, produces a personalized email, sends it via Tool Gateway, both events fire.

**Step 3.7 — FollowUpAgent**
- Builds: applies follow-up cadence rules from Knowledge Layer; on trigger, generates follow-up via AI Gateway, sends via Tool Gateway; records Decision Card; publishes `followup.triggered`.
- Depends on: 3.6
- Definition of Done: given no-reply after cadence window, follow-up fires correctly and events log.

**Step 3.8 — MeetingAgent**
- Builds: calls `sdk.tools.check_calendar_availability()` and `sdk.tools.update_crm()` (writes to Postgres `opportunities`); on booking, records Decision Card; publishes `meeting.booked` and `crm.updated`.
- Depends on: 3.7, 2.4
- Definition of Done: given a positive reply, agent books a meeting slot and updates `opportunities` stage to `meeting_booked`; both events fire.

**Step 3.9 — Human Handoff**
- Layer: Business Agent Layer (end of pipeline, §3)
- Builds: on `meeting.booked`, graph pauses/ends with a clear handoff payload (lead summary + Decision Card trail) written to a `handoffs` table + Slack notification via n8n (n8n only relays, no logic).
- Depends on: 3.8, 2.6
- Definition of Done: a booked meeting produces a visible handoff record a human can act on.

---

## Phase 4: End-to-end wiring

**Step 4.1 — Wire n8n trigger → Queue → Worker → LangGraph graph**
- Layer: n8n, Queue, Workers, Business Agent Layer
- Builds: connects 1.4/1.5 to 3.1 so a real trigger runs the full 7-agent pipeline.
- Depends on: 1.4, 1.5, 3.1–3.9
- Definition of Done: one manual n8n trigger runs the entire pipeline end-to-end for one test tenant/prospect, producing Decision Cards, Events, and a Handoff record.

**Step 4.2 — Minimal Event Bus subscribers (Dashboard, Slack)**
- Layer: Event Bus subscribers (§8)
- Builds: bare Dashboard (read-only page/table view of `events`, `decision_cards`, and `opportunities` by pipeline stage) and Slack notification via n8n subscribing to key events (`meeting.booked`, `workflow.failed`).
- Depends on: 2.6, 3.9
- Definition of Done: running the full pipeline results in visible dashboard rows and a Slack message on meeting booked.

**Step 4.3 — `workflow.failed` handling**
- Layer: Event Bus, Business Agent Layer
- Builds: any node exception in the LangGraph graph publishes `workflow.failed` with error context instead of crashing silently.
- Depends on: 3.1, 2.6
- Definition of Done: forcing a tool failure mid-pipeline results in a `workflow.failed` event, not a silent crash.

---

## Not In This Roadmap (Phase Group 1)

**Deferred to Phase Group 2 per sequencing rule:**
Full Memory, full Audit trail (beyond bare log), Security (RBAC/PII masking/prompt-injection protection/tenant isolation enforcement), Approval Engine, Confidence Engine, Replay Engine, Evaluation Engine, full Observability (LangSmith/Prometheus/Grafana), Cost Engine, multi-provider AI Gateway/fallback, MCP Client wiring, Knowledge Layer expansion beyond flat files, remaining Event Bus subscribers (Analytics/full Audit/Daily Report generator beyond raw log).

**Deferred per Master Spec §10 (Explicitly Deferred Backlog) — do not build without a new owner request:**
| Deferred item | Reason | Build trigger |
|---|---|---|
| Multi-channel outreach (LinkedIn, WhatsApp, phone) | v1 pipeline is email-first | Owner requests channel #2 |
| CRM data-hygiene bot (dedupe, dead-contact cleanup) | Separate from linear pipeline | Owner flags dirty CRM as blocking |
| SDR coaching AI (call review, objection training) | No human SDRs being coached yet | Owner hires human reps alongside AI |
| Continuous buying-intent monitoring (funding/hiring alerts, always-on polling) | v1 scoring is point-in-time at prospect-find | Owner wants proactive re-engagement |
| Full auto-tuning learning loop (auto-adjusting prompts from reply data) | v1 ships evaluation logging only, not auto-tuning | Enough volume to have signal |
| Kubernetes / autoscaling infra | Docker Compose is sufficient for v1 scale | Load requires it |
| Admin UI for Knowledge Layer | v1 Knowledge Layer is YAML/JSON files | Non-technical staff need to edit configs |

**Deviation from Master Spec §6 (flagged, owner-approved):**
GoHighLevel (GHL) replaced with direct Postgres implementation for `update_crm()` in Phase Group 1, to avoid a paid dependency. Revisit in Phase Group 2/3 if a real CRM UI (HubSpot Free / Twenty CRM / actual GHL) becomes necessary.

---

*End of Phase Group 1. Do not proceed to Phase Group 2 until this phase is built, tested against every Definition of Done above, and reviewed by the project owner.*
