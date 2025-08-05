
from typing import List, Dict, Optional
import pandas as pd
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "loads.csv"

def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def search_loads(
    equipment_type: str,
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    pickup_window_start: Optional[str] = None,
    pickup_window_end: Optional[str] = None,
    limit: int = 3,
) -> List[Dict]:
    df = pd.read_csv(CSV_PATH)
    # Basic filters
    if equipment_type:
        df = df[df["equipment_type"].str.lower() == equipment_type.lower()]
    if origin:
        o = _norm(origin)
        df = df[df["origin"].str.lower().str.contains(o)]
    if destination:
        d = _norm(destination)
        df = df[df["destination"].str.lower().str.contains(d)]
    # TODO: filter on pickup window (ISO8601) in later step

    # Simple ranking: prefer rows that match both origin and destination text
    def score_row(row):
        s = 0
        if origin and _norm(row["origin"]).find(_norm(origin)) >= 0:
            s += 1
        if destination and _norm(row["destination"]).find(_norm(destination)) >= 0:
            s += 1
        return s

    if not df.empty:
        df = df.copy()
        df["__score"] = df.apply(score_row, axis=1)
        df = df.sort_values(by=["__score"], ascending=False)

    # Limit to top N
    results = df.head(limit).drop(columns=[c for c in df.columns if c.startswith("__")]).to_dict(orient="records")
    return results
