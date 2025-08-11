from __future__ import annotations
from typing import Dict, Any, Optional


def evaluate_offer(
    loadboard_rate: Any,
    carrier_offer: Any,
    round_num: Any,
    *,
    # Policy knobs
    floor_pct: float = 0.90,           # minimum we’ll proactively pay (as % of board)
    max_rounds: int = 3,
    tol: float = 15.0,                 # acceptance window (USD) vs targets/anchors
    tick: float = 5.0,                 # snap to $tick
    ceiling: Optional[float] = None,   # cap (defaults to board)

    # Negotiation memory (pass these back in subsequent calls)
    prev_counter: Optional[Any] = None,    # our last counter (required r>=2)
    anchor_high: Optional[Any] = None,     # highest $ we’ve anchored earlier
    accept_return_to_anchor: bool = True,  # if they return to an earlier anchor, accept

    # Contextual extras
    miles: Optional[Any] = None,           # lane miles (for dynamic tolerance)
    accept_close_to_prev: bool = True,     # accept if offer ≤ prev + tol
    dynamic_tol_by_miles: bool = True,     # bump tol on longer lanes
    accept_below_floor: bool = True,       # if they ask below our floor, accept it
    debug: bool = False,
    **_
) -> Dict:
    """
    We are the payer — lower numbers are better for us.

    Returns:
      {
        decision: 'accept' | 'counter' | 'counter-final' | 'reject',
        counter_rate: float,
        floor: float,
        max_rounds: int,
        # helpers for your memory:
        next_round_num: int,
        next_prev_counter: float | None,
        next_anchor_high: float | None,
      }
    """

    # ---------- helpers ----------
    def _to_f(x: Any) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    def _snap(x: float, t: float) -> float:
        return round(round(x / t) * t, 2)

    def _nz(v: Optional[float]) -> float:
        return 0.0 if v is None else float(v)

    # ---------- parse & guards ----------
    lb = max(0.0, _to_f(loadboard_rate))
    offer = max(0.0, _to_f(carrier_offer))
    r = int(_to_f(round_num)) if str(round_num).strip() else 1
    r = max(1, min(r, max_rounds))

    prev = None if prev_counter in (None, "", "null") else max(0.0, _to_f(prev_counter))
    anc_high_val = None if anchor_high in (None, "", "null") else max(0.0, _to_f(anchor_high))
    mi = _to_f(miles)

    if lb <= 0:
        out = {
            "decision": "reject",
            "counter_rate": 0.0,
            "floor": 0.0,
            "max_rounds": max_rounds,
            "next_round_num": r,
            "next_prev_counter": prev,
            "next_anchor_high": anc_high_val,
        }
        if debug: out.update({"reason": "no_board_rate"})
        return out

    ceil = lb if ceiling is None else float(ceiling)
    floor = round(lb * float(floor_pct), 2)
    if floor > ceil:
        floor = ceil

    tol_eff = float(tol)
    if dynamic_tol_by_miles and mi > 0:
        if mi > 150: tol_eff += 10.0
        if mi > 400: tol_eff += 10.0

    # ---------- initial target curve (ceiling -> floor across rounds) ----------
    gap = ceil - floor
    progress = {1: 0.33, 2: 0.60, 3: 0.80}
    prog = progress.get(r, 0.80 if r >= max_rounds else 0.60)
    base_target = min(max(ceil - gap * prog, floor), ceil)

    # Blend toward their ask on early rounds
    offer_clamped = min(max(offer, floor), ceil)
    blend_w = 1.0 if r >= max_rounds else (0.75 if r == 2 else 0.65)
    target = blend_w * base_target + (1.0 - blend_w) * offer_clamped

    # If we already have a previous counter, do not increase our number
    if prev is not None:
        target = min(target, prev)

    target = _snap(min(max(target, floor), ceil), tick)

    # ---------- fast accepts ----------
    # Return to earlier anchor?
    if anc_high_val is not None and offer <= ceil and accept_return_to_anchor:
        if abs(offer - anc_high_val) <= tol_eff:
            rate = _snap(offer, tick)
            return {
                "decision": "accept",
                "counter_rate": rate,
                "floor": floor,
                "max_rounds": max_rounds,
                "next_round_num": r,                     # stop loop
                "next_prev_counter": prev,               # unchanged
                "next_anchor_high": max(_nz(anc_high_val), rate),
            }

    # Meet/near our last counter?
    if prev is not None and offer <= prev + (tol_eff if accept_close_to_prev else 0.0):
        rate = _snap(min(offer, prev), tick)
        return {
            "decision": "accept",
            "counter_rate": rate,
            "floor": floor,
            "max_rounds": max_rounds,
            "next_round_num": r,                     # stop loop
            "next_prev_counter": prev,
            "next_anchor_high": max(_nz(anc_high_val), rate) if anc_high_val is not None else rate,
        }

    # Below our floor (we pay less)? Take it.
    if offer < floor and accept_below_floor:
        rate = _snap(offer, tick)
        return {
            "decision": "accept",
            "counter_rate": rate,
            "floor": floor,
            "max_rounds": max_rounds,
            "next_round_num": r,
            "next_prev_counter": prev,
            "next_anchor_high": max(_nz(anc_high_val), rate) if anc_high_val is not None else rate,
        }

    # Close if within target + tol
    if offer <= target + tol_eff:
        rate = _snap(offer, tick)
        return {
            "decision": "accept",
            "counter_rate": rate,
            "floor": floor,
            "max_rounds": max_rounds,
            "next_round_num": r,
            "next_prev_counter": prev,
            "next_anchor_high": max(_nz(anc_high_val), rate) if anc_high_val is not None else rate,
        }

    # ---------- regression (they came ABOVE our last counter) ----------
    if prev is not None and offer > prev + (tol_eff if accept_close_to_prev else 0.0):
        hold = _snap(prev, tick)
        decision = "counter-final" if r >= max_rounds else "counter"
        return {
            "decision": decision,
            "counter_rate": hold,
            "floor": floor,
            "max_rounds": max_rounds,
            "next_round_num": min(r + 1, max_rounds) if decision == "counter" else r,
            "next_prev_counter": hold,
            "next_anchor_high": max(_nz(anc_high_val), hold) if anc_high_val is not None else hold,
        }

    # ---------- normal counter path ----------
    counter = min(target, offer)        # never above their ask
    if prev is not None:
        counter = min(counter, prev)    # never above our last counter
    counter = _snap(max(counter, floor), tick)

    if r >= max_rounds:
        # Final round: pick strongest credible number ≤ ask, preferring anchors over floor
        candidates = [counter, floor]
        if prev is not None: candidates.append(min(prev, offer))
        if anc_high_val is not None: candidates.append(min(anc_high_val, offer))
        cf = max(_snap(max(candidates), tick), _snap(floor, tick))
        if abs(cf - offer) <= 0.01:
            return {
                "decision": "accept",
                "counter_rate": _snap(offer, tick),
                "floor": floor,
                "max_rounds": max_rounds,
                "next_round_num": r,
                "next_prev_counter": prev,
                "next_anchor_high": max(_nz(anc_high_val), offer) if anc_high_val is not None else offer,
            }
        return {
            "decision": "counter-final",
            "counter_rate": cf,
            "floor": floor,
            "max_rounds": max_rounds,
            "next_round_num": r,
            "next_prev_counter": cf,
            "next_anchor_high": max(_nz(anc_high_val), cf) if anc_high_val is not None else cf,
        }

    return {
        "decision": "counter",
        "counter_rate": counter,
        "floor": floor,
        "max_rounds": max_rounds,
        "next_round_num": min(r + 1, max_rounds),
        "next_prev_counter": counter,
        "next_anchor_high": max(_nz(anc_high_val), counter) if anc_high_val is not None else counter,
    }
