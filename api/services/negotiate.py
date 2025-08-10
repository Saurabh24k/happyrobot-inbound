# negotiate.py
from typing import Dict, Any

def evaluate_offer(
    loadboard_rate: Any,
    carrier_offer: Any,
    round_num: Any,
    *,
    floor_pct: float = 0.90,   # lowest we'll pay as a % of board
    max_rounds: int = 3,
    tol: float = 15.0,         # accept if within $tol of our target
    tick: float = 5.0,         # round counters to nearest $tick
    ceiling: float | None = None,
    **_
) -> Dict:
    """
    Downward negotiation policy for a freight brokerage.

    Key ideas
    ----------
    • We pay the carrier, so LOWER is better for us.
    • ceiling = maximum we will pay (defaults to loadboard_rate).
    • floor   = minimum we are willing to pay (loadboard_rate * floor_pct).
    • We concede toward the floor across rounds, never above ceiling.
    • Accept when the carrier is at/under our target (within tol) and within [floor, ceiling].
    • Final round returns `counter-final` at (rounded) floor.

    Returns
    -------
    {
      "decision": "accept" | "counter" | "counter-final" | "reject",
      "counter_rate": float,
      "floor": float,
      "max_rounds": int
    }
    """

    # --- helpers ----------------------------------------------------
    def _to_f(x: Any) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    def _round_tick(x: float, t: float) -> float:
        return round(round(x / t) * t, 2)

    # --- sanitize & bounds -----------------------------------------
    lb = max(0.0, _to_f(loadboard_rate))
    offer = max(0.0, _to_f(carrier_offer))
    r = int(_to_f(round_num)) if str(round_num).strip() else 1
    r = max(1, min(r, max_rounds))

    ceil = lb if ceiling is None else float(ceiling)
    floor = round(lb * float(floor_pct), 2)
    if floor > ceil:
        # Safety: never let floor exceed ceiling
        floor = ceil

    # --- build this round's target ---------------------------------
    # Concession schedule (cumulative toward the floor):
    # round 1 → 35% of gap, round 2 → 60%, round 3 → 80%
    progress = {1: 0.35, 2: 0.60, 3: 0.80}
    prog = progress.get(r, 0.80 if r >= max_rounds else 0.60)

    gap = ceil - floor
    base_target = ceil - gap * prog
    base_target = min(max(base_target, floor), ceil)

    # Slightly blend toward the offer on early rounds
    # (keeps counters realistic without giving away the floor too fast)
    offer_clamped = min(max(offer, floor), ceil)
    blend_weight = 1.0 if r >= max_rounds else (0.75 if r == 2 else 0.65)
    target = blend_weight * base_target + (1 - blend_weight) * offer_clamped

    # Round to neat tick and clamp to [floor, ceiling]
    target = _round_tick(min(max(target, floor), ceil), tick)

    # --- acceptance rule (downward logic) ---------------------------
    # Accept if the offer is at/under our target (within tol) and within bounds.
    if floor <= offer <= ceil and offer <= target + tol:
        return {
            "decision": "accept",
            "counter_rate": round(offer, 2),
            "floor": floor,
            "max_rounds": max_rounds,
        }

    # --- final round firmness --------------------------------------
    if r >= max_rounds:
        floor_rounded = _round_tick(floor, tick)

        # If their offer is still above what we can do, give a final take-it-or-leave-it.
        if offer > floor_rounded + tol:
            return {
                "decision": "counter-final",
                "counter_rate": floor_rounded,
                "floor": floor,
                "max_rounds": max_rounds,
            }

        # If they actually came in at/below floor (rare), accept (it’s better for us).
        if offer <= floor_rounded + tol and offer >= floor_rounded:
            return {
                "decision": "accept",
                "counter_rate": round(offer, 2),
                "floor": floor,
                "max_rounds": max_rounds,
            }

        # Otherwise reject (e.g., offer way above ceiling and not moving).
        return {
            "decision": "reject",
            "counter_rate": floor_rounded,
            "floor": floor,
            "max_rounds": max_rounds,
        }

    # --- normal counter --------------------------------------------
    counter = _round_tick(min(max(target, floor), ceil), tick)
    return {
        "decision": "counter",
        "counter_rate": counter,
        "floor": floor,
        "max_rounds": max_rounds,
    }
