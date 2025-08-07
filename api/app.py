from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pathlib import Path
import json

from .config import API_KEY, ALLOW_ORIGINS
from .adapters import fmcsa
from .services.search import search_loads

app = FastAPI(title="HappyRobot Inbound API (Starter)")

# ----- CORS ---------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if ALLOW_ORIGINS == "*" else [ALLOW_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Security dependency ------------------------------------------------
def require_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """
    Require header: x-api-key: <API_KEY>
    """
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return None

# ----- Models -------------------------------------------------------------
class VerifyMCRequest(BaseModel):
    mc_number: Union[str, int] = Field(
        ...,
        description="Carrier MC (docket) number (accepts string or int)"
    )
    mock: Optional[bool] = Field(
         False,
         description="If true, return a simulated 'eligible' result for testing"
     )
    
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

class LogEventRequest(BaseModel):
    # Free-form payload for now; we'll structure later
    event: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

# ----- Endpoints ----------------------------------------------------------

@app.post(
    "/verify_mc",
    response_model=VerifyMCResponse,
    dependencies=[Depends(require_api_key)],
)
def verify_mc_endpoint(req: VerifyMCRequest):
    """
    Verify carrier MC eligibility.
    - If req.mock is true, return a simulated 'eligible' response (useful for demos).
    - Else call FMCSA (if FMCSA_API_KEY is set), with safe fallbacks.
    """
    mc = str(req.mc_number)          # string for downstream call
    result = fmcsa.verify_mc(mc, mock=bool(req.mock))
    return VerifyMCResponse(**result)

@app.post(
    "/search_loads",
    response_model=SearchLoadsResponse,
    dependencies=[Depends(require_api_key)],
)
def search_loads_endpoint(req: SearchLoadsRequest):
    """
    Search loads from CSV with simple filters and return top 3.
    """
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

@app.post(
    "/log_event",
    dependencies=[Depends(require_api_key)],
)
def log_event(req: LogEventRequest):
    """
    Append a structured event to data/events.jsonl for simple auditing/metrics.
    """
    events_path = Path(__file__).resolve().parents[1] / "data" / "events.jsonl"
    record = {
        "ts": datetime.utcnow().isoformat(),
        "event": req.event or "unspecified",
        "data": req.data or {},
    }
    with open(events_path, "a") as f:
        f.write(json.dumps(record) + "\n")
    return {"status": "ok", "written": True}

@app.get("/health")
def health():
    return {"status": "ok"}
