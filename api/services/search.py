from __future__ import annotations
from typing import List, Dict, Optional
from pathlib import Path
import pandas as pd
import re
from datetime import datetime

CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "loads.csv"

# --- helpers -----------------------------------------------------------

def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()

# state map:  "texas" -> "tx", "tx" -> "tx"
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
# add the abbreviations themselves
_STATES.update({abbr: abbr for abbr in _STATES.values()})

def _state_abbr(text: str) -> Optional[str]:
    """Return 2-letter state abbr if text looks like a state name/abbr."""
    t = _norm(text)
    return _STATES.get(t)

def _match_city_state(series: pd.Series, query: str) -> pd.Series:
    """Return boolean mask where destination/origin contains query city
    OR ends with ', XX' matching state abbreviation."""
    q = _norm(query)
    abbr = _state_abbr(q)
    if abbr:  # user gave a state
        state_regex = re.compile(rf",\s*{abbr}$", flags=re.I)
        return series.str.lower().str.contains(q) | series.str.contains(state_regex)
    # city substring match
    return series.str.lower().str.contains(q)

# --- main search -------------------------------------------------------

def search_loads(
    equipment_type: str,
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    pickup_window_start: Optional[str] = None,
    pickup_window_end: Optional[str] = None,
    limit: int = 3,
) -> List[Dict]:
    """
    Return up to `limit` loads ranked by lane relevance.
    Widens filters progressively if no rows remain.
    """
    df = pd.read_csv(CSV_PATH)

    # required equipment filter
    df = df[df["equipment_type"].str.lower() == equipment_type.lower()]

    # --- time window filter -------------------------------------------
    if pickup_window_start:
        try:
            start_dt = pd.to_datetime(pickup_window_start)
            df = df[pd.to_datetime(df["pickup_datetime"]) >= start_dt]
        except ValueError:
            pass  # ignore bad date
    if pickup_window_end:
        try:
            end_dt = pd.to_datetime(pickup_window_end)
            df = df[pd.to_datetime(df["pickup_datetime"]) <= end_dt]
        except ValueError:
            pass

    # keep original df for fallback
    base_df = df.copy()

    # --- lane filters --------------------------------------------------
    def apply_lane_filters(data: pd.DataFrame) -> pd.DataFrame:
        if origin:
            data = data[_match_city_state(data["origin"], origin)]
        if destination:
            data = data[_match_city_state(data["destination"], destination)]
        return data

    df = apply_lane_filters(df)

    # widen search if empty  → drop destination filter, then origin
    if df.empty and destination:
        df = apply_lane_filters(base_df.drop(columns=[]).assign(destination=None))
    if df.empty and origin:
        df = base_df  # just equipment/time match

    if df.empty:
        return []

    # --- ranking -------------------------------------------------------
    def score_row(row):
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
    df["__score"] = df.apply(score_row, axis=1)
    df = df.sort_values(by="__score", ascending=False)

    # limit + clean columns
    cols = [c for c in df.columns if not c.startswith("__")]
    return df.head(limit)[cols].to_dict(orient="records")
