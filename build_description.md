# Acme Logistics — Inbound Carrier Load Sales Automation (POC)

> **Outcome:** Carriers who call in get verified, pitched, negotiated, and handed off—fast. Your reps pick up only the ready-to-book deals, with clean KPI visibility.

---

## 1) Executive Summary

We built a production-style voice agent on **HappyRobot** that:

* **Verifies MC** eligibility with the FMCSA QCMobile API.
* **Finds and pitches** best-fit loads from your feed in a single sentence.
* **Negotiates up to 3 rounds** using a tunable policy that protects margin.
* **Books & transfers** to your sales queue on agreement.
* **Captures** the key facts (MC, load ID, agreed rate, rounds).
* **Classifies** outcome and **sentiment** for coaching & funnel analytics.
* Streams into a lightweight **dashboard**; deploys as **containers**.

**Why Acme cares:** lower AHT, after-hours capture, consistent pricing discipline, and executive-clean KPIs—without changing your existing systems.

---

## 2) Acceptance-Criteria Compliance (at a glance)

* ✔ Get MC + verify via FMCSA
* ✔ Search loads & pitch details
* ✔ Ask for acceptance / “what do you need on it?”
* ✔ Negotiate ≤ **3** back-and-forths
* ✔ Transfer call to a rep on agreement
* ✔ Extract offer data (MC, load\_id, agreed\_rate, rounds)
* ✔ Classify outcome (booked / no-agreement / no-match / failed-auth / abandoned)
* ✔ Classify sentiment (positive / neutral / negative)
* ✔ Dashboard/reporting (KPIs, storage health)
* ✔ Containerized (frontend + API)

---

## 3) Live Demo Flow (what you will see)

1. Greeting & consent → MC captured → **FMCSA verified**
2. Lane & window intake → **1–3 succinct pitches**
3. “What do you need on it?” → negotiate (≤3 rounds)
4. “Deal” → **confirmation + transfer**
5. **Post-call**: outcome + sentiment written to analytics

Real test runs show instant verification, clean pitches, 1–2 negotiation rounds, and successful booking confirmations.

---

## 4) How It Works

**Agent & Orchestration**

* HappyRobot runtime handles ASR/TTS, barge-in, timeouts, and tool calls.
* State memory tracks MC, lane, and negotiation anchors; **no fabricated numbers**—all pricing flows through the policy engine.

**API Services (FastAPI / SQLModel)**

* `verify_mc` → FMCSA QCMobile (`docket → dot → authority + oos`)
* `search_loads` → CSV/DB feed with smart date handling (“next future occurrence”), city/state matching, and ranking
* `evaluate_offer` → payer-side policy (floor %, tolerance, tick, 3-round cap, mile-based flexibility, regression & acceptance guards)
* `log_event` / `analytics_finalize` → events, offers, tool calls, utterances
* `metrics` → `/analytics/kpis` and `/analytics/db_usage`

**Data Model**

* `events`, `offers`, `tool_calls`, `utterances` (SQLite or Postgres)

---

## 5) Negotiation Safety (margin-aware, configurable)

* **Three-round cap**; counters never rise above prior anchors.
* **R1 low-offer confirmation** guard (catches ASR mishears like 1500→500).
* **Dynamic tolerance** for longer lanes; optional below-floor accept when it’s in Acme’s favor.
* “Go back to the previous price” is treated as acceptance of our last anchor.
* No “board” talk—internal math stays server-side.

**Tuning parameters** per lane/equipment: floor %, max rounds, tolerance, tick size, reefer upcharge, disclosure behavior.

---

## 6) Dashboard & Reporting

**KPIs**

* Eligible rate (FMCSA passes / attempts)
* Match rate (loads pitched / eligible)
* Conversion (booked / pitched), **avg rounds to close**
* Price delta vs internal benchmark
* Outcome distribution + end-of-call sentiment mix

**APIs**

* `GET /analytics/kpis?from=YYYY-MM-DD&to=YYYY-MM-DD`
* `GET /analytics/db_usage`

**Frontend**
React + Chakra UI single page; cards for KPIs, a funnel, and recent bookings table. Runtime config injects `API_BASE_URL`—same image across dev/stage/prod.

---

## 7) Deployment (Containers)

**Frontend container (nginx)**
Serves the SPA and injects runtime config (`API_BASE_URL`, `API_KEY`) into `/runtime-config.js`.

**API container (python-slim)**
Uvicorn/FastAPI with envs: `DATABASE_URL`, `FMCSA_API_KEY`, `FMCSA_BASE_URL`, `ALLOW_ORIGINS`, watchdog toggles.

Sample compose provided for local demos; runs anywhere (Render, ECS, K8s).

---

## 8) Handoff & Reliability (operational assurances)

* **Primary**: SIP transfer to Acme’s sales queue
* **Assurance**: built-in health check + **automatic PSTN fallback** to a backup DID
* **If both busy**: capture callback intent, persist contact & rate, and alert the team
* Minimal PII; audit trail preserved via `tool_calls` and `events`

---

## 9) Post Demo Plan

**1** Integrate SIP/FMCSA + load feed; set floors/tolerances.
**2** Shadow traffic off-hours; align counters with rep playbook.
**3** Limited production (20–30% of inbound); weekly KPI review.
**4** Scale to 50–70%; enable callback automation + CRM notes export.

**Success gates:** ≥60% pitched, ≥30% booked, ≤2.0 avg rounds, low transfer retries.

---

## 10) What We Need from Acme

* Load feed (CSV/API: id, O/D, windows, equipment, miles, benchmark, notes)
* SIP URI + backup DID and caller ID
* Business sign-off on floors & acceptance behavior per equipment

---

## 11) Key API Contracts (brief)

**`POST /verify_mc`** → `{ eligible, authority_status, source }`
**`POST /search_loads`** → `[{ load_id, origin, destination, pickup/delivery, equipment, miles, notes, benchmark }]`
**`POST /evaluate_offer`** → `{ decision: 'accept'|'counter'|'counter-final'|'confirm-low'|'reject', counter_rate, floor, next_* }`
**`POST /analytics_finalize`** → `{ session_id, mc_number, selected_load_id, agreed_rate, last_offer, rounds, sentiment, outcome }`

---

## 12) Why Choose This POC

* **Agent speed:** answers instantly; asks for the number, not the story.
* **Rep leverage:** handoffs are already verified and pre-negotiated.
* **Governance:** pricing logic is centralized, audited, and easy to tune.
* **Time-to-value:** runs with a CSV feed on day one; same images promote to prod.
* **Compliance-grade eligibility:** FMCSA authority + out-of-service checks with graceful ineligible exits.
* **Negotiation safety rails:** three-round cap, low-offer confirmation to catch ASR mishears, no counter regression, “previous price” = acceptance.
* **No-dead-end handoff:** SIP warm transfer with PSTN fallback and structured `transfer_failed` logging to trigger callbacks.
* **KPI-ready + auditable:** conversion, rounds, pricing deltas, sentiment—plus a full audit trail of offers and tool calls.
* **Security & data ownership:** env-scoped keys, minimal PII, strict CORS; your data stays in your DB with clean export paths.
