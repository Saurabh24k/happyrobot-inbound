# negotiate.py
from typing import Dict, Any, Optional

def evaluate_offer(
    loadboard_rate: Any,
    carrier_offer: Any,
    round_num: Any,
    *,
    floor_pct: float = 0.90,   # lowest we'll pay as a % of board
    max_rounds: int = 3,
    tol: float = 15.0,         # accept if within $tol of our target
    tick: float = 5.0,         # round counters to nearest $tick
    ceiling: Optional[float] = None,
    prev_counter: Optional[Any] = None,
    **_
) -> Dict:
    """
    Downward negotiation policy for a freight brokerage.

    We (broker) pay the carrier, so LOWER is better for us.

    - ceiling = max we'll pay (defaults to board).
    - floor   = min we're willing to pay (board * floor_pct).
    - Concede toward the floor across rounds.
    - Accept when offer is at/under our target (within tol) and within [floor, ceiling].
    - Final round: 'counter-final' at floor (rounded).
    - Human-sane guard: if the carrier moves away from our last counter (i.e., offers >= prev_counter),
      HOLD our last counter (don't go even lower), and never increase our counter above prev_counter.
    """

    def _to_f(x: Any) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    def _round_tick(x: float, t: float) -> float:
        return round(round(x / t) * t, 2)

    # ---- sanitize ------------------------------------------------
    lb = _to_f(loadboard_rate)
    offer = max(0.0, _to_f(carrier_offer))
    r = int(_to_f(round_num)) if str(round_num).strip() else 1
    r = max(1, min(r, max_rounds))
    prev = None if prev_counter is None else max(0.0, _to_f(prev_counter))

    if lb <= 0:
        # Without a valid board, we can't compute a policy; reject safely.
        return {
            "decision": "reject",
            "counter_rate": 0.0,
            "floor": 0.0,
            "max_rounds": max_rounds,
        }

    ceil = lb if ceiling is None else float(ceiling)
    floor = round(lb * float(floor_pct), 2)
    if floor > ceil:
        floor = ceil

    # ---- concession schedule (cumulative toward floor) -----------
    progress = {1: 0.35, 2: 0.60, 3: 0.80}
    prog = progress.get(r, 0.80 if r >= max_rounds else 0.60)

    gap = ceil - floor
    base_target = ceil - gap * prog
    base_target = min(max(base_target, floor), ceil)

    # Blend a touch toward the offer on early rounds (but not too much)
    offer_clamped = min(max(offer, floor), ceil)
    blend_weight = 1.0 if r >= max_rounds else (0.75 if r == 2 else 0.65)
    target = blend_weight * base_target + (1 - blend_weight) * offer_clamped

    # Human-sane guardrails:
    # A) If carrier moved away from our last counter, HOLD the line.
    if prev is not None and offer >= prev:
        target = prev
    # B) Never raise our price vs last counter.
    if prev is not None:
        target = min(target, prev)

    # Round to tick & clamp
    target = _round_tick(min(max(target, floor), ceil), tick)

    # ---- accept rule --------------------------------------------
    if floor <= offer <= ceil and offer <= target + tol:
        return {
            "decision": "accept",
            "counter_rate": round(offer, 2),
            "floor": floor,
            "max_rounds": max_rounds,
        }

    # ---- final round --------------------------------------------
    if r >= max_rounds:
        floor_rounded = _round_tick(floor, tick)
        if offer > floor_rounded + tol:
            return {
                "decision": "counter-final",
                "counter_rate": floor_rounded,
                "floor": floor,
                "max_rounds": max_rounds,
            }
        if floor_rounded <= offer <= floor_rounded + tol:
            return {
                "decision": "accept",
                "counter_rate": round(offer, 2),
                "floor": floor,
                "max_rounds": max_rounds,
            }
        return {
            "decision": "reject",
            "counter_rate": floor_rounded,
            "floor": floor,
            "max_rounds": max_rounds,
        }

    # ---- normal counter -----------------------------------------
    counter = _round_tick(min(max(target, floor), ceil), tick)
    return {
        "decision": "counter",
        "counter_rate": counter,
        "floor": floor,
        "max_rounds": max_rounds,
    }
