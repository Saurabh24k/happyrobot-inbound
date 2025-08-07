from typing import Dict

def evaluate_offer(
    loadboard_rate: float,
    carrier_offer: float,
    round_num: int,
    floor_pct: float = 0.90,
    max_rounds: int = 3,
) -> Dict:
    """
    Simple bounded-concession policy.

    • Floor rate = loadboard_rate × floor_pct (default 90 %).
    • Each round we concede % of gap toward floor (30 %, 20 %, 10 %).
    • If carrier’s offer ≥ our counter − $25 → accept.
    • Auto-reject after max_rounds if still below floor-$25.
    """
    floor = round(loadboard_rate * floor_pct, 2)
    round_num = max(1, min(round_num, max_rounds))

    step_map = {1: 0.30, 2: 0.20, 3: 0.10}
    step = step_map.get(round_num, 0.05)
    target = max(
        floor,
        round(loadboard_rate - (loadboard_rate - floor) * step * round_num, 2),
    )

    # Decide
    if carrier_offer >= target - 25:
        return {
            "decision": "accept",
            "counter_rate": carrier_offer,
            "floor": floor,
            "max_rounds": max_rounds,
        }

    if round_num >= max_rounds and carrier_offer < floor - 25:
        return {
            "decision": "reject",
            "counter_rate": floor,
            "floor": floor,
            "max_rounds": max_rounds,
        }

    return {
        "decision": "counter",
        "counter_rate": target,
        "floor": floor,
        "max_rounds": max_rounds,
    }
