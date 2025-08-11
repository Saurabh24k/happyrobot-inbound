from __future__ import annotations
from typing import Dict, Any, Optional

def evaluate_offer(
    loadboard_rate: Any,
    carrier_offer: Any,
    round_num: Any,
    *,
    # Policy knobs
    floor_pct: float = 0.90,          # min we’ll proactively pay (as % of board)
    max_rounds: int = 3,
    tol: float = 15.0,                # accept window vs target/anchors
    tick: float = 5.0,                # snap to $tick
    ceiling: Optional[float] = None,  # max we’ll pay (defaults to board)
    prev_counter: Optional[Any] = None,  # our last counter (pass this on r>=2!)
    # Optional extras
    miles: Optional[Any] = None,          # lane miles (for dynamic tol)
    accept_close_to_prev: bool = True,    # accept if offer ≤ prev + tol
    dynamic_tol_by_miles: bool = True,    # bump tol on longer lanes
    accept_below_floor: bool = True,      # if they offer less than floor, accept it
    debug: bool = False,
    **_
) -> Dict:
    """
    We are the payer (lower is better for us).

    Fixes:
    - Flip anchor check: meeting our last counter means offer <= prev.
    - Never counter above the carrier’s current offer.
    - Keep counters non-increasing across rounds; cap target by prev when present.
    """

    def _to_f(x: Any) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    def _snap(x: float, t: float) -> float:
        return round(round(x / t) * t, 2)

    lb = max(0.0, _to_f(loadboard_rate))
    offer = max(0.0, _to_f(carrier_offer))
    r = int(_to_f(round_num)) if str(round_num).strip() else 1
    r = max(1, min(r, max_rounds))
    prev = None if prev_counter is None else max(0.0, _to_f(prev_counter))
    mi = _to_f(miles)

    if lb <= 0:
        out = {"decision": "reject", "counter_rate": 0.0, "floor": 0.0, "max_rounds": max_rounds}
        if debug: out.update({"reason": "no_board_rate", "round_num": r})
        return out

    ceil = lb if ceiling is None else float(ceiling)
    floor = round(lb * float(floor_pct), 2)
    if floor > ceil:
        floor = ceil

    # tolerance, optionally bump by miles
    tol_eff = tol
    if dynamic_tol_by_miles and mi > 0:
        if mi > 150:
            tol_eff += 10.0
        if mi > 400:
            tol_eff += 10.0

    # concession target: move from ceiling -> floor over rounds
    progress = {1: 0.35, 2: 0.60, 3: 0.80}
    prog = progress.get(r, 0.80 if r >= max_rounds else 0.60)
    gap = ceil - floor
    base_target = min(max(ceil - gap * prog, floor), ceil)

    # blend a bit toward carrier’s number on early rounds
    offer_clamped = min(max(offer, floor), ceil)
    blend_w = 1.0 if r >= max_rounds else (0.75 if r == 2 else 0.65)
    target = blend_w * base_target + (1.0 - blend_w) * offer_clamped

    # Anchor integrity (we pay the carrier):
    # - If they meet/beat our last counter → accept at the better (lower) of {offer, prev}.
    # - Otherwise, NEVER raise above our last counter → cap target by prev.
    if prev is not None:
        meets_prev = (offer <= prev + (tol_eff if accept_close_to_prev else 0.0))
        if meets_prev and (offer <= ceil):
            out = {
                "decision": "accept",
                "counter_rate": _snap(min(offer, prev), tick),
                "floor": floor,
                "max_rounds": max_rounds,
            }
            if debug:
                out.update({
                    "target": _snap(min(max(target, floor), ceil), tick),
                    "ceiling": ceil, "round_num": r, "prev_counter": prev,
                    "offer_clamped": offer_clamped, "reason": "met_prev_anchor"
                })
            return out
        # don’t go higher than our last counter
        target = min(target, prev)

    # clamp & snap target
    target = _snap(min(max(target, floor), ceil), tick)

    # General accepts:
    # - If they offer below floor (and policy allows), take it.
    # - If offer is at/under target + tol, take it.
    if offer <= ceil:
        if accept_below_floor and offer < floor:
            return {"decision": "accept", "counter_rate": _snap(offer, tick), "floor": floor, "max_rounds": max_rounds}
        if offer <= target + tol_eff:
            return {"decision": "accept", "counter_rate": _snap(offer, tick), "floor": floor, "max_rounds": max_rounds}

    # Final round: prefer closing; never counter above their offer
    if r >= max_rounds:
        floor_r = _snap(floor, tick)
        if offer <= floor_r + tol_eff:
            return {"decision": "accept", "counter_rate": _snap(min(offer, floor_r), tick), "floor": floor, "max_rounds": max_rounds}
        if target >= offer:
            return {"decision": "accept", "counter_rate": _snap(offer, tick), "floor": floor, "max_rounds": max_rounds}
        return {"decision": "counter-final", "counter_rate": floor_r, "floor": floor, "max_rounds": max_rounds}

    # Normal counter — but NEVER above their current offer
    if target >= offer:
        return {"decision": "accept", "counter_rate": _snap(offer, tick), "floor": floor, "max_rounds": max_rounds}

    return {"decision": "counter", "counter_rate": target, "floor": floor, "max_rounds": max_rounds}
