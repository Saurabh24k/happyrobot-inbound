from __future__ import annotations
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import re

# Path to your loads CSV
CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "loads.csv"

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

def _match_city_state(series: pd.Series, query: str) -> pd.Series:
    """True where series contains city substring OR ends with ', XX' (state)."""
    q = _norm(query)
    abbr = _state_abbr(q)
    s_lower = series.str.lower()
    if abbr:  # user gave a state
        state_regex = re.compile(rf",\s*{abbr}$", flags=re.I)
        return s_lower.str.contains(q) | series.str.contains(state_regex)
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
        dt = du_parser.parse(raw, default=default_base, fuzzy=True)
    else:
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
    """
    # Load data
    df = pd.read_csv(CSV_PATH)

    # Minimal schema check (raises clear error early if CSV is wrong)
    required_cols = {
        "load_id", "equipment_type", "origin", "destination", "pickup_datetime",
        "delivery_datetime", "miles", "weight", "dimensions", "notes", "loadboard_rate",
        "commodity_type", "num_of_pieces"
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"loads.csv missing required columns: {sorted(missing)}")

    # Equipment filter (required)
    df = df[df["equipment_type"].str.lower() == (equipment_type or "").strip().lower()]

    # Time window: normalize to next-future when year missing
    if pickup_window_start or pickup_window_end:
        pickup_window_start, pickup_window_end = _normalize_future_window(
            pickup_window_start, pickup_window_end
        )

    if pickup_window_start:
        try:
            start_dt = pd.to_datetime(pickup_window_start)
            df = df[pd.to_datetime(df["pickup_datetime"]) >= start_dt]
        except Exception:
            pass  # ignore bad date
    if pickup_window_end:
        try:
            end_dt = pd.to_datetime(pickup_window_end)
            df = df[pd.to_datetime(df["pickup_datetime"]) <= end_dt]
        except Exception:
            pass

    # Keep base for widening
    base_df = df.copy()

    # Lane filters
    def apply_lane_filters(data: pd.DataFrame) -> pd.DataFrame:
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
    def _score_row(row: pd.Series) -> int:
        score = 0
        if origin and _norm(origin) in _norm(row["origin"]):
            score += 1
        if destination:
            dest_norm = _norm(row["destination"])
            if _norm(destination) in dest_norm:
                score += 1
            elif _state_abbr(destination or "") and dest_norm.endswith(f", {_state_abbr(destination)}"):
                score += 1
        return score

    df = df.copy()
    df["__score"] = df.apply(_score_row, axis=1)

    # Prefer closer pickup to requested start if provided
    if pickup_window_start:
        start_dt = pd.to_datetime(pickup_window_start)
        df["__time_delta"] = (pd.to_datetime(df["pickup_datetime"]) - start_dt).abs()
        df = df.sort_values(by=["__score", "__time_delta"], ascending=[False, True])
    else:
        df = df.sort_values(by="__score", ascending=False)

    # Limit + clean
    cols = [c for c in df.columns if not c.startswith("__")]
    return df.head(max(1, int(limit)))[cols].to_dict(orient="records")
