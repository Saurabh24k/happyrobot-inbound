Perfect—here’s a clean, final **Deployment & Reproduction Guide** written for a customer using a **real FMCSA key** (no mock flags). It includes how to access your running POC, how to wire their FMCSA key, and how to reproduce the deploy (cloud + local) using your existing containers and repo.

---

# Inbound Carrier Sales POC — Deployment & Reproduction Guide (FMCSA-Ready)

This guide shows Acme’s team how to **access the running POC**, configure it with a **real FMCSA key**, and **reproduce** the deployment (cloud or local). It also covers env vars, security, and troubleshooting.

---

## 1) Quick Access (Live)

* **Dashboard (frontend):**
  [https://inbound-frontend.onrender.com/dashboard](https://inbound-frontend.onrender.com/dashboard)

* **API Base URL (backend):**
  [https://happyrobot-inbound.onrender.com](https://happyrobot-inbound.onrender.com)

* **Auth header (all API calls):**
  `x-api-key: prod-xyz-123`

* **OpenAPI docs:**
  [https://happyrobot-inbound.onrender.com/openapi.json](https://happyrobot-inbound.onrender.com/openapi.json)

* **Health checks:**
  `GET /health` (service) • `GET /health/db` (database)

**Discovered API paths (for your reference):**
`/verify_mc`, `/search_loads`, `/evaluate_offer`, `/log_event`, `/health`, `/health/db`, `/analytics/db_usage`, `/analytics/finalize`, `/analytics/summary`, `/calls`, `/calls/{session_id}`

---

## 2) FMCSA Configuration (Real Key)

The backend validates carriers by calling FMCSA. To use **live** FMCSA:

1. **Provision your FMCSA web key** (your internal credential).
2. Set it on the API service as env var:

   * `FMCSA_API_KEY=<your-real-fmcsa-key>`

> Once set, `POST /verify_mc` will call FMCSA for eligibility (authority/out-of-service status). **Do not** include `mock:true` in production requests.

---

## 3) One-Minute Smoke Tests (Production)

> Replace `<real-mc-number>` with one of your known carrier MC numbers. Keep the API key header.

**A) Service health**

```bash
curl -sS 'https://happyrobot-inbound.onrender.com/health'
```

**B) FMCSA verification (live)**

```bash
curl -X POST 'https://happyrobot-inbound.onrender.com/verify_mc' \
  -H 'content-type: application/json' \
  -H 'x-api-key: prod-xyz-123' \
  -d '{"mc_number":"<real-mc-number>"}'
```

**C) Search loads (example lane)**

```bash
curl -X POST 'https://happyrobot-inbound.onrender.com/search_loads' \
  -H 'content-type: application/json' \
  -H 'x-api-key: prod-xyz-123' \
  -d '{
        "equipment_type":"Dry Van",
        "origin":"Newark, New Jersey",
        "destination":"Boston, MA",
        "pickup_window_start":"2025-08-06T09:00:00",
        "pickup_window_end":"2025-08-06T19:00:00"
      }'
```

**D) Evaluate an offer**

```bash
curl -X POST 'https://happyrobot-inbound.onrender.com/evaluate_offer' \
  -H 'content-type: application/json' \
  -H 'x-api-key: prod-xyz-123' \
  -d '{
        "load_id":"L010",
        "loadboard_rate":1400,
        "carrier_offer":1500,
        "round_num":1,
        "prev_counter":null,
        "anchor_high":null
      }'
```

---

## 4) HappyRobot Agent Wiring (Web Call Trigger)

> Per the challenge: **use the Web Call Trigger** (do not purchase a number).

Configure your agent’s tools (all calls send header `x-api-key: prod-xyz-123`):

| Tool in Agent        | Method + Path (under API Base) |
| -------------------- | ------------------------------ |
| `verify_mc`          | `POST /verify_mc`              |
| `search_loads`       | `POST /search_loads`           |
| `evaluate_offer`     | `POST /evaluate_offer`         |
| `log_event`          | `POST /log_event`              |
| `analytics_finalize` | `POST /analytics/finalize`     |

**Flow expectation:** MC → FMCSA verify → load pitch → up to 3 rounds negotiate → agreement → (optional) transfer → finalize + analytics.

---

## 5) Reproducing the Deployment

You can mirror this environment in three ways:

### A) Cloud (Render — Docker)

