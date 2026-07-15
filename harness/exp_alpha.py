"""Sweep the cost-raise intensity in the 4-agent Task-1 regime.

Base best-response picks the profit-max slot k* and its price = rivals[k*] (set by the agent
below us -- unaffected by our own bid). We then raise our bid toward the rival directly ABOVE
us to inflate THEIR cost (free for us in a static market). Two knobs:

  alpha in [0,1]: bid = rivals[k*] + alpha*(rivals[k*-1] - rivals[k*])  (0=bottom, 1=full top)
  top_only:       apply the raise ONLY when k*==1 (directly below the slot-0 winner, our chief
                  rival) -- minimizes broad market inflation that feeds dummy3's 1.1*median rule.

All bids capped at `value` -> utility stays >= 0. Reports each variant's mean utility vs the
dummies over CRN-paired real-server sims; WIN = ours > every dummy.

Usage: PYTHONPATH=src python harness/exp_alpha.py [num_sims]
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
    n = min(num_slots, len(ctr_list))
    best_k, best_u = None, -1.0
    for k in range(n):
        price = rivals[k] if k < len(rivals) else 0.0
        if price > value:
            continue
        u = (value - price) * ctr_list[k]
        if u > best_u:
            best_k, best_u = k, u
    return best_k


def make_bidder(alpha, top_only):
    def bid(value, ctr_list, rivals, num_slots):
        if not ctr_list or value <= 0:
            return 0.0
        k = _best_slot(value, ctr_list, rivals, num_slots)
        if k is None:
            return 0.0
        if k >= len(rivals):                           # free floor: below all rivals, pay 0
            return 0.0
        if k == 0:                                     # top slot: nobody above to charge
            return min(value, rivals[0] + _EPS)
        floor = min(value, rivals[k] + _EPS)          # bottom: secure slot k
        above = rivals[k - 1]                          # rival directly above us
        if top_only and k != 1:
            return floor
        raised = min(value, rivals[k] + alpha * max(0.0, above - rivals[k]))
        return max(floor, raised)
    return bid


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
        return "ours"


def make(bidfn):
    def get_bid(self, budget):
        if not self.ctr or self.value <= 0:
            return 0.0
        if not self.last:
            return self.value * 0.9
        rivals = reconstruct_rivals(self.last, "ours", self.ns)
        return float(min(bidfn(self.value, self.ctr, rivals, self.ns), budget))
    return type("Cand", (Base,), {"get_bid": get_bid})


def evaluate(cand_cls, num_sims):
    per = {"ours": [], "dummy_1": [], "dummy_2": [], "dummy_3": []}
    for s in range(num_sims):
        random.seed(s)
        agents = [cand_cls(), id_dummy_1.BiddingAgent1(),
                  id_dummy_2.BiddingAgent1(), id_dummy_3.BiddingAgent1()]
        u = grader.run_simulation(agents, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS, enforce_budget=False)
        for k in per:
            per[k].append(u[k])
    return {k: statistics.fmean(v) for k, v in per.items()}


VARIANTS = [
    ("alpha=0.0", make(make_bidder(0.0, False))),
    ("alpha=0.25", make(make_bidder(0.25, False))),
    ("alpha=0.5", make(make_bidder(0.5, False))),
    ("alpha=0.75", make(make_bidder(0.75, False))),
    ("alpha=1.0", make(make_bidder(1.0, False))),
    ("top_only=1.0", make(make_bidder(1.0, True))),
    ("top_only=0.5", make(make_bidder(0.5, True))),
]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    print(f"alpha sweep, Task-1 4-agent ({n} sims, CRN). WIN = ours > every dummy.\n")
    print(f"  {'variant':<14} {'ours':>9} {'dummy1':>9} {'dummy2':>9} {'dummy3':>9} {'margin':>9}")
    for name, cls in VARIANTS:
        m = evaluate(cls, n)
        margin = m["ours"] - max(m["dummy_1"], m["dummy_2"], m["dummy_3"])
        tag = "  WIN" if margin > 0 else ""
        print(f"  {name:<14} {m['ours']:>9.0f} {m['dummy_1']:>9.0f} {m['dummy_2']:>9.0f} "
              f"{m['dummy_3']:>9.0f} {margin:>+9.0f}{tag}")


if __name__ == "__main__":
    main()
