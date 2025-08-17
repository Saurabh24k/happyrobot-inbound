# Inbound Carrier Sales — HappyRobot POC

Automated inbound carrier calls: verify MCs against FMCSA, pitch loads, negotiate up to 3 rounds, and hand off to a sales rep with clean KPIs and an audit trail.

---

## Live Demo Links

* **Dashboard (frontend):** [https://inbound-frontend.onrender.com/dashboard](https://inbound-frontend.onrender.com/dashboard)
* **API Base (backend):** [https://happyrobot-inbound.onrender.com](https://happyrobot-inbound.onrender.com)
* **OpenAPI (JSON):** [https://happyrobot-inbound.onrender.com/openapi.json](https://happyrobot-inbound.onrender.com/openapi.json)
* **Outbound Campaign (Live Agent):** [https://v2.platform.happyrobot.ai/deployments/le1prokaa63h/b4t9r7dfhbn7](https://v2.platform.happyrobot.ai/deployments/le1prokaa63h/b4t9r7dfhbn7)
* **Outbound Campaign (Workflow):** [https://v2.platform.happyrobot.ai/fde-saurabh/workflow/le1prokaa63h/editor/vgz18gdakjjg](https://v2.platform.happyrobot.ai/fde-saurabh/workflow/le1prokaa63h/editor/vgz18gdakjjg)

**Auth header (all API calls):** `x-api-key: prod-xyz-123`

---

## What’s in this repo

* **/api** — FastAPI service exposing:

  * `POST /verify_mc` — FMCSA eligibility (authority / out-of-service)
  * `POST /search_loads` — query loads by lane, equipment, pickup window
  * `POST /evaluate_offer` — 3-round negotiation policy engine
  * `POST /log_event` — record call events
  * `POST /analytics/finalize` — write structured call summary
  * Analytics & health endpoints (see OpenAPI)
* **/frontend** — React (Chakra UI) dashboard:

  * Settings page (API base + key, diagnostics)
  * Dashboard (KPIs: conversion, rounds, outcomes, sentiment, etc.)

---

## Architecture (high level)

* **HappyRobot** agent (Web Call Trigger) → calls your **API tools**
  `verify_mc` → `search_loads` → `evaluate_offer` → `log_event` → `analytics/finalize`
* **API** (FastAPI) behind HTTPS; `x-api-key` on every request; CORS allow-list
* **FMCSA**: live eligibility via your **FMCSA web key**
* **Dashboard** reads analytics endpoints for KPIs
* Containerized for cloud or local runs

---

## Quickstart

### 1) Cloud (Render)

1. Fork/clone: [https://github.com/Saurabh24k/happyrobot-inbound](https://github.com/Saurabh24k/happyrobot-inbound)
2. In **Render**: New → Web Service (Docker) → connect the repo → deploy
3. Set environment variables:

   * `API_KEY=prod-xyz-123`
   * `FMCSA_API_KEY=<your-real-fmcsa-key>`
   * `ALLOW_ORIGINS=https://inbound-frontend.onrender.com`
     *(Use `*` for a demo; restrict in prod.)*
4. Deploy. Use the resulting URL as your **API Base**.

> Render provides HTTPS automatically.

### 2) Local (Docker)

```bash
# from repo root
docker build -t inbound-api .

# run API on localhost:8000
docker run --rm -p 8000:8000 \
  -e API_KEY=dev-local-xyz \
  -e FMCSA_API_KEY='<your-real-fmcsa-key>' \
  -e ALLOW_ORIGINS='http://localhost:5173' \
  inbound-api
```

Smoke tests:

```bash
curl -sS 'http://localhost:8000/health'

curl -X POST 'http://localhost:8000/verify_mc' \
  -H 'content-type: application/json' \
  -H 'x-api-key: dev-local-xyz' \
  -d '{"mc_number":"<real-mc-number>"}'
```

### 3) Local (Python venv)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -r requirements.txt

# Environment
export API_KEY=dev-local-xyz
export FMCSA_API_KEY=<your-real-fmcsa-key>
export ALLOW_ORIGINS=http://localhost:5173

uvicorn api.app:app --port 8000
```

---

## Configure the Dashboard

Open: [https://inbound-frontend.onrender.com/dashboard](https://inbound-frontend.onrender.com/dashboard) → **Settings & Connections**

* **API Base URL:** `https://happyrobot-inbound.onrender.com` *(or your local URL)*
* **API Key:** `prod-xyz-123` *(or your local key)*
* Click **Save** → **Run All Tests**
  You should see: **Auth OK**, **Health OK**, **OpenAPI OK**.

The Settings page supports export/import of config and shows discovered API routes.

---

## FMCSA (live)

* Set `FMCSA_API_KEY` on the **API** service.
* Call `POST /verify_mc` with a **real** MC number *(no `mock` flag in prod)*:

  ```bash
  curl -X POST '<API_BASE>/verify_mc' \
    -H 'content-type: application/json' \
    -H 'x-api-key: <your-api-key>' \
    -d '{"mc_number":"<real-mc-number>"}'
  ```

> For non-prod demos only, you can test the pipeline with a mock flag:
>
> ```bash
> curl -X POST '<API_BASE>/verify_mc' \
>   -H 'content-type: application/json' \
>   -H 'x-api-key: <your-api-key>' \
>   -d '{"mc_number":"123456","mock":true}'
> ```

---

## HappyRobot Agent Wiring (Web Call Trigger)

Map tools to these endpoints (all with header `x-api-key: <your-api-key>`):

| Tool (Agent)        | Method & Path              |
| ------------------- | -------------------------- |
| verify\_mc          | `POST /verify_mc`          |
| search\_loads       | `POST /search_loads`       |
| evaluate\_offer     | `POST /evaluate_offer`     |
| log\_event          | `POST /log_event`          |
| analytics\_finalize | `POST /analytics/finalize` |

**Expected flow:** MC → FMCSA verify → pitch loads → ≤3 negotiation rounds → agreement → (transfer) → finalize analytics.

---

## API Cheatsheet (cURL)

**Health**

```bash
curl -sS '<API_BASE>/health'
```

**Verify MC (live)**

```bash
curl -X POST '<API_BASE>/verify_mc' \
  -H 'content-type: application/json' \
  -H 'x-api-key: <your-api-key>' \
  -d '{"mc_number":"<real-mc-number>"}'
```

**Search loads**

```bash
curl -X POST '<API_BASE>/search_loads' \
  -H 'content-type: application/json' \
  -H 'x-api-key: <your-api-key>' \
  -d '{
        "equipment_type":"Dry Van",
        "origin":"Newark, New Jersey",
        "destination":"Boston, MA",
        "pickup_window_start":"2025-08-06T09:00:00",
        "pickup_window_end":"2025-08-06T19:00:00"
      }'
```

**Evaluate offer**

```bash
curl -X POST '<API_BASE>/evaluate_offer' \
  -H 'content-type: application/json' \
  -H 'x-api-key: <your-api-key>' \
  -d '{
        "load_id":"L010",
        "loadboard_rate":1400,
        "carrier_offer":1500,
        "round_num":1,
        "prev_counter":null,
        "anchor_high":null
      }'
```

OpenAPI: `<API_BASE>/openapi.json` (includes `/verify_mc`, `/search_loads`, `/evaluate_offer`, `/log_event`, `/analytics/*`, `/health`, `/calls/*`)

---

## Environment Variables

| Variable        | Purpose                           | Example                                 |
| --------------- | --------------------------------- | --------------------------------------- |
| `API_KEY`       | API key required via `x-api-key`  | `prod-xyz-123`                          |
| `FMCSA_API_KEY` | Real FMCSA web key (live checks)  | `<your-real-fmcsa-key>`                 |
| `ALLOW_ORIGINS` | CORS allow-list (frontend origin) | `https://inbound-frontend.onrender.com` |

> With `FMCSA_API_KEY` set, `/verify_mc` performs **live** FMCSA verification.

---

## Security

* **HTTPS** (cloud): served by the platform (e.g., Render)
* **Auth**: all endpoints expect `x-api-key`
* **CORS**: restrict `ALLOW_ORIGINS` to your dashboard origin in production
* **Data**: minimal PII; events/analytics only for auditability

---

## Troubleshooting

**401/403 (Unauthorized)**
Ensure the client sends `x-api-key` that matches server `API_KEY`.

**FMCSA verify error**

* Confirm `FMCSA_API_KEY` is set on the API service.
* Retry with a known-good MC number.
* Check that your FMCSA key is active / not rate-limited.

**CORS errors (browser)**
Set `ALLOW_ORIGINS` to your **exact** dashboard origin (or `*` for demo).

**OpenAPI / Settings diagnostics fail**

* Check `GET /health`.
* Re-run **Run All Tests**.
* Confirm the **API Base URL** is correct.

---

## License

TBD by repository owner.

---

## Contact

* **Dashboard:** [https://inbound-frontend.onrender.com/dashboard](https://inbound-frontend.onrender.com/dashboard)
* **API Base:** [https://happyrobot-inbound.onrender.com](https://happyrobot-inbound.onrender.com)
* **OpenAPI:** [https://happyrobot-inbound.onrender.com/openapi.json](https://happyrobot-inbound.onrender.com/openapi.json)
* **Repo:** [https://github.com/Saurabh24k/happyrobot-inbound](https://github.com/Saurabh24k/happyrobot-inbound)
