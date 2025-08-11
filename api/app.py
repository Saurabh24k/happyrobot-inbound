from fastapi import FastAPI, Header, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date, time, timezone
from pathlib import Path
from collections import defaultdict
import json

from .config import API_KEY, ALLOW_ORIGINS
from .adapters import fmcsa
from .services.search import search_loads
from .services.negotiate import evaluate_offer as eval_offer

from .db import init_db, get_session
from .models import Event
from sqlmodel import select


app = FastAPI(title="HappyRobot Inbound API (Starter)")

# --- Startup ---------------------------------------------------------------
@app.on_event("startup")
def _startup():
    init_db()

# --- CORS ------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if ALLOW_ORIGINS == "*" else [ALLOW_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auth dependency -------------------------------------------------------
def require_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """Require header: x-api-key: <API_KEY>"""
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return None

# --- Pydantic models -------------------------------------------------------
class VerifyMCRequest(BaseModel):
    mc_number: Union[str, int] = Field(..., description="Carrier MC (docket) number")
    mock: Optional[bool] = Field(False, description="If true, return simulated 'eligible' result")

class VerifyMCResponse(BaseModel):
    mc_number: str
    eligible: bool
    authority_status: Optional[str] = None
    safety_rating: Optional[str] = None
    source: str

class SearchLoadsRequest(BaseModel):
    equipment_type: str
    origin: Optional[str] = None
    destination: Optional[str] = None
    pickup_window_start: Optional[str] = None
    pickup_window_end: Optional[str] = None

class Load(BaseModel):
    load_id: str
    origin: str
    destination: str
    pickup_datetime: str
    delivery_datetime: str
    equipment_type: str
    loadboard_rate: float
    notes: Optional[str] = None
    weight: Optional[float] = None
    commodity_type: Optional[str] = None
    num_of_pieces: Optional[int] = None
    miles: Optional[float] = None
    dimensions: Optional[str] = None

class SearchLoadsResponse(BaseModel):
    results: List[Load]

class EvaluateOfferRequest(BaseModel):
    load_id: str
    loadboard_rate: float
    carrier_offer: float
    round_num: int = 1

class EvaluateOfferResponse(BaseModel):
    decision: str          # accept | counter | counter-final | reject
    counter_rate: float
    floor: float
    max_rounds: int

class LogEventRequest(BaseModel):
    event: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

# --- Helpers for analytics -------------------------------------------------
def _avg(nums: List[float]) -> Optional[float]:
    if not nums:
        return None
    return round(sum(nums) / len(nums), 1)

def _range_to_utc(s: str, u: str) -> tuple[datetime, datetime]:
    """since/until (YYYY-MM-DD) -> naive datetimes covering full days."""
    s_date = datetime.strptime(s, "%Y-%m-%d").date()
    u_date = datetime.strptime(u, "%Y-%m-%d").date()
    start = datetime.combine(s_date, time.min)  # no tzinfo
    end   = datetime.combine(u_date, time.max)  # no tzinfo
    return start, end

# --- Endpoints: core features ---------------------------------------------
@app.post("/verify_mc", response_model=VerifyMCResponse, dependencies=[Depends(require_api_key)])
def verify_mc_endpoint(req: VerifyMCRequest):
    """Verify carrier MC eligibility (FMCSA or mock)."""
    mc = str(req.mc_number)
    result = fmcsa.verify_mc(mc, mock=bool(req.mock))
    return VerifyMCResponse(**result)

@app.post("/search_loads", response_model=SearchLoadsResponse, dependencies=[Depends(require_api_key)])
def search_loads_endpoint(req: SearchLoadsRequest):
    """Search loads from CSV with simple filters and return top 3."""
    results = search_loads(
        equipment_type=req.equipment_type,
        origin=req.origin,
        destination=req.destination,
        pickup_window_start=req.pickup_window_start,
        pickup_window_end=req.pickup_window_end,
        limit=3,
    )
    loads = [Load(**r) for r in results]
    return SearchLoadsResponse(results=loads)