1. Repo: **[https://github.com/Saurabh24k/happyrobot-inbound](https://github.com/Saurabh24k/happyrobot-inbound)**
2. In Render: **New → Web Service (Docker)** → connect the repo → deploy.
3. Set environment variables in Render:

   * `API_KEY=prod-xyz-123`
   * `FMCSA_API_KEY=<your-real-fmcsa-key>`
   * `ALLOW_ORIGINS=https://inbound-frontend.onrender.com`
     *(use `*` for a demo, but lock to your frontend origin in prod)*
4. Deploy. The resulting base URL becomes your **API Base** for the agent and dashboard.

> Render serves HTTPS by default.

### B) Local (Docker)

From the repo root:

```bash
# Build API container
docker build -t inbound-api .

# Run API on localhost:8000 with your FMCSA key
docker run --rm -p 8000:8000 \
  -e API_KEY=dev-local-xyz \
  -e FMCSA_API_KEY='<your-real-fmcsa-key>' \
  -e ALLOW_ORIGINS='http://localhost:5173' \
  inbound-api
```

Smoke test locally:

```bash
curl -sS 'http://localhost:8000/health'
curl -X POST 'http://localhost:8000/verify_mc' \
  -H 'content-type: application/json' \
  -H 'x-api-key: dev-local-xyz' \
  -d '{"mc_number":"<real-mc-number>"}'
```

### C) Local (Python venv)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# .env (or shell) — set your real FMCSA key
export API_KEY=dev-local-xyz
export FMCSA_API_KEY=<your-real-fmcsa-key>
export ALLOW_ORIGINS=http://localhost:5173

uvicorn api.app:app --port 8000
```

---

## 6) Frontend (Dashboard) Settings

Visit: **[https://inbound-frontend.onrender.com/dashboard](https://inbound-frontend.onrender.com/dashboard)** → open **Settings & Connections**.

* **API Base URL:** `https://happyrobot-inbound.onrender.com`  *(or your local/Render base)*
* **API Key:** `prod-xyz-123`  *(or your local key)*
* Click **Save** → **Run All Tests**
  You should see: **Auth OK**, **Health OK**, **OpenAPI OK**.

*The Settings page supports export/import of config and shows discovered API paths.*

---

## 7) Environment Variables (Summary)

| Variable        | Purpose                                 | Example / Notes                                              |
| --------------- | --------------------------------------- | ------------------------------------------------------------ |
| `API_KEY`       | Backend API key for `x-api-key` auth    | `prod-xyz-123` (prod) / `dev-local-xyz` (local)              |
| `FMCSA_API_KEY` | **Real** FMCSA key for live eligibility | `<your-real-fmcsa-key>`                                      |
| `ALLOW_ORIGINS` | CORS allow-list                         | Prod: your dashboard origin • Local: `http://localhost:5173` |

> With `FMCSA_API_KEY` present, `/verify_mc` performs live FMCSA verification. No `mock` flag is used in production.

---

## 8) Security & Compliance

* **HTTPS**: Render provides TLS for the backend.
* **Auth**: All mutating endpoints expect `x-api-key` (set `API_KEY` server-side).
* **CORS**: Restrict `ALLOW_ORIGINS` to the dashboard’s origin in production.
* **PII**: Minimal data stored; payloads are limited to MC and session data needed for audit/analytics.

---

## 9) Troubleshooting (FMCSA-Focused)

- **401/403 (Unauthorized)**  
  Ensure your client sends `x-api-key` matching server `API_KEY`.

- **FMCSA verify returns an error**  
  - Confirm `FMCSA_API_KEY` is set on the API service.  
  - Retry with a **known-good MC number**.  
  - If still failing, verify the FMCSA key is active and not rate-limited.

- **Mock testing (optional for non-prod demos)**  
  If you need to test the pipeline **without a real MC / FMCSA call**, you can send:
  ```bash
  curl -X POST '<API_BASE>/verify_mc' \
    -H 'content-type: application/json' \
    -H 'x-api-key: <your-api-key>' \
    -d '{"mc_number":"123456","mock":true}'
  ```
  Remove the `mock` flag when using your real FMCSA key.

- **CORS errors in the browser**  
  Set `ALLOW_ORIGINS` to your exact dashboard origin (or `*` for demo).

- **OpenAPI discovery fails in Settings**  
  Check `GET /health`, then re-run **Run All Tests**. Confirm the **API Base URL** is correct.

---

## 10) Final Links

* **Dashboard:** [https://inbound-frontend.onrender.com/dashboard](https://inbound-frontend.onrender.com/dashboard)
* **API Base (prod):** [https://happyrobot-inbound.onrender.com](https://happyrobot-inbound.onrender.com)
* **OpenAPI:** [https://happyrobot-inbound.onrender.com/openapi.json](https://happyrobot-inbound.onrender.com/openapi.json)
* **Repo:** [https://github.com/Saurabh24k/happyrobot-inbound](https://github.com/Saurabh24k/happyrobot-inbound)

---

## 11) Reviewer Checklist

* [ ] API Base reachable over HTTPS
* [ ] `FMCSA_API_KEY` set on API service (non-empty)
* [ ] `API_KEY` set and clients use `x-api-key`
* [ ] Health & OpenAPI pass in dashboard Settings
* [ ] Web Call Trigger wired to the five endpoints with headers
* [ ] Live `POST /verify_mc` returns FMCSA-derived eligibility for a real MC

