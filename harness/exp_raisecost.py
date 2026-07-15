"""Experiment: does raising our bid to the TOP of the inter-rival gap (forcing the agent
directly ABOVE us to pay more) beat the current bottom-of-gap best-response?

In GSP our own price is the bid of whoever sits directly BELOW us, so raising our bid while
staying in the same slot costs us nothing but inflates the cost of the agent above us. The
grader ranks by average utility (relative), so lowering dummy1's utility helps exactly as much
as raising ours. Capped at `value` -> we never pay more than value for any slot we could land
in (price = a rival strictly below our bid <= our bid <= value), so utility stays >= 0.

Compares candidate Agent-1 strategies in the REAL 4-agent server, CRN-paired. Reports each
agent's mean utility per sim; a candidate WINS iff its mean > every dummy's mean in its run.

Usage: PYTHONPATH=src python harness/exp_raisecost.py [num_sims]
"""
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fixtures"))
sys.path.insert(0, str(ROOT / "src"))
import CONSTANTS  # noqa: E402
import id_dummy_1  # noqa: E402
import id_dummy_2  # noqa: E402
import id_dummy_3  # noqa: E402
import server as grader  # noqa: E402

from hw3.strategy import reconstruct_rivals  # noqa: E402

_EPS = 1e-3


def _best_slot(value, ctr_list, rivals, num_slots):
    """Return (k*, price_at_k) for the profit-max reachable slot, or (None, 0) to abstain."""
    n = min(num_slots, len(ctr_list))
    best_k, best_u, best_price = None, -1.0, 0.0
    for k in range(n):
        price = rivals[k] if k < len(rivals) else 0.0
        if price > value:
            continue
        u = (value - price) * ctr_list[k]
        if u > best_u:
            best_k, best_u, best_price = k, u, price
    return best_k, best_price


def bid_bottom(value, ctr_list, rivals, num_slots, budget):
    """Current best-response: minimum bid that secures slot k* (bottom of the gap)."""
    if not ctr_list or value <= 0:
        return 0.0
    k, _ = _best_slot(value, ctr_list, rivals, num_slots)
    if k is None:
        return 0.0
    bid = (min(value, rivals[k] + _EPS)) if k < len(rivals) else 0.0
    return min(max(0.0, bid), budget)


def bid_top(value, ctr_list, rivals, num_slots, budget):
    """Top-of-gap: same slot k*, but bid just under the rival directly above us (capped at
    value) to force that rival to pay our high bid. Free for us; costly for them."""
    if not ctr_list or value <= 0:
        return 0.0
    k, _ = _best_slot(value, ctr_list, rivals, num_slots)
    if k is None:
        return 0.0
    if k == 0:
        bid = min(value, rivals[0] + _EPS) if rivals else 0.0  # nobody above -> just secure it
    else:
        # rivals[k-1] is the agent directly above us; bid just under it, capped at value.
        bid = min(value, rivals[k - 1] - _EPS)
        # never drop below what secures slot k (guard against tiny/crossed gaps)
        floor = min(value, rivals[k] + _EPS) if k < len(rivals) else 0.0
        bid = max(bid, floor)
    return min(max(0.0, bid), budget)


class Base:
    def __init__(self):
        self._reset()

    def _reset(self):
        self.value, self.ctr, self.ns, self.last = 0.0, [], 0, []

    def start_simulation(self, na, ns, ctr, v, tb, T):
        self._reset(); self.ns = ns; self.ctr = list(ctr); self.value = float(v)

    def notify_round_results(self, rr):
        self.last = rr or []

    def get_id(self):
        return self._id


def make(name, bidfn):
    def get_bid(self, budget):
        if not self.ctr or self.value <= 0:
            return 0.0
        if not self.last:
            return self.value * 0.9  # cold start
        rivals = reconstruct_rivals(self.last, self._id, self.ns)
        return float(bidfn(self.value, self.ctr, rivals, self.ns, self.value))
    return type(name, (Base,), {"_id": name, "get_bid": get_bid})


CANDIDATES = {
    "bottom": make("ours", bid_bottom),   # current shipped behavior
    "top": make("ours", bid_top),         # experimental cost-raise
}


def evaluate(cand_cls, num_sims):
    per = {"ours": [], "dummy1": [], "dummy2": [], "dummy3": []}
    for s in range(num_sims):
        random.seed(s)
        agents = [cand_cls(), id_dummy_1.BiddingAgent1(),
                  id_dummy_2.BiddingAgent1(), id_dummy_3.BiddingAgent1()]
        # relabel dummies to stable ids (their get_id already returns dummy_1/2/3)
        u = grader.run_simulation(agents, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS, enforce_budget=False)
        per["ours"].append(u["ours"])
        per["dummy1"].append(u["dummy_1"])
        per["dummy2"].append(u["dummy_2"])
        per["dummy3"].append(u["dummy_3"])
    return {k: statistics.fmean(v) for k, v in per.items()}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    print(f"raise-cost experiment ({n} sims, CRN). WIN = ours > every dummy.\n")
    for name, cls in CANDIDATES.items():
        m = evaluate(cls, n)
        margin = m["ours"] - max(m["dummy1"], m["dummy2"], m["dummy3"])
        verdict = "WIN " if margin > 0 else "lose"
        print(f"[{name:<7}] ours {m['ours']:9.1f} | d1 {m['dummy1']:9.1f}  d2 {m['dummy2']:9.1f} "
              f"d3 {m['dummy3']:9.1f} | margin {margin:+8.1f}  {verdict}")


if __name__ == "__main__":
    main()
