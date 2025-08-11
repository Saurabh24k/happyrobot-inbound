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
    anchor_high: Optional[Any] = None,     # highest $ we’ve anchored earlier (e.g., round-1 counter)
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

    Contract:
    - Inputs: loadboard_rate, carrier_offer, round_num, prev_counter (r>=2), anchor_high (optional)
    - Output: { decision: 'accept' | 'counter' | 'counter-final' | 'reject',
                counter_rate: float, floor: float, max_rounds: int,
                (optional debug fields when debug=True) }

    Core rules:
    1) Anchor integrity: If they meet/beat our last counter (or return to an earlier anchor),
       accept instead of dropping.
    2) Monotone counters: Our counters never increase across rounds.
    3) Never counter above their current ask.
    4) Final round prefers closing near prev/anchor; only falls to floor if no viable anchor/target.
    """

    # ---------- helpers ----------
    def _to_f(x: Any) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    def _snap(x: float, t: float) -> float:
        return round(round(x / t) * t, 2)

    # ---------- parse & guards ----------
    lb = max(0.0, _to_f(loadboard_rate))
    offer = max(0.0, _to_f(carrier_offer))
    r = int(_to_f(round_num)) if str(round_num).strip() else 1
    r = max(1, min(r, max_rounds))

    prev = None if prev_counter is None else max(0.0, _to_f(prev_counter))
    anc_high_val = None if anchor_high is None else max(0.0, _to_f(anchor_high))
    mi = _to_f(miles)

    if lb <= 0:
        out = {"decision": "reject", "counter_rate": 0.0, "floor": 0.0, "max_rounds": max_rounds}
        if debug: out.update({"reason": "no_board_rate", "round_num": r})
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
    # Concession schedule (feel free to tweak)
    progress = {1: 0.33, 2: 0.60, 3: 0.80}
    prog = progress.get(r, 0.80 if r >= max_rounds else 0.60)
    base_target = min(max(ceil - gap * prog, floor), ceil)

    # Blend toward their ask on early rounds
    offer_clamped = min(max(offer, floor), ceil)
    blend_w = 1.0 if r >= max_rounds else (0.75 if r == 2 else 0.65)
    target = blend_w * base_target + (1.0 - blend_w) * offer_clamped

    # If we already have a previous counter, we must not increase our counter
    if prev is not None:
        target = min(target, prev)

    # Snap & clamp
    target = _snap(min(max(target, floor), ceil), tick)

    # ---------- fast accepts ----------
    # 1) Return to earlier anchor we set? (e.g., we said 1760 in r1, later we went to 1720; if they come back to ~1760, accept.)
    if anc_high_val is not None and offer <= ceil and accept_return_to_anchor:
        if abs(offer - anc_high_val) <= tol_eff:
            out = {"decision": "accept", "counter_rate": _snap(offer, tick), "floor": floor, "max_rounds": max_rounds}
            if debug: out.update({"reason": "met_earlier_anchor", "anchor_high": anc_high_val, "round_num": r})
            return out

    # 2) Meeting/near our last counter? Accept at the better (lower) of {offer, prev}
    if prev is not None:
        if offer <= prev + (tol_eff if accept_close_to_prev else 0.0):
            out = {
                "decision": "accept",
                "counter_rate": _snap(min(offer, prev), tick),
                "floor": floor,
                "max_rounds": max_rounds,
            }
            if debug:
                out.update({
                    "reason": "met_prev_anchor",
                    "prev_counter": prev,
                    "target": target, "round_num": r
                })
            return out

    # 3) If they’re under our floor and policy allows, take it (we pay less)
    if offer < floor and accept_below_floor:
        return {"decision": "accept", "counter_rate": _snap(offer, tick), "floor": floor, "max_rounds": max_rounds}

    # 4) If their ask is within target + tol, take it
    if offer <= target + tol_eff:
        return {"decision": "accept", "counter_rate": _snap(offer, tick), "floor": floor, "max_rounds": max_rounds}

    # ---------- regression guard (they came ABOVE our last counter) ----------
    # Example: we countered 1290, they now ask 1320. Do NOT drop to floor; hold at our last counter.
    if prev is not None and offer > prev + (tol_eff if accept_close_to_prev else 0.0):
        hold = _snap(prev, tick)
        if r >= max_rounds:
            return {"decision": "counter-final", "counter_rate": hold, "floor": floor, "max_rounds": max_rounds}
        else:
            return {"decision": "counter", "counter_rate": hold, "floor": floor, "max_rounds": max_rounds}

    # ---------- normal counter path ----------
    # Never counter above their current ask.
    counter = min(target, offer)
    # Keep non-increasing vs prev (if any)
    if prev is not None:
        counter = min(counter, prev)
    counter = _snap(max(counter, floor), tick)

    if r >= max_rounds:
        # Final round: pick the strongest credible number <= ask, preferring anchors > floor.
        candidates = [counter, floor]
        if prev is not None: candidates.append(min(prev, offer))
        if anc_high_val is not None: candidates.append(min(anc_high_val, offer))
        cf = max(_snap(max(candidates), tick), _snap(floor, tick))  # prefer higher credible (still ≤ ask), but ≥ floor
        # If the credible “best” is actually the ask (rare with payer logic), accept.
        if abs(cf - offer) <= 0.01:
            return {"decision": "accept", "counter_rate": _snap(offer, tick), "floor": floor, "max_rounds": max_rounds}
        return {"decision": "counter-final", "counter_rate": cf, "floor": floor, "max_rounds": max_rounds}

    return {"decision": "counter", "counter_rate": counter, "floor": floor, "max_rounds": max_rounds}
