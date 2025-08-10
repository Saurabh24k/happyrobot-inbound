# negotiate.py
from typing import Any, Dict, Optional
import math

class NegotiationError(ValueError):
    """Raised when required inputs are missing/invalid."""

def _to_float(x: Any, name: str) -> float:
    try:
        f = float(x)
    except Exception as e:
        raise NegotiationError(f"Invalid {name}: {x!r}") from e
    if math.isnan(f) or math.isinf(f):
        raise NegotiationError(f"Invalid {name}: {x!r}")
    return f

def _round_down_to_tick(x: float, tick: float) -> float:
    if tick <= 0:
        return round(x, 2)
    return round(math.floor(x / tick) * tick, 2)

def evaluate_offer(
    loadboard_rate: Any,
    carrier_offer: Any,
    round_num: Any,
    *,
    floor_pct: float = 0.90,        # aim-for minimum as % of ceiling/board
    max_rounds: int = 3,
    tol: float = 15.0,              # accept if within $tol of target
    tick: float = 5.0,              # counters rounded DOWN to nearest tick
    ceiling: Optional[float] = None, # max we will pay (defaults to board)
    prev_counter: Optional[float] = None,  # ensure monotone concessions if provided
) -> Dict[str, Any]:
    """
    Downward negotiation policy for a freight brokerage (we pay the carrier).

    Semantics
    - ceiling: max we'll pay (defaults to loadboard_rate).
    - floor:   min we aim to pay (ceiling * floor_pct).
    - Concede monotonically toward the floor across rounds.
    - Accept if the ask <= target + tol and <= ceiling. (We also accept BELOW floor.)
    - On the final round, return `counter-final` at floor if not accepting.
    - Counters are rounded DOWN to `tick` and never increase across rounds.
    """
    # ---- Parse & validate ----------------------------------------------------
    lb = _to_float(loadboard_rate, "loadboard_rate")
    offer = _to_float(carrier_offer, "carrier_offer")
    try:
        r = int(float(round_num))
    except Exception as e:
        raise NegotiationError(f"Invalid round_num: {round_num!r}") from e
    if max_rounds < 1:
        max_rounds = 1
    r = max(1, min(r, max_rounds))

    ceil = lb if ceiling is None else _to_float(ceiling, "ceiling")
    if ceil <= 0:
        raise NegotiationError(f"Invalid ceiling derived from loadboard_rate: {ceil}")
    floor = round(ceil * float(floor_pct), 2)
    if floor > ceil:
        floor = ceil

    # ---- Concession schedule (monotone toward floor) ------------------------
    progress = {1: 0.35, 2: 0.60, 3: 0.80}  # portion of (ceil-floor) conceded by round
    prog = progress.get(r, 0.80 if r >= max_rounds else 0.60)

    gap = ceil - floor
    base_target = ceil - gap * prog
    base_target = min(max(base_target, floor), ceil)

    # Lightly blend toward the offer before final round (keeps counters realistic)
    offer_clamped = min(max(offer, floor), ceil)
    blend_w = 0.0 if r >= max_rounds else (0.25 if r == 2 else 0.35)
    target_unrounded = (1 - blend_w) * base_target + blend_w * offer_clamped

    # Round DOWN toward our objective and clamp
    target = _round_down_to_tick(min(max(target_unrounded, floor), ceil), tick)

    # Never go up vs. a previous counter we may have issued
    if prev_counter is not None:
        try:
            target = min(target, float(prev_counter))
        except Exception:
            pass

    # ---- Acceptance rule (downward logic) -----------------------------------
    # Accept if the ask is close enough to our target and under ceiling.
    # NOTE: We *do* accept if the ask is below floor (that’s better for us).
    if offer <= ceil and offer <= target + tol:
        return {
            "decision": "accept",
            "counter_rate": round(offer, 2),
            "floor": round(floor, 2),
            "max_rounds": max_rounds,
        }

    # ---- Final round firmness -----------------------------------------------
    if r >= max_rounds:
        floor_final = _round_down_to_tick(floor, tick)
        if offer > floor_final + tol:
            # Last take-it-or-leave-it at our floor.
            return {
                "decision": "counter-final",
                "counter_rate": floor_final,
                "floor": round(floor, 2),
                "max_rounds": max_rounds,
            }
        # Ask is near/below our floor ⇒ accept (at their number or our floor if lower)
        return {
            "decision": "accept",
            "counter_rate": round(min(offer, floor_final), 2),
            "floor": round(floor, 2),
            "max_rounds": max_rounds,
        }

    # ---- Normal counter ------------------------------------------------------
    counter = _round_down_to_tick(target, tick)
    counter = min(max(counter, floor), ceil)
    if prev_counter is not None:
        try:
            counter = min(counter, float(prev_counter))
        except Exception:
            pass

    return {
        "decision": "counter",
        "counter_rate": round(counter, 2),
        "floor": round(floor, 2),
        "max_rounds": max_rounds,
    }
