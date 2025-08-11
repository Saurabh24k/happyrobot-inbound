# negotiate.py
from typing import Dict, Any, Optional

def evaluate_offer(
    loadboard_rate: Any,
    carrier_offer: Any,
    round_num: Any,
    *,
    floor_pct: float = 0.90,      # minimum we will pay as a % of board (our floor)
    max_rounds: int = 3,
    tol: float = 15.0,            # accept if within $tol of a target/anchor
    tick: float = 5.0,            # snap all counters to $tick
    ceiling: Optional[float] = None,  # max we'll pay (defaults to board)
    prev_counter: Optional[Any] = None,  # our last counter (pass this!)
    debug: bool = False,          # set True to return extra fields
    **_
) -> Dict:
    """
    Freight-broker negotiation (we pay the carrier → lower is better for us).

    Policy highlights
    -----------------
    • Bounds:  ceiling = max we will pay (default: loadboard_rate)
               floor   = min we will pay (board * floor_pct)
      We never counter outside [floor, ceiling].
    • Concessions: move from ceiling → floor over rounds.
    • Guardrails:
        - If the carrier meets/exceeds OUR LAST COUNTER (prev_counter), ACCEPT
          at the better (lower) of {offer, prev_counter}. Do NOT drop further.
        - Never raise our price above our last counter.
        - Do not “slide downward” (to floor) just because the carrier goes up.
    • Final round: respect prev_counter first; otherwise issue `counter-final`
      at the rounded floor.

    Returns
    -------
    Minimal:
      { "decision": "accept"|"counter"|"counter-final"|"reject",
        "counter_rate": float, "floor": float, "max_rounds": int }

    If debug=True, also returns:
      "target", "ceiling", "round_num", "prev_counter", "offer_clamped"
    """

    # --- helpers ----------------------------------------------------
    def _to_f(x: Any) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    def _snap(x: float, t: float) -> float:
        return round(round(x / t) * t, 2)

    # --- sanitize ---------------------------------------------------
    lb = max(0.0, _to_f(loadboard_rate))
    offer = max(0.0, _to_f(carrier_offer))
    r = int(_to_f(round_num)) if str(round_num).strip() else 1
    r = max(1, min(r, max_rounds))
    prev = None if prev_counter is None else max(0.0, _to_f(prev_counter))

    if lb <= 0:
        out = {
            "decision": "reject",
            "counter_rate": 0.0,
            "floor": 0.0,
            "max_rounds": max_rounds,
        }
        if debug:
            out.update({"reason": "no_board_rate", "round_num": r})
        return out

    ceil = lb if ceiling is None else float(ceiling)
    floor = round(lb * float(floor_pct), 2)
    if floor > ceil:
        floor = ceil  # never let floor exceed ceiling

    # --- concession target -----------------------------------------
    # cumulative progress toward the floor
    progress = {1: 0.35, 2: 0.60, 3: 0.80}
    prog = progress.get(r, 0.80 if r >= max_rounds else 0.60)

    gap = ceil - floor
    base_target = min(max(ceil - gap * prog, floor), ceil)

    # lightly blend toward their number on early rounds
    offer_clamped = min(max(offer, floor), ceil)
    blend_w = 1.0 if r >= max_rounds else (0.75 if r == 2 else 0.65)
    target = blend_w * base_target + (1.0 - blend_w) * offer_clamped

    # Guardrail A: if they meet/exceed our last counter, hold that line
    if prev is not None and offer >= prev - tol:
        target = prev
    # Guardrail B: never raise above our prior counter
    if prev is not None:
        target = min(target, prev)

    target = _snap(min(max(target, floor), ceil), tick)

    # --- early accept: they met/beaten our last counter -------------
    if prev is not None and floor <= offer <= ceil and offer >= prev - tol:
        out = {
            "decision": "accept",
            # Pay the better (lower) of their offer or our last counter
            "counter_rate": _snap(min(offer, prev), tick),
            "floor": floor,
            "max_rounds": max_rounds,
        }
        if debug:
            out.update({
                "target": target, "ceiling": ceil, "round_num": r,
                "prev_counter": prev, "offer_clamped": offer_clamped,
                "reason": "met_prev"
            })
        return out

    # --- general accept vs target ----------------------------------
    if floor <= offer <= ceil and offer <= target + tol:
        out = {
            "decision": "accept",
            "counter_rate": _snap(offer, tick),
            "floor": floor,
            "max_rounds": max_rounds,
        }
        if debug:
            out.update({
                "target": target, "ceiling": ceil, "round_num": r,
                "prev_counter": prev, "offer_clamped": offer_clamped,
                "reason": "within_target"
            })
        return out

    # --- final round behavior --------------------------------------
    if r >= max_rounds:
        floor_r = _snap(floor, tick)

        # If our previous counter exists and is feasible, close at prev
        if prev is not None and floor <= prev <= ceil and offer >= prev - tol:
            out = {
                "decision": "accept",
                "counter_rate": _snap(prev, tick),
                "floor": floor,
                "max_rounds": max_rounds,
            }
            if debug:
                out.update({
                    "target": target, "ceiling": ceil, "round_num": r,
                    "prev_counter": prev, "offer_clamped": offer_clamped,
                    "reason": "final_accept_prev"
                })
            return out

        # Otherwise, one last take-it-or-leave-it at floor
        if offer > floor_r + tol:
            out = {
                "decision": "counter-final",
                "counter_rate": floor_r,
                "floor": floor,
                "max_rounds": max_rounds,
            }
            if debug:
                out.update({
                    "target": target, "ceiling": ceil, "round_num": r,
                    "prev_counter": prev, "offer_clamped": offer_clamped,
                    "reason": "final_floor"
                })
            return out

        # If they’re basically at floor, accept
        if floor_r <= offer <= floor_r + tol:
            out = {
                "decision": "accept",
                "counter_rate": _snap(offer, tick),
                "floor": floor,
                "max_rounds": max_rounds,
            }
            if debug:
                out.update({
                    "target": target, "ceiling": ceil, "round_num": r,
                    "prev_counter": prev, "offer_clamped": offer_clamped,
                    "reason": "final_near_floor"
                })
            return out

        # Otherwise reject (uncooperative / off bounds)
        out = {
            "decision": "reject",
            "counter_rate": floor_r,
            "floor": floor,
            "max_rounds": max_rounds,
        }
        if debug:
            out.update({
                "target": target, "ceiling": ceil, "round_num": r,
                "prev_counter": prev, "offer_clamped": offer_clamped,
                "reason": "final_reject"
            })
        return out

    # --- normal counter --------------------------------------------
    out = {
        "decision": "counter",
        "counter_rate": target,
        "floor": floor,
        "max_rounds": max_rounds,
    }
    if debug:
        out.update({
            "target": target, "ceiling": ceil, "round_num": r,
            "prev_counter": prev, "offer_clamped": offer_clamped,
            "reason": "counter_normal"
        })
    return out