@app.post("/evaluate_offer", response_model=EvaluateOfferResponse, dependencies=[Depends(require_api_key)])
def evaluate_offer_ep(req: EvaluateOfferRequest):
    res = eval_offer(
        loadboard_rate=req.loadboard_rate,
        carrier_offer=req.carrier_offer,
        round_num=req.round_num,
    )
    return EvaluateOfferResponse(**res)

@app.post("/log_event", dependencies=[Depends(require_api_key)])
def log_event(req: LogEventRequest):
    """
    Append a structured event to data/events.jsonl (for audit) AND persist to DB.
    """
    events_path = Path(__file__).resolve().parents[1] / "data" / "events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "ts": datetime.utcnow().isoformat(),
        "event": (req.event or "unspecified"),
        "data": (req.data or {}),
    }

    # 1) Keep file-based append for simple auditing
    with open(events_path, "a") as f:
        f.write(json.dumps(record) + "\n")

    # 2) Persist to DB
    data = record["data"]
    ev = Event(
        event=record["event"],
        session_id=data.get("session_id"),
        mc=data.get("mc"),
        load_id=data.get("load_id"),
        sentiment=(data.get("sentiment") or "").lower() or None,
        rounds=int(data["rounds"]) if str(data.get("rounds", "")).isdigit() else None,
        agreed_rate=float(data["agreed_rate"]) if data.get("agreed_rate") is not None else None,
        loadboard_rate=float(data["loadboard_rate"]) if data.get("loadboard_rate") is not None else None,
        equipment_type=data.get("equipment_type"),
        extra=data,
    )
    with get_session() as s:
        s.add(ev)
        s.commit()

    return {"status": "ok", "written": True}

@app.get("/health")
def health():
    return {"status": "ok"}

# --- Endpoints: analytics + calls (DB-backed) -----------------------------
@app.get("/analytics/summary", dependencies=[Depends(require_api_key)])
def analytics_summary(
    since: str = Query(..., description="YYYY-MM-DD"),
    until: str = Query(..., description="YYYY-MM-DD"),
):
    start, end = _range_to_utc(since, until)

    with get_session() as sess:
        q = select(Event).where(Event.ts >= start, Event.ts <= end)
        rows = list(sess.exec(q))

    if not rows:
        return {
            "totals": {"calls": 0, "booked": 0, "no_agreement": 0, "no_match": 0, "failed_auth": 0, "abandoned": 0},
            "rates": {"avg_board": None, "avg_agreed": None, "avg_delta": None},
            "sentiment": {"positive": 0, "neutral": 0, "negative": 0},
            "by_equipment": [],
            "timeseries": [],
        }

    # Group events by session (a "call")
    sessions: dict[str, list[Event]] = defaultdict(list)
    for e in rows:
        sid = e.session_id or "unknown"
        sessions[sid].append(e)

    # Totals by event name (we count occurrences; last event per session is usually outcome)
    alias = {
        "booked": "booked",
        "no-agreement": "no_agreement",
        "no-match": "no_match",
        "failed-auth": "failed_auth",
        "abandoned": "abandoned",
        "transfer_failed": "abandoned",
    }
    totals = {"calls": len(sessions), "booked": 0, "no_agreement": 0, "no_match": 0, "failed_auth": 0, "abandoned": 0}
    sentiment = {"positive": 0, "neutral": 0, "negative": 0}
    agreed_rates: List[float] = []
    board_rates: List[float] = []
    deltas: List[float] = []
    by_eq: dict[str, dict] = defaultdict(lambda: {"booked": 0, "sum": 0.0, "n": 0})

    for e in rows:
        k = alias.get(e.event)
        if k in totals:
            totals[k] += 1
        if e.sentiment in sentiment:
            sentiment[e.sentiment] += 1
        if e.agreed_rate is not None:
            agreed_rates.append(e.agreed_rate)
        if e.loadboard_rate is not None:
            board_rates.append(e.loadboard_rate)
        if e.agreed_rate is not None and e.loadboard_rate is not None:
            deltas.append(e.agreed_rate - e.loadboard_rate)
        if e.event == "booked" and e.equipment_type:
            by_eq[e.equipment_type]["booked"] += 1
            if e.agreed_rate is not None:
                by_eq[e.equipment_type]["sum"] += e.agreed_rate
                by_eq[e.equipment_type]["n"] += 1

    by_equipment = [
        {"equipment_type": k, "booked": v["booked"], "avg_rate": round(v["sum"] / v["n"], 0) if v["n"] else None}
        for k, v in by_eq.items()
    ]

    # Timeseries by day
    ts = defaultdict(lambda: {"calls": 0, "booked": 0})
    for sid, evs in sessions.items():
        evs.sort(key=lambda x: x.ts)
        first_day = evs[0].ts.date()
        if start.date() <= first_day <= end.date():
            ts[first_day]["calls"] += 1
        for e in evs:
            if e.event == "booked":
                d = e.ts.date()
                if start.date() <= d <= end.date():
                    ts[d]["booked"] += 1

    timeseries = [
        {"date": d.isoformat(), "calls": v["calls"], "booked": v["booked"]}
        for d, v in sorted(ts.items(), key=lambda kv: kv[0])
    ]

    return {
        "totals": totals,
        "rates": {"avg_board": _avg(board_rates), "avg_agreed": _avg(agreed_rates), "avg_delta": _avg(deltas)},
        "sentiment": sentiment,
        "by_equipment": by_equipment,
        "timeseries": timeseries,
    }

