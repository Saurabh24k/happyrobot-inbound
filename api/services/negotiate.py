from __future__ import annotations
from typing import Dict, Any, Optional

def evaluate_offer(
    loadboard_rate: Any,
    carrier_offer: Any,
    round_num: Any,
    *,
    # Policy knobs
    floor_pct: float = 0.90,          # minimum we'll pay as % of board (floor)
    max_rounds: int = 3,
    tol: float = 15.0,                # base accept tolerance vs target/anchors
    tick: float = 5.0,                # snap all counters to $tick
    ceiling: Optional[float] = None,  # max we'll pay (defaults to board)
    prev_counter: Optional[Any] = None,  # our last counter (pass this on r>=2!)
    # Optional extras
    miles: Optional[Any] = None,          # lane miles (for dynamic tolerance)
    accept_close_to_prev: bool = False,   # if True, accept when offer is within tol of prev
    dynamic_tol_by_miles: bool = True,    # bump tol on longer lanes
    debug: bool = False,                  # include extra fields in output
    **_
) -> Dict:
    """
    Freight-broker negotiation (we pay the carrier → lower is better for us).

    Core policy
    -----------
    • Bounds:
        ceiling = max we'll pay (default: board)
        floor   = min we'll pay (board * floor_pct)
      We never counter outside [floor, ceiling].
    • Concessions:
        move from ceiling → floor over rounds (1:35%, 2:60%, 3+:80% of gap).
    • Guardrails (anchor integrity):
        A) If the carrier meets/exceeds OUR LAST COUNTER:
           - If `accept_close_to_prev` is False → require offer >= prev_counter.
           - If `accept_close_to_prev` is True  → allow offer >= prev_counter - tol_eff.
           In either case: ACCEPT at the better (lower) of {offer, prev_counter}. Do NOT drop.
        B) Never raise our price above our last counter.
        C) Do not “slide downward” just because the carrier goes up.
    • Final round:
        prefer closing at prev_counter (if met/close per above), else `counter-final` at floor.

    Returns
    -------
    Minimal:
      { "decision": "accept"|"counter"|"counter-final"|"reject",
        "counter_rate": float, "floor": float, "max_rounds": int }

    If debug=True, also returns fields like:
      "target", "ceiling", "round_num", "prev_counter", "offer_clamped", "reason"
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
    mi = _to_f(miles)

    if lb <= 0:
        out = {"decision": "reject", "counter_rate": 0.0, "floor": 0.0, "max_rounds": max_rounds}
        if debug:
            out.update({"reason": "no_board_rate", "round_num": r})
        return out

    ceil = lb if ceiling is None else float(ceiling)
    floor = round(lb * float(floor_pct), 2)
    if floor > ceil:
        floor = ceil  # never let floor exceed ceiling

    # --- tolerance (optionally dynamic by miles) --------------------
    tol_eff = tol
    if dynamic_tol_by_miles and mi > 0:
        # gentle slope: +$10 for 150–400mi; +$20 for >400mi
        if mi > 150:
            tol_eff += 10.0
        if mi > 400:
            tol_eff += 10.0

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

    # --- anchor integrity: hold the line ---------------------------
    # If they moved toward/above our last counter, don't go lower than prev.
    if prev is not None:
        # Accept window around prev (strict or tolerant)
        meets_prev = (offer >= prev) if not accept_close_to_prev else (offer >= prev - tol_eff)

        if meets_prev and (floor <= offer <= ceil):
            # Early accept at the better (lower) of the two
            out = {
                "decision": "accept",
                "counter_rate": _snap(min(offer, prev), tick),
                "floor": floor,
                "max_rounds": max_rounds,
            }
            if debug:
                out.update({
                    "target": _snap(min(max(target, floor), ceil), tick),
                    "ceiling": ceil, "round_num": r,
                    "prev_counter": prev, "offer_clamped": offer_clamped,
                    "reason": "met_prev_anchor"
                })
            return out

        # Otherwise, force target not to drop below our anchor
        target = max(target, prev)

        # and never raise above our last counter either
        target = min(target, prev)

    # Round & clamp target
    target = _snap(min(max(target, floor), ceil), tick)

    # --- general accept vs target ----------------------------------
    if floor <= offer <= ceil and offer <= target + tol_eff:
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

        # Prefer to close at prev if they met/are close to it
        if prev is not None:
            meets_prev = (offer >= prev) if not accept_close_to_prev else (offer >= prev - tol_eff)
            if meets_prev and floor <= prev <= ceil:
                out = {
                    "decision": "accept",
                    "counter_rate": _snap(min(offer, prev), tick),
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

        # Otherwise one last take-it-or-leave-it at floor
        if offer > floor_r + tol_eff:
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
        if floor_r <= offer <= floor_r + tol_eff:
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

        # Otherwise reject (way off / not moving)
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
