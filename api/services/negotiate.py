from __future__ import annotations
from typing import Dict, Any, Optional


def evaluate_offer(
    loadboard_rate: Any,
    carrier_offer: Any,
    round_num: Any,
    *,
    # Policy knobs
    floor_pct: float = 0.90,            # min we’ll proactively pay (as % of board)
    max_rounds: int = 3,
    tol: float = 15.0,                  # accept window vs targets/anchors (USD)
    tick: float = 5.0,                  # snap to $tick
    ceiling: Optional[float] = None,    # max we’ll pay (defaults to board)

    # Negotiation memory (pass these back in subsequent calls)
    prev_counter: Optional[Any] = None,     # our last counter (required r>=2)
    anchor_high: Optional[Any] = None,      # highest $ we’ve anchored earlier (e.g., r1 counter)

    # Contextual extras
    miles: Optional[Any] = None,            # lane miles (for dynamic tolerance)
    accept_close_to_prev: bool = True,      # accept if offer ≤ prev + tol
    dynamic_tol_by_miles: bool = True,      # bump tol on longer lanes
    accept_below_floor: bool = True,        # if they ask below our floor, accept it (we pay less)
    debug: bool = False,
    **_
) -> Dict:
    """
    We are the payer — lower is better.

    Output includes helper fields to keep your graph state in sync:
      decision: "accept" | "counter" | "counter-final" | "reject"
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
            # keep our counters non-increasing across rounds
            next_prev = price if prev_v is None else min(prev_v, price)
            # track the highest anchor we've ever set
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
    offer = max(0.0, _to_f(carrier_offer))  # offer may be 0 on "give me a number" probe
    # round_num may come as "", ensure sensible default
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

    # If graph resets round to 1 but we already have memory, bump to 2.
    r = r_in
    if r <= 1 and (prev is not None or anc_high_val is not None):
        r = 2
    r = max(1, min(r, max_rounds))

    # Effective tolerance (wider for longer lanes)
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

    # Never increase our counter vs history
    if prev is not None:
        target = min(target, prev)

    # Clamp & snap
    target = _snap(min(max(target, floor), ceil), tick)

    # ---------- fast accepts ----------
    # If they return to an earlier anchor we set, accept (avoid whiplash)
    if anc_high_val is not None and offer <= ceil:
        if abs(offer - anc_high_val) <= tol_eff:
            return _mk_out("accept", _snap(offer, tick), floor, r, prev, anc_high_val, "met_earlier_anchor")

    # Meeting/near our last counter? Accept at lower of {offer, prev}
    if prev is not None:
        if offer <= prev + (tol_eff if accept_close_to_prev else 0.0):
            return _mk_out("accept", _snap(min(offer, prev), tick), floor, r, prev, anc_high_val, "met_prev_anchor")

    # Under floor but allowed → accept (we pay less)
    if offer < floor and accept_below_floor:
        return _mk_out("accept", _snap(offer, tick), floor, r, prev, anc_high_val, "below_floor_accept")

    # Within target + tol → accept
    if offer <= target + tol_eff:
        return _mk_out("accept", _snap(offer, tick), floor, r, prev, anc_high_val, "within_target_tol")

    # ---------- regression guard ----------
    # If they raise above our last counter, hold that anchor (don’t drop further)
    if prev is not None and offer > prev + (tol_eff if accept_close_to_prev else 0.0):
        hold = _snap(prev, tick)
        if r >= max_rounds:
            return _mk_out("counter-final", hold, floor, r, prev, anc_high_val, "regression_hold_final")
        else:
            return _mk_out("counter", hold, floor, r, prev, anc_high_val, "regression_hold")

    # ---------- normal counter path ----------
    # Never counter above their ask; keep non-increasing vs prev.
    counter = min(target, offer)
    if prev is not None:
        counter = min(counter, prev)
    counter = _snap(max(counter, floor), tick)

    if r >= max_rounds:
        # Final round: choose strongest credible number ≤ ask, preferring anchors > floor.
        candidates = [counter, floor]
        if prev is not None:
            candidates.append(min(prev, offer))
        if anc_high_val is not None:
            candidates.append(min(anc_high_val, offer))
        cf = max(_snap(max(candidates), tick), _snap(floor, tick))
        if abs(cf - offer) <= 0.01:
            return _mk_out("accept", _snap(offer, tick), floor, r, prev, anc_high_val, "final_accept_eq")
        return _mk_out("counter-final", cf, floor, r, prev, anc_high_val, "final_counter")

    return _mk_out("counter", counter, floor, r, prev, anc_high_val, "normal_counter")
