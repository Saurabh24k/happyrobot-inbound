
# HappyRobot Inbound Carrier Sales — Backend API (Starter)

This is the **minimal, production-ready starter** for your HappyRobot inbound agent backend.
It exposes HTTP tools the agent will call during a live web-triggered call.

## What this repo does (today)
- **/search_loads**: reads `data/loads.csv`, filters by equipment/lane/pickup window, returns up to 3 loads.
- **/verify_mc**: returns a **mock** eligibility (we'll swap to the real FMCSA adapter next).
- **/log_event**: appends structured events to `data/events.jsonl` (for simple auditing/metrics later).
- Secured by an **API key** via the `x-api-key` header.
- Ready for **Docker** and **Render** deployment.

> We'll add `/evaluate_offer` (negotiation), `/metrics`, and the real FMCSA check in the next steps.

---

## Quickstart (local)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env to set API_KEY and FMCSA_API_KEY (optional for now)

uvicorn api.app:app --reload --port 8000
```

### Smoke tests
```bash
# Search sample loads
curl -X POST http://localhost:8000/search_loads   -H "x-api-key: dev-local-xyz" -H "Content-Type: application/json"   -d '{"equipment_type":"Dry Van","origin":"Chicago, IL","destination":"Dallas, TX"}'

# Verify MC (mock)
curl -X POST http://localhost:8000/verify_mc   -H "x-api-key: dev-local-xyz" -H "Content-Type: application/json"   -d '{"mc_number":"123456"}'

# Log event
curl -X POST http://localhost:8000/log_event   -H "x-api-key: dev-local-xyz" -H "Content-Type: application/json"   -d '{"event":"test","note":"hello"}'
```

---

## Deploy to Render (Docker)

1. **Push this repo to GitHub** (or GitLab/Bitbucket).
2. In Render, create a **new Web Service** → **Use Docker** → point to this repo.
3. Set environment variables:
   - `API_KEY` (e.g., `prod-xyz-123`)
   - `FMCSA_API_KEY` (your real key)
   - `ALLOW_ORIGINS` = `*` (or your domain)
4. Click **Deploy**. After it turns green, you’ll get a public base URL like:
   - `https://happyrobot-inbound-api.onrender.com`
5. In HappyRobot, define tools pointing to that base URL, and add header:
   - `x-api-key: <your API_KEY>`

> For future infra-as-code, you can add a `render.yaml` blueprint, but the UI flow is quickest for now.

---

## Repo layout

```
api/
  app.py                # FastAPI app with endpoints and API key auth
  config.py             # Environment configuration (API keys, CORS, etc.)
  adapters/
    fmcsa.py            # FMCSA adapter (mock now; real HTTP coming next)
  services/
    search.py           # CSV-backed load search
  models/
    events.py           # (placeholder for future DB models)
data/
  loads.csv             # Sample loads (edit/replace with your data)
  events.jsonl          # Appended call events (created at runtime)
Dockerfile              # Container image for Render
requirements.txt        # Python deps
.env.example            # Example environment variables
README.md               # This file
```

---

## Next milestones

1. Swap `/verify_mc` to call the **real FMCSA** API using your key (keep mock as a fallback).
2. Add `/evaluate_offer` negotiation policy and prompt loop in HappyRobot (3 rounds max).
3. Persist events to SQLite and expose `/metrics` → simple dashboard page.
4. Harden security (rate limiting; schema validation; logs).
