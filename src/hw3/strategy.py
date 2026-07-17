"""Shared GSP bidding logic for HW3 (stdlib-only).

Verified mechanics (from fixtures/server.py):
  - Your bid sets your RANK, not your price. The price for slot j is the raw bid of the
    agent directly below you; cost = price * CTR[slot]; utility += (value - price)*CTR[slot].
  - `notify_round_results` delivers ONLY the current round's <= num_slots winner tuples
    (agent_id, slot, price) -- the agent must accumulate its own history.
  - The price paid for slot j == the raw bid of the agent in slot j+1, so rival bids are
    reconstructed almost exactly from the public results (system identification, not a bandit).
"""

_EPS = 1e-3


def reconstruct_rivals(last_results, my_id, num_slots):
    """Estimate rivals' bids from the previous round's (winner_id, slot, price) tuples.

    The occupant of slot k (k>=1) bid == the price paid for slot k-1; the top occupant's
    bid is hidden, so estimate it just above the slot-0 price. Exclude ourselves.
    Returns rival bids sorted descending.
    """
    price_by_slot = {slot: float(price) for (_w, slot, price) in last_results}
    winner_by_slot = {slot: w for (w, slot, _p) in last_results}
    rivals = []
    for k in range(num_slots):
        if k not in winner_by_slot:
            continue
        if k == 0:
            occ_bid = price_by_slot.get(0, 0.0) * 1.1 + 1.0
        else:
            occ_bid = price_by_slot.get(k - 1, 0.0)
        if winner_by_slot[k] != my_id:
            rivals.append(occ_bid)
    return sorted(rivals, reverse=True)


def best_response(value, ctr_list, rivals, budget, num_slots):
    """Pick the profit-maximizing reachable slot and the minimum bid that SECURES it.

    rivals is sorted descending. To land in slot k you need exactly k rivals above you, so
    bid just above rivals[k] (the rival you displace) -- you then pay rivals[k]. When there
    are fewer rivals than k (the free bottom slot), bid 0: you sit last and pay 0. For each k
    utility = (value - price)*CTR[k]; skip negative-utility slots (price > value). This
    compares every paid slot against the free floor honestly and never over-bids into a higher
    (more expensive) slot than the one chosen. Always returns a finite bid in [0, budget].
    """
    if not ctr_list or value <= 0:
        return 0.0
    n = min(num_slots, len(ctr_list))
    best_bid, best_u = 0.0, -1.0
    for k in range(n):
        price = rivals[k] if k < len(rivals) else 0.0  # what we pay if we sit in slot k
        if price > value:
            continue
        u = (value - price) * ctr_list[k]
        if u <= best_u:
            continue
        if k < len(rivals):
            bid = min(value, rivals[k] + _EPS)  # just above the displaced rival -> slot k
        else:
            bid = 0.0                           # free floor: below all rivals -> last slot, pay 0
        best_u, best_bid = u, min(max(0.0, bid), budget)
    if best_u < 0:
        return 0.0
    return float(best_bid)


def choose_bid(value, ctr_list, num_slots, last_results, my_id, budget):
    """Best-respond to the reconstructed rival bids; guaranteed a finite float in [0, budget]."""
    rivals = reconstruct_rivals(last_results, my_id, num_slots)
    bid = best_response(value, ctr_list, rivals, budget, num_slots)
    if bid != bid or bid in (float("inf"), float("-inf")):
        return 0.0
    return float(bid)