@app.get("/calls", dependencies=[Depends(require_api_key)])
def calls_list(
    since: str = Query(..., description="YYYY-MM-DD"),
    until: str = Query(..., description="YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    start, end = _range_to_utc(since, until)

    with get_session() as sess:
        q = select(Event).where(Event.ts >= start, Event.ts <= end)
        rows = list(sess.exec(q))

    sessions: dict[str, list[Event]] = defaultdict(list)
    for e in rows:
        sid = e.session_id or "unknown"
        sessions[sid].append(e)

    items: List[Dict[str, Any]] = []
    for sid, evs in sessions.items():
        evs.sort(key=lambda x: x.ts)
        first, last = evs[0], evs[-1]
        items.append({
            "id": sid,
            "started_at": first.ts.isoformat(),
            "duration_sec": 0,  # TODO: populate if/when you log duration
            "mc_number": first.mc or last.mc,
            "selected_load_id": first.load_id or last.load_id,
            "agreed_rate": last.agreed_rate,
            "negotiation_round": last.rounds,
            "outcome": last.event,
            "sentiment": last.sentiment,
        })

    items.sort(key=lambda r: r["started_at"], reverse=True)
    total = len(items)
    return {"items": items[offset:offset + limit], "total": total}

@app.get("/calls/{session_id}", dependencies=[Depends(require_api_key)])
def call_detail(session_id: str):
    with get_session() as sess:
        evs = list(sess.exec(select(Event).where(Event.session_id == session_id)))
    if not evs:
        raise HTTPException(status_code=404, detail="Call not found")
    evs.sort(key=lambda x: x.ts)
    first, last = evs[0], evs[-1]
    return {
        "id": session_id,
        "started_at": first.ts.isoformat(),
        "duration_sec": 0,
        "mc_number": first.mc or last.mc,
        "selected_load_id": first.load_id or last.load_id,
        "offers": [],        # TODO: extend if you log offer steps
        "outcome": last.event,
        "sentiment": last.sentiment,
        "transcript": [],    # TODO: extend if you log conversation turns
        "tool_calls": [],    # TODO: extend if you log verify/search/evaluate calls
    }
