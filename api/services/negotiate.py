from typing import Dict

def evaluate_offer(
    loadboard_rate: float,
    carrier_offer: float,
    round_num: int,
    *,
    floor_pct: float = 0.90,
    max_rounds: int = 3,
) -> Dict:
    """
    Three-round bounded-concession policy.

    ───────────────────────────────────────────────
    Definitions
    • floor  = loadboard_rate × floor_pct (default 90 %)
    • step % = portion of the gap we concede toward the floor
               {round1: 30 %, round2: 20 %, round3: 10 %}
    Rules
    • If carrier_offer ≥ (counter_rate − 25) → accept.
    • If round_num == max_rounds and still not accepted:
        – return “counter-final” at the floor rate so the caller
          has one last chance to meet our minimum.
        – If their offer is still < floor − 25 → reject.
    • Otherwise return “counter” with the new counter_rate.
    ───────────────────────────────────────────────
    Returned dict
    {
        "decision": "accept" | "counter" | "counter-final" | "reject",
        "counter_rate": float,
        "floor": float,
        "max_rounds": int
    }
    """

    # ── 1. Guard / normalise inputs ─────────────────────────────────
    round_num = max(1, min(round_num, max_rounds))
    floor = round(loadboard_rate * floor_pct, 2)

    # ── 2. Calculate this-round target (counter_rate) ───────────────
    step_map = {1: 0.30, 2: 0.20, 3: 0.10}
    step = step_map.get(round_num, 0.05)
    target = max(
        floor,
        round(loadboard_rate - (loadboard_rate - floor) * step * round_num, 2),
    )

    # ── 3. Accept if the carrier is close enough ────────────────────
    if carrier_offer >= target - 25:
        return {
            "decision": "accept",
            "counter_rate": carrier_offer,
            "floor": floor,
            "max_rounds": max_rounds,
        }

    # ── 4. Final-round logic ────────────────────────────────────────
    if round_num >= max_rounds:
        # Offer is still below our threshold
        if carrier_offer < floor - 25:
            return {
                "decision": "reject",
                "counter_rate": floor,
                "floor": floor,
                "max_rounds": max_rounds,
            }
        # Give one last take-it-or-leave-it opportunity at the floor
        return {
            "decision": "counter-final",
            "counter_rate": floor,
            "floor": floor,
            "max_rounds": max_rounds,
        }

    # ── 5. Normal counter case ──────────────────────────────────────
    return {
        "decision": "counter",
        "counter_rate": target,
        "floor": floor,
        "max_rounds": max_rounds,
    }
