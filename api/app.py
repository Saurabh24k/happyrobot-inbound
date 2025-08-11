# api/app.py
from fastapi import FastAPI, Header, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date, time
from pathlib import Path
from collections import defaultdict
import json

from .config import API_KEY, ALLOW_ORIGINS
from .adapters import fmcsa
from .services.search import search_loads
from .services.negotiate import evaluate_offer as eval_offer

from .db import init_db, get_session
from .models import Event, Offer, ToolCall, Utterance
from sqlmodel import select

app = FastAPI(title="HappyRobot Inbound API (Starter)")

# ── Startup ────────────────────────────────────────────────────────────────
@app.on_event("startup")
def _startup():
    init_db()

# ── CORS ───────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if ALLOW_ORIGINS == "*" else [ALLOW_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth dependency ────────────────────────────────────────────────────────
def require_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """Require header: x-api-key: <API_KEY>"""
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return None

# ── Pydantic models ────────────────────────────────────────────────────────
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

# ── Helpers ────────────────────────────────────────────────────────────────
def _avg(nums: List[float]) -> Optional[float]:
    if not nums:
        return None
    return round(sum(nums) / len(nums), 1)

def _range_to_utc(s: str, u: str) -> tuple[datetime, datetime]:
    """since/until (YYYY-MM-DD) -> naive datetimes covering full days."""
    s_date = datetime.strptime(s, "%Y-%m-%d").date()
    u_date = datetime.strptime(u, "%Y-%m-%d").date()
    start = datetime.combine(s_date, time.min)
    end   = datetime.combine(u_date, time.max)
    return start, end

def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None

def _to_int(x: Any) -> Optional[int]:
    try:
        if x is None or str(x).strip() == "":
            return None
        return int(x)
    except Exception:
        return None

# ── Core endpoints ─────────────────────────────────────────────────────────
@app.post("/verify_mc", response_model=VerifyMCResponse, dependencies=[Depends(require_api_key)])
def verify_mc_endpoint(req: VerifyMCRequest):
    """Verify carrier MC eligibility (FMCSA or mock)."""
    mc = str(req.mc_number)
    result = fmcsa.verify_mc(mc, mock=bool(req.mock))
    return VerifyMCResponse(**result)

@app.post("/search_loads", response_model=SearchLoadsResponse, dependencies=[Depends(require_api_key)])
def search_loads_endpoint(req: SearchLoadsRequest):
    """Search loads from CSV with simple filters and return top results."""
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

