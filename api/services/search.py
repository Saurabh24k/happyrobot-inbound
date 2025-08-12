# api/services/search.py
from __future__ import annotations
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime, timedelta
import os
import re
import logging

# Prefer pandas, but never crash the API if it isn't available
try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore

log = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────
# Dataset location (overridable via env)
# Default resolves to /app/data/loads.csv when packaged in Docker
# ────────────────────────────────────────────────────────────────────
_DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data" / "loads.csv"
CSV_PATH = Path(os.getenv("LOADS_CSV_PATH", str(_DEFAULT_CSV)))

# Try python-dateutil for smarter parsing; fall back to pandas if missing
try:
    from dateutil import parser as du_parser
except Exception:  # pragma: no cover
    du_parser = None  # type: ignore

# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()

# State map: "texas" -> "tx", "tx" -> "tx"
_STATES = {
    "alabama": "al", "alaska": "ak", "arizona": "az", "arkansas": "ar",
    "california": "ca", "colorado": "co", "connecticut": "ct", "delaware": "de",
    "florida": "fl", "georgia": "ga", "hawaii": "hi", "idaho": "id",
    "illinois": "il", "indiana": "in", "iowa": "ia", "kansas": "ks",
    "kentucky": "ky", "louisiana": "la", "maine": "me", "maryland": "md",
    "massachusetts": "ma", "michigan": "mi", "minnesota": "mn", "mississippi": "ms",
    "missouri": "mo", "montana": "mt", "nebraska": "ne", "nevada": "nv",
    "new hampshire": "nh", "new jersey": "nj", "new mexico": "nm", "new york": "ny",
    "north carolina": "nc", "north dakota": "nd", "ohio": "oh", "oklahoma": "ok",
    "oregon": "or", "pennsylvania": "pa", "rhode island": "ri", "south carolina": "sc",
    "south dakota": "sd", "tennessee": "tn", "texas": "tx", "utah": "ut",
    "vermont": "vt", "virginia": "va", "washington": "wa", "west virginia": "wv",
    "wisconsin": "wi", "wyoming": "wy",
}
_STATES.update({abbr: abbr for abbr in _STATES.values()})

def _state_abbr(text: str) -> Optional[str]:
    """Return 2-letter state abbr if text looks like a state name/abbr."""
    t = _norm(text)
    return _STATES.get(t)

def _match_city_state(series, query: str):
    """
    True where series contains city substring OR ends with ', XX' (state).
    Assumes `series` is a pandas Series of strings.
    """
    q = _norm(query)
    abbr = _state_abbr(q)
    s = series.fillna("").astype(str)
    s_lower = s.str.lower()
    if abbr:  # user gave a state
        state_regex = re.compile(rf",\s*{abbr}$", flags=re.I)
        return s_lower.str.contains(q) | s.str.contains(state_regex)
    return s_lower.str.contains(q)

# ── Date normalization: assume next future occurrence if year omitted ──

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

def _parse_with_default_year(text: Optional[str], now: datetime) -> Optional[datetime]:
    if not text:
        return None
    raw = text.strip()
    if not raw:
        return None

    had_year = bool(_YEAR_RE.search(raw))

    if du_parser:
        # Use current year as default when year is missing
        default_base = datetime(now.year, 1, 1, 0, 0, 0)
        try:
            dt = du_parser.parse(raw, default=default_base, fuzzy=True)
        except Exception:
            return None
    else:
        if pd is None:
            return None
        # Fallback: if no 4-digit year present, append current year for parsing
        to_parse = raw if had_year else f"{raw} {now.year}"
        dt = pd.to_datetime(to_parse, errors="coerce")
        if pd.isna(dt):
            return None
        dt = dt.to_pydatetime()

    # If no year provided and parsed dt is in the past, roll it to next year
    if not had_year and dt < now:
        try:
            dt = dt.replace(year=now.year + 1)
        except ValueError:
            # Handle 2/29 etc.
            dt = dt + timedelta(days=365)

    return dt

