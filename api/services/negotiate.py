from __future__ import annotations
from typing import Dict, Any, Optional


def evaluate_offer(
    loadboard_rate: Any,
    carrier_offer: Any,
    round_num: Any,
    *,
    # Policy knobs
    floor_pct: float = 0.90,            # min pay (as % of board)
    max_rounds: int = 3,
    tol: float = 15.0,                  # accept window vs targets/anchors (USD)
    tick: float = 5.0,                  # snap to $tick
    ceiling: Optional[float] = None,    # max we’ll pay (defaults to board)

    # Negotiation memory
    prev_counter: Optional[Any] = None,     # our last counter (required r>=2)
    anchor_high: Optional[Any] = None,      # highest $

    # Contextual extras
    miles: Optional[Any] = None,            # lane miles (dynamic tolerance)
    accept_close_to_prev: bool = True,      # accept if offer ≤ prev + tol
    dynamic_tol_by_miles: bool = True,      # bump tol on longer lanes

    # Below-floor handling
    accept_below_floor: bool = True,        # we can accept below our floor (payer wins)
    low_confirm_ratio: float = 0.85,        # R1 guard: if offer < floor*ratio → confirm first
    min_ratio_vs_board: float = 0.50,       # R1 guard: if offer < board*ratio → confirm first

    debug: bool = False,
    **_
) -> Dict:
    """
    We are the payer — lower is better.

    Possible decisions:
      - "accept"        : take their number (counter_rate)
      - "counter"       : not final; propose counter_rate
      - "counter-final" : last counter this negotiation
      - "confirm-low"   : (new) R1 guard — offer looks too low; ask the caller to confirm verbally
      - "reject"        : cannot proceed (e.g., no board rate)

    Output also includes helper fields to keep your graph state in sync:
      counter_rate: float
      floor: float
      max_rounds: int
      next_round_num: int
      next_prev_counter: float | None
      next_anchor_high: float | None
    """

    # ---------- helpers ----------
    def _to_f(x: Any) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    def _as_opt_anchor(x: Any) -> Optional[float]:
        """Treat '', 'null', 'None', 0 → as missing for anchor/prev_counter."""
        if x is None:
            return None
        if isinstance(x, str):
            s = x.strip().lower()
            if s in ("", "null", "none", "nan"):
                return None
            try:
                v = float(s)
            except Exception:
                return None
        else:
            try:
                v = float(x)
            except Exception:
                return None
        return None if v <= 0 else v

    def _snap(x: float, t: float) -> float:
        return round(round(x / t) * t, 2)

    def _mk_out(decision: str, price: float, floor_v: float, r_now: int,
                prev_v: Optional[float], anc_v: Optional[float], reason: Optional[str] = None) -> Dict:
        """Build response + helper fields so the agent can persist state."""
        next_prev = prev_v
        next_anc = anc_v
        if decision in ("counter", "counter-final"):
            # counters: non-increasing across rounds
            next_prev = price if prev_v is None else min(prev_v, price)
            # highest anchor ever set
            next_anc = price if (anc_v is None or price > anc_v) else anc_v
        elif decision == "accept":
            next_anc = price if (anc_v is None or price > anc_v) else anc_v

        out = {
            "decision": decision,
            "counter_rate": price,
            "floor": floor_v,
            "max_rounds": max_rounds,
            "next_round_num": min(r_now + 1, max_rounds),
            "next_prev_counter": next_prev,
            "next_anchor_high": next_anc,
        }
        if debug:
            out.update({"reason": reason})
        return out

    # ---------- parse ----------
    lb = max(0.0, _to_f(loadboard_rate))
    offer = max(0.0, _to_f(carrier_offer))

    try:
        r_in = int(_to_f(round_num)) if str(round_num).strip() else 1
    except Exception:
        r_in = 1

    prev = _as_opt_anchor(prev_counter)
    anc_high_val = _as_opt_anchor(anchor_high)

    if lb <= 0:
        out = {"decision": "reject", "counter_rate": 0.0, "floor": 0.0, "max_rounds": max_rounds}
        if debug:
            out.update({"reason": "no_board_rate"})
        return out

    ceil = lb if ceiling is None else float(ceiling)
    floor = round(lb * float(floor_pct), 2)
    if floor > ceil:
        floor = ceil

    # If graph resets round to 1
    r = r_in
    if r <= 1 and (prev is not None or anc_high_val is not None):
        r = 2
    r = max(1, min(r, max_rounds))
    r1 = (r == 1)

    # Effective tolerance
    tol_eff = float(tol)
    mi = _to_f(miles)
    if dynamic_tol_by_miles and mi > 0:
        if mi > 150:
            tol_eff += 10.0
        if mi > 400:
            tol_eff += 10.0

    # ---------- target curve (ceiling -> floor across rounds) ----------
    gap = ceil - floor
    progress = {1: 0.33, 2: 0.60, 3: 0.80}
    prog = progress.get(r, 0.80 if r >= max_rounds else 0.60)
    base_target = min(max(ceil - gap * prog, floor), ceil)

    # Blend toward their ask on early rounds
    offer_clamped = min(max(offer, floor), ceil)
    blend_w = 1.0 if r >= max_rounds else (0.75 if r == 2 else 0.65)
    target = blend_w * base_target + (1.0 - blend_w) * offer_clamped

    if prev is not None:
        target = min(target, prev)

    # Clamp & snap
    target = _snap(min(max(target, floor), ceil), tick)
    floor_r = _snap(floor, tick)


    if r1 and offer == 0.0:
        return _mk_out("counter", target, floor, r, prev, anc_high_val, "probe_target_r1")

    # ---------- R1 lowball guard ----------
    if offer > 0 and r1:
        too_low_vs_floor = offer < (floor * float(low_confirm_ratio))
        too_low_vs_board = offer < (lb * float(min_ratio_vs_board))
        if too_low_vs_floor or too_low_vs_board:
            return _mk_out("confirm-low", _snap(offer, tick), floor, r, prev, anc_high_val, "r1_lowball_confirm")

    # ---------- fast accepts ----------
    if anc_high_val is not None and offer <= ceil:
        if abs(offer - anc_high_val) <= tol_eff:
            return _mk_out("accept", _snap(offer, tick), floor, r, prev, anc_high_val, "met_earlier_anchor")

    if prev is not None:
        if offer <= prev + (tol_eff if accept_close_to_prev else 0.0):
            return _mk_out("accept", _snap(min(offer, prev), tick), floor, r, prev, anc_high_val, "met_prev_anchor")

    if offer < floor and accept_below_floor:
        if (not r1) or (floor - offer) <= tol_eff:
            return _mk_out("accept", _snap(offer, tick), floor, r, prev, anc_high_val, "below_floor_accept")

    if offer <= target + tol_eff:
        return _mk_out("accept", _snap(offer, tick), floor, r, prev, anc_high_val, "within_target_tol")

    # ---------- regression guard ----------
    if prev is not None and offer > prev + (tol_eff if accept_close_to_prev else 0.0):
        hold = _snap(prev, tick)
        if r >= max_rounds:
            return _mk_out("counter-final", hold, floor, r, prev, anc_high_val, "regression_hold_final")
        else:
            return _mk_out("counter", hold, floor, r, prev, anc_high_val, "regression_hold")

    # ---------- normal counter path ----------
    counter = target
    if prev is not None:
        counter = min(counter, prev)

    counter = _snap(counter, tick)

    if counter < floor_r:
        if floor_r >= offer:
            return _mk_out("accept", _snap(offer, tick), floor, r, prev, anc_high_val, "avoid_counter_above_ask")
        counter = floor_r

    # Final safety: if counter would end up ≥ their ask, accept their ask.
    if counter >= offer:
        return _mk_out("accept", _snap(offer, tick), floor, r, prev, anc_high_val, "accept_instead_of_counter_above_ask")

    if r >= max_rounds:
        candidates = [counter, floor_r]
        if prev is not None:
            candidates.append(min(_snap(prev, tick), _snap(offer, tick)))
        if anc_high_val is not None:
            candidates.append(min(_snap(anc_high_val, tick), _snap(offer, tick)))
        cf = max(candidates)  # best credible that’s still ≤ ask
        if abs(cf - _snap(offer, tick)) <= 0.01:
            return _mk_out("accept", _snap(offer, tick), floor, r, prev, anc_high_val, "final_accept_eq")
        return _mk_out("counter-final", _snap(cf, tick), floor, r, prev, anc_high_val, "final_counter")

    return _mk_out("counter", counter, floor, r, prev, anc_high_val, "normal_counter")
