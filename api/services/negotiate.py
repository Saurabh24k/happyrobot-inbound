from __future__ import annotations
from typing import Dict, Any, Optional

def evaluate_offer(
    loadboard_rate: Any,
    carrier_offer: Any,
    round_num: Any,
    *,
    # Policy knobs
    floor_pct: float = 0.90,           # min we’ll proactively pay (as % of board)
    max_rounds: int = 3,
    tol: float = 15.0,                 # accept window vs target/anchors
    tick: float = 5.0,                 # snap to $tick
    ceiling: Optional[float] = None,   # max we’ll pay (defaults to board)

    # Anchors / memory
    prev_counter: Optional[Any] = None,    # our last counter (pass this on r>=2!)
    anchor_high: Optional[Any] = None,     # our highest prior counter in this negotiation
    accept_return_to_anchor: bool = True,  # if they return to an earlier anchor, accept

    # Optional extras
    miles: Optional[Any] = None,           # lane miles (for dynamic tol)
    accept_close_to_prev: bool = True,     # accept if offer ≤ prev + tol
    dynamic_tol_by_miles: bool = True,     # bump tol on longer lanes
    accept_below_floor: bool = True,       # if they offer less than floor, accept it
    debug: bool = False,
    **_
) -> Dict:
    """
    We are the payer (lower is better for us).

    Improvements vs prior version:
    - Honors a returned earlier anchor (anchor_high) so we can close at a number we set before.
    - Softer final-round policy (prefers closing near prev/anchor instead of nuking to pure floor).
    - Still never counters above the carrier’s current offer.
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
    anc_high = None if anchor_high is None else max(0.0, _to_f(anchor_high))
    mi = _to_f(miles)

    if lb <= 0:
        out = {"decision": "reject", "counter_rate": 0.0, "floor": 0.0, "max_rounds": max_rounds}
        if debug:
            out.update({"reason": "no_board_rate", "round_num": r})
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

    # --- Anchor integrity & fast accepts -------------------------------------

    # If they return to an earlier higher anchor we set (e.g., round 1 counter),
    # accept to avoid "whiplash" behavior.
    if anc_high is not None and offer <= ceil:
        if abs(offer - anc_high) <= tol_eff and accept_return_to_anchor:
            out = {
                "decision": "accept",
                "counter_rate": _snap(min(offer, anc_high), tick),  # typically equals offer
                "floor": floor,
                "max_rounds": max_rounds,
            }
            if debug:
                out.update({
                    "reason": "met_earlier_anchor",
                    "anchor_high": anc_high,
                    "round_num": r,
                })
            return out

    # Meeting/near our last counter → accept at the better (lower) of {offer, prev}
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
        # Don’t go higher than our last counter
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

    # --- Final round: prefer closing; never counter above their offer ---------
    if r >= max_rounds:
        floor_r = _snap(floor, tick)

        # Close near previous anchor(s)
        if prev is not None and abs(offer - prev) <= tol_eff:
            return {"decision": "accept", "counter_rate": _snap(offer, tick), "floor": floor, "max_rounds": max_rounds}
        if anc_high is not None and abs(offer - anc_high) <= tol_eff:
            return {"decision": "accept", "counter_rate": _snap(offer, tick), "floor": floor, "max_rounds": max_rounds}

        # If offer close to floor, take it
        if offer <= floor_r + tol_eff:
            return {"decision": "accept", "counter_rate": _snap(min(offer, floor_r), tick), "floor": floor, "max_rounds": max_rounds}

        # If our target would be >= offer, accept at offer (never counter above offer)
        if target >= offer:
            return {"decision": "accept", "counter_rate": _snap(offer, tick), "floor": floor, "max_rounds": max_rounds}

        # Counter-final but don't nuke to pure floor if we’ve already anchored higher.
        # Choose the highest number we’ve anchored that is <= offer, but not below floor.
        cf = floor_r
        if prev is not None:
            cf = max(floor_r, min(prev, offer))
        if anc_high is not None:
            cf = max(cf, min(anc_high, offer))
        cf = _snap(cf, tick)
        return {"decision": "counter-final", "counter_rate": cf, "floor": floor, "max_rounds": max_rounds}

    # --- Normal counter — but NEVER above their current offer -----------------
    if target >= offer:
        return {"decision": "accept", "counter_rate": _snap(offer, tick), "floor": floor, "max_rounds": max_rounds}

    return {"decision": "counter", "counter_rate": target, "floor": floor, "max_rounds": max_rounds}