def _normalize_future_window(
    start_str: Optional[str],
    end_str: Optional[str],
    now: Optional[datetime] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Normalize to the next future occurrence when year is missing.
    Ensure end >= start. Build a ~12h window if only one bound provided.
    Returns ISO strings (YYYY-MM-DDTHH:MM:SS) or None.
    """
    now = now or datetime.now()

    start_dt = _parse_with_default_year(start_str, now) if start_str else None
    end_dt   = _parse_with_default_year(end_str,   now) if end_str   else None

    # If only one bound given, create a 12h window
    if start_dt and not end_dt:
        end_dt = start_dt + timedelta(hours=12)
    if end_dt and not start_dt:
        start_dt = end_dt - timedelta(hours=12)

    # Align if both exist but end < start (e.g., times only spanning midnight)
    if start_dt and end_dt and end_dt < start_dt:
        end_dt = end_dt.replace(year=start_dt.year, month=start_dt.month, day=start_dt.day)
        if end_dt < start_dt:
            end_dt = end_dt + timedelta(days=1)

    fmt = "%Y-%m-%dT%H:%M:%S"
    return (
        start_dt.strftime(fmt) if start_dt else None,
        end_dt.strftime(fmt) if end_dt else None,
    )

# ────────────────────────────────────────────────────────────────────
# Main search
# ────────────────────────────────────────────────────────────────────

_REQUIRED_COLS = {
    "load_id", "equipment_type", "origin", "destination", "pickup_datetime",
    "delivery_datetime", "miles", "weight", "dimensions", "notes",
    "loadboard_rate", "commodity_type", "num_of_pieces"
}

def _read_df_safely() -> Optional["pd.DataFrame"]:
    """
    Read the CSV into a DataFrame. If anything goes wrong, return None.
    Ensures required columns exist (creates empty ones if missing).
    """
    if pd is None:
        log.warning("pandas is not available; cannot read CSV.")
        return None

    path = CSV_PATH
    if not path.exists():
        log.warning("loads.csv not found at %s", path)
        return None

    try:
        df = pd.read_csv(path)
    except Exception as e:  # pragma: no cover
        log.exception("Failed to read CSV at %s: %s", path, e)
        return None

    # Create any missing required columns to avoid downstream crashes
    for col in _REQUIRED_COLS - set(df.columns):
        df[col] = None

    # Coerce to sensible types where possible (but never raise)
    try:
        if "loadboard_rate" in df:
            df["loadboard_rate"] = pd.to_numeric(df["loadboard_rate"], errors="coerce")
        if "miles" in df:
            df["miles"] = pd.to_numeric(df["miles"], errors="coerce")
        if "num_of_pieces" in df:
            df["num_of_pieces"] = pd.to_numeric(df["num_of_pieces"], errors="coerce").astype("Int64")
    except Exception:
        pass

    return df

def search_loads(
    equipment_type: str,
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    pickup_window_start: Optional[str] = None,
    pickup_window_end: Optional[str] = None,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """
    Return up to `limit` loads ranked by lane relevance.
    - Accepts city/state names or abbreviations for origin/destination.
    - Interprets dates without a year as the *next future occurrence*.
    - Progressively widens filters if nothing matches (first drop destination, then origin).
    - NEVER raises (returns []) so the API won’t 500.
    """
    df = _read_df_safely()
    if df is None or df.empty:
        return []

    # Equipment filter (required)
    et = (equipment_type or "").strip().lower()
    if not et:
        return []
    try:
        df = df[df["equipment_type"].fillna("").astype(str).str.lower() == et]
    except Exception:
        return []

    # Time window: normalize to next-future when year missing
    if pickup_window_start or pickup_window_end:
        pickup_window_start, pickup_window_end = _normalize_future_window(
            pickup_window_start, pickup_window_end
        )

    if pickup_window_start:
        try:
            start_dt = pd.to_datetime(pickup_window_start)
            df = df[pd.to_datetime(df["pickup_datetime"], errors="coerce") >= start_dt]
        except Exception:
            pass  # ignore bad date
    if pickup_window_end:
        try:
            end_dt = pd.to_datetime(pickup_window_end)
            df = df[pd.to_datetime(df["pickup_datetime"], errors="coerce") <= end_dt]
        except Exception:
            pass

    # Keep base for widening
    base_df = df.copy()

    # Lane filters
    def apply_lane_filters(data):
        res = data
        if origin:
            res = res[_match_city_state(res["origin"], origin)]
        if destination:
            res = res[_match_city_state(res["destination"], destination)]
        return res

    df = apply_lane_filters(df)

    # Widen search if empty → drop destination filter first, then origin
    if df.empty and destination:
        df = base_df.copy()
        if origin:
            df = df[_match_city_state(df["origin"], origin)]

    if df.empty and origin:
        df = base_df.copy()  # only equipment/time filters remain

    if df.empty:
        return []

    # Ranking: score by lane match strength (simple heuristic)
    def _score_row(row) -> int:
        score = 0
        if origin and _norm(origin) in _norm(str(row.get("origin", ""))):
            score += 1
        if destination:
            dest_norm = _norm(str(row.get("destination", "")))
            if _norm(destination) in dest_norm:
                score += 1
            else:
                ab = _state_abbr(destination or "")
                if ab and dest_norm.endswith(f", {ab}"):
                    score += 1
        return score

    try:
        df = df.copy()
        df["__score"] = df.apply(_score_row, axis=1)
    except Exception:
        # If scoring fails for any reason, just keep rows as-is
        df["__score"] = 0

    # Prefer closer pickup to requested start if provided
    if pickup_window_start:
        try:
            start_dt = pd.to_datetime(pickup_window_start)
            df["__time_delta"] = (
                pd.to_datetime(df["pickup_datetime"], errors="coerce") - start_dt
            ).abs()
            df = df.sort_values(by=["__score", "__time_delta"], ascending=[False, True])
        except Exception:
            df = df.sort_values(by="__score", ascending=False)
    else:
        df = df.sort_values(by="__score", ascending=False)

    # Limit + clean
    cols = [c for c in df.columns if not c.startswith("__")]
    try:
        out = df.head(max(1, int(limit)))[cols]
    except Exception:
        out = df[cols].head(3)

    # Convert to plain dicts (ensure JSON-serializable)
    records: List[Dict[str, Any]] = []
    for r in out.to_dict(orient="records"):
        r["loadboard_rate"] = _safe_float(r.get("loadboard_rate"))
        r["miles"] = _safe_float(r.get("miles"))
        r["num_of_pieces"] = _safe_int(r.get("num_of_pieces"))
        records.append(r)

    return records

def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None or x == "" or str(x).lower() == "nan":
            return None
        return float(x)
    except Exception:
        return None

def _safe_int(x: Any) -> Optional[int]:
    try:
        if x is None or x == "" or str(x).lower() == "nan":
            return None
        return int(x)
    except Exception:
        return None