# ── Logging & artifacts ────────────────────────────────────────────────────
@app.post("/log_event", dependencies=[Depends(require_api_key)])
def log_event(req: LogEventRequest):
    """
    Append a structured event to data/events.jsonl (audit) AND persist to DB.

    Accepts:
      - event: 'booked' | 'no-agreement' | 'no-match' | 'failed-auth' | 'abandoned'
               plus optional: 'offer', 'tool-call', 'final-artifacts'
      - data: free-form payload; we look for keys like:
              session_id, mc, load_id, sentiment, rounds, agreed_rate, loadboard_rate, equipment_type
              and arrays: offers[], tool_calls[], transcript[] (when event = final-artifacts)

    Also tolerates legacy keys like 'quoted_rate' (we'll store as a carrier offer step).
    """
    events_path = Path(__file__).resolve().parents[1] / "data" / "events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.utcnow()
    data: Dict[str, Any] = req.data or {}
    record = {
        "ts": now.isoformat(),
        "event": (req.event or "unspecified"),
        "data": data,
    }

    # Always keep a file audit trail
    with open(events_path, "a") as f:
        f.write(json.dumps(record) + "\n")

    ev_name = (req.event or "unspecified").lower()
    sid = (data.get("session_id") or data.get("sessionId") or "").strip() or None

    with get_session() as s:
        # 1) Final outcome rows → feed analytics/dashboard
        final_labels = {"booked", "no-agreement", "no-match", "failed-auth", "abandoned", "transfer_failed"}
        if ev_name in final_labels:
            # map transfer_failed into abandoned for analytics later
            event_for_row = "abandoned" if ev_name == "transfer_failed" else ev_name
            e = Event(
                event=event_for_row,
                session_id=sid,
                mc=data.get("mc"),
                load_id=data.get("load_id"),
                sentiment=(data.get("sentiment") or None),
                rounds=_to_int(data.get("rounds")),
                agreed_rate=_to_float(data.get("agreed_rate")),
                loadboard_rate=_to_float(data.get("loadboard_rate")),
                equipment_type=data.get("equipment_type"),
                extra=data,
            )
            s.add(e)

            # If a legacy 'quoted_rate' was sent on 'booked', record it as a carrier offer
            qrate = _to_float(data.get("quoted_rate"))
            if sid and qrate is not None:
                s.add(Offer(session_id=sid, who="carrier", value=qrate, t=now))

            # If agreed_rate exists on 'booked', add agent-side closing offer as well
            arate = _to_float(data.get("agreed_rate"))
            if sid and arate is not None:
                s.add(Offer(session_id=sid, who="agent", value=arate, t=now))

        # 2) Single 'offer' events (optional, if you choose to emit during negotiation)
        if ev_name == "offer" and sid:
            who = (data.get("who") or "carrier").lower()
            val = _to_float(data.get("value"))
            if val is not None:
                s.add(Offer(session_id=sid, who=who, value=val, t=now))

        # 3) Single 'tool-call' events (optional)
        if ev_name == "tool-call" and sid:
            fn = data.get("fn") or "unknown"
            ok = data.get("ok")
            info = {k: v for k, v in data.items() if k not in {"session_id", "fn", "ok"}}
            s.add(ToolCall(session_id=sid, fn=fn, ok=bool(ok) if ok is not None else None, info=info))

        # 4) Bulk artifacts: offers[], tool_calls[], transcript[] (preferred one-shot at call end)
        if ev_name == "final-artifacts" and sid:
            for o in (data.get("offers") or []):
                val = _to_float(o.get("value"))
                if val is None:
                    continue
                who = (o.get("who") or "carrier").lower()
                t = now
                try:
                    t_raw = o.get("t")
                    if t_raw:
                        t = datetime.fromisoformat(str(t_raw).replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    pass
                s.add(Offer(session_id=sid, who=who, value=val, t=t))

            for tc in (data.get("tool_calls") or []):
                fn = tc.get("fn") or "unknown"
                ok = tc.get("ok")
                info = {k: v for k, v in tc.items() if k not in {"fn", "ok"}}
                s.add(ToolCall(session_id=sid, fn=fn, ok=bool(ok) if ok is not None else None, info=info))

            for line in (data.get("transcript") or []):
                role = (line.get("role") or "user").lower()
                text = (line.get("text") or "").strip()
                if text:
                    s.add(Utterance(session_id=sid, role=role, text=text, t=now))

        s.commit()

    return {"status": "ok", "written": True}

@app.get("/health")
def health():
    return {"status": "ok"}

# ── Analytics & calls ──────────────────────────────────────────────────────
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

    # Group by session
    sessions: dict[str, list[Event]] = defaultdict(list)
    for e in rows:
        sid = e.session_id or "unknown"
        sessions[sid].append(e)

    # Totals
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

        offers = list(sess.exec(
            select(Offer).where(Offer.session_id == session_id).order_by(Offer.t.asc())
        ))
        tools = list(sess.exec(
            select(ToolCall).where(ToolCall.session_id == session_id).order_by(ToolCall.id.asc())
        ))
        lines = list(sess.exec(
            select(Utterance).where(Utterance.session_id == session_id).order_by(Utterance.id.asc())
        ))

    # Earliest timestamp across artifacts
    earliest = first.ts
    if offers:
        earliest = min(earliest, offers[0].t)
    if lines:
        earliest = min(earliest, lines[0].t)

    return {
        "id": session_id,
        "started_at": earliest.isoformat(),
        "duration_sec": 0,
        "mc_number": first.mc or last.mc,
        "selected_load_id": first.load_id or last.load_id,
        "offers": [{"t": o.t.isoformat(), "who": o.who, "value": o.value} for o in offers],
        "outcome": last.event,
        "sentiment": last.sentiment,
        "transcript": [{"role": l.role, "text": l.text} for l in lines],
        "tool_calls": [{"fn": t.fn, "ok": t.ok, **(t.info or {})} for t in tools],
    }
