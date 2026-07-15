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


def best_response(value, ctr_list, rivals, budget, num_slots, raise_top=False, top_bid=None):
    """Pick the profit-maximizing reachable slot and the minimum bid that SECURES it.

    rivals is sorted descending. To land in slot k you need exactly k rivals above you, so
    bid just above rivals[k] (the rival you displace) -- you then pay rivals[k]. When there
    are fewer rivals than k (the free bottom slot), bid 0: you sit last and pay 0. For each k
    utility = (value - price)*CTR[k]; skip negative-utility slots (price > value). This
    compares every paid slot against the free floor honestly and never over-bids into a higher
    (more expensive) slot than the one chosen. Always returns a finite bid in [0, budget].

    Cost-raise (`raise_top`) -- applied only when the profit-max slot is slot 1 (we sit right
    below the slot-0 winner). In GSP the slot-0 winner pays the bid of whoever is directly below
    it -- us -- so by bidding just under the winner's TRUE bid we force them to pay ~their full
    bid for slot 0 while we keep our cheap slot-1 price (set by the agent below US). `top_bid` is
    that identified true bid (the caller tracks each rival's exact bid across rounds: whenever an
    agent sits in slot k>=1, the price of slot k-1 IS its bid; for a constant bidder like dummy1
    this is exact after one observation). We then bid min(value, top_bid - eps) -- just under the
    top, so we do NOT overtake and our own slot/price are untouched.

    If `top_bid` is None (the slot-0 winner has never been seen outside slot 0 yet), we fall back
    to min(value, rivals[0]); note rivals[0] is a SELF-REFERENTIAL estimate here (when we hold
    slot 1, the slot-0 price we observe == our own prior bid), so the fallback tends to overtake.
    The value cap keeps util >= 0 (any slot we land in has price <= our bid <= value).

    Measured on the real server (paired CRN): the identified-top ('smart') form matches the
    self-referential form's ranking gain over the OFF baseline (~+5347 rank-margin, 4-agent) while
    recovering ~+765 of our own utility (the self-ref form overtook and cost us ~842). It raises
    our rank vs the naive dummies, though the 4-agent ABSOLUTE standing stays a near-tie (value-
    draw variance dominates) -- it does not guarantee first place. Kept OFF for Agent 2, which
    already dominates Task 2 (raising there cost ~2% absolute for no relative gain).
    """
    if not ctr_list or value <= 0:
        return 0.0
    n = min(num_slots, len(ctr_list))
    best_bid, best_u, best_k = 0.0, -1.0, None
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
        best_u, best_bid, best_k = u, min(max(0.0, bid), budget), k
    if best_u < 0:
        return 0.0
    if raise_top and best_k == 1 and rivals:
        if top_bid is not None:
            cap = min(value, max(0.0, float(top_bid) - _EPS))  # just under the TRUE top
        else:
            cap = min(value, rivals[0])                        # fallback: self-referential estimate
        best_bid = max(best_bid, min(cap, budget))
    return float(best_bid)


def choose_bid(value, ctr_list, num_slots, last_results, my_id, budget,
               num_agents=None, raise_top=False, top_bid=None):
    """Best-respond to the reconstructed rival bids; guaranteed a finite float in [0, budget].

    `raise_top` enables the slot-1 cost-raise on the slot-0 winner (see best_response). `top_bid`
    is the caller's cross-round-identified true bid of that winner; when supplied we sit just
    under it (no overtake), otherwise we fall back to the self-referential estimate.

    (A regime-aware `barbell` variant for the everyone-wins field was measured on the CRN
    tournament and REJECTED -- it lowered absolute utility and lost to dummy2 as well.
    `num_agents` is accepted but unused, kept for a future regime split.)
    """
    rivals = reconstruct_rivals(last_results, my_id, num_slots)
    bid = best_response(value, ctr_list, rivals, budget, num_slots,
                        raise_top=raise_top, top_bid=top_bid)
    if bid != bid or bid in (float("inf"), float("-inf")):
        return 0.0
    return float(bid)
