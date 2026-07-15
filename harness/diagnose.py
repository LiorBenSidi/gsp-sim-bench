"""Diagnostic: run the 4-agent regime over many CRN sims and report, per agent, WHY the
utilities differ -- slot distribution, avg price paid, avg cost & utility per round. Records
each agent's own outcomes from the public results stream (no re-implementation of the auction).

Usage:  PYTHONPATH=src python harness/diagnose.py [num_sims]
"""
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fixtures"))
sys.path.insert(0, str(ROOT / "src"))

import CONSTANTS  # noqa: E402
import id_dummy_1  # noqa: E402
import id_dummy_2  # noqa: E402
import id_dummy_3  # noqa: E402
import server as grader  # noqa: E402

from hw3.agent1 import BiddingAgent1  # noqa: E402
from hw3.agent2 import BiddingAgent2  # noqa: E402


class Spy:
    """Wrap an agent, record its own (slot, price) wins and its value/CTR each sim."""

    def __init__(self, inner, uid, stats):
        self._inner, self._uid, self._s = inner, uid, stats
        inner.id = uid  # keep the inner agent's self.id in sync with get_id (else it treats
        #                 its own wins as a rival's -- see harness/benchmark.py _labelled)

    def start_simulation(self, num_agents, num_slots, ctr, value, budget, T):
        self._value, self._ctr = value, ctr
        return self._inner.start_simulation(num_agents, num_slots, ctr, value, budget, T)

    def get_bid(self, b):
        return self._inner.get_bid(b)

    def notify_round_results(self, rr):
        for (w, slot, price) in rr:
            if w == self._uid:
                s = self._s[self._uid]
                s["rounds"] += 1
                s["slot"][slot] += 1
                s["price"] += price
                s["cost"] += price * self._ctr[slot]
                s["util"] += (self._value - price) * self._ctr[slot]
        return self._inner.notify_round_results(rr)

    def get_id(self):
        return self._uid


def diagnose(factories, enforce_budget, num_sims):
    stats = {lab: {"rounds": 0, "slot": defaultdict(int), "price": 0.0, "cost": 0.0, "util": 0.0}
             for lab, _ in factories}
    agents = [Spy(cls(), lab, stats) for lab, cls in factories]
    for s in range(num_sims):
        random.seed(s)
        grader.run_simulation(agents, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS, enforce_budget=enforce_budget)
    return stats


def report(title, stats):
    print(f"\n== {title} ==")
    print(f"  {'agent':<8} {'won/rnd':>8} {'slots(0/1/2/3)':>18} {'avgPrice':>9} {'cost/rnd':>9} {'util/rnd':>9}")
    order = sorted(stats.items(), key=lambda kv: kv[1]["util"], reverse=True)
    total_rounds = CONSTANTS.T_ROUNDS
    for lab, s in order:
        r = max(1, s["rounds"])
        dist = "/".join(f"{s['slot'][j] / (total_rounds * NUM_SIMS):.0%}" for j in range(4))
        winrate = s["rounds"] / (total_rounds * NUM_SIMS)
        print(f"  {lab:<8} {winrate:>8.2f} {dist:>18} {s['price'] / r:>9.2f} "
              f"{s['cost'] / (total_rounds * NUM_SIMS):>9.2f} {s['util'] / (total_rounds * NUM_SIMS):>9.2f}")


NUM_SIMS = int(sys.argv[1]) if len(sys.argv) > 1 else 60

d1 = [("ours", BiddingAgent1), ("dummy1", id_dummy_1.BiddingAgent1),
      ("dummy2", id_dummy_2.BiddingAgent1), ("dummy3", id_dummy_3.BiddingAgent1)]
d2 = [("ours", BiddingAgent2), ("dummy1", id_dummy_1.BiddingAgent2),
      ("dummy2", id_dummy_2.BiddingAgent2), ("dummy3", id_dummy_3.BiddingAgent2)]
report("TASK 1 (4 agents) -- slot dist / price / cost / utility per round",
       diagnose(d1, False, NUM_SIMS))
report("TASK 2 (4 agents)", diagnose(d2, True, NUM_SIMS))
