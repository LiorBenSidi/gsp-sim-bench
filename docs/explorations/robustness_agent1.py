"""Front-4 peer-robustness read for Agent 1 (Task 1, replica engine -- fast, byte-identical).

We can't measure the real competition (other students' bots are unknown), so instead we characterize
how our Agent 1 behaves against PLAUSIBLE strategies a peer might submit: truthful (bid=value),
shaders (bid=f*value), a naive avg-price tracker, and self-play (4x ours). For each field we report
ours' absolute utility, its rank among the 4, the min utility seen (sanity: never wildly negative),
and confirm all outputs are finite. This is a robustness/sanity read, NOT a tuned peer strategy.

  ROB_N=500 ROB_T=3000 PYTHONPATH=src python docs/explorations/robustness_agent1.py
"""
import os
import random
import statistics
import sys
from pathlib import Path

ROOT = Path("/Users/liorben/dev/ec-hw3-gsp-bidding-bot")
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "fixtures"))
sys.path.insert(0, str(ROOT / "src"))

import CONSTANTS
from replica_sim import run_simulation_replica as sim
from hw3.agent1 import BiddingAgent1

NS = CONSTANTS.NUM_SLOTS
T = int(os.environ.get("ROB_T", "3000"))
N = int(os.environ.get("ROB_N", "500"))


class Truthful:
    def __init__(self, tag): self.id = tag
    def start_simulation(self, na, ns, ctr, v, tb, T): self.v = float(v)
    def get_bid(self, b): return self.v
    def notify_round_results(self, r): pass
    def get_id(self): return self.id


class Shade:
    def __init__(self, tag, f): self.id = tag; self.f = f
    def start_simulation(self, na, ns, ctr, v, tb, T): self.v = float(v)
    def get_bid(self, b): return self.f * self.v
    def notify_round_results(self, r): pass
    def get_id(self): return self.id


class AvgTracker:
    """Naive: aim just above the average clearing price (a plausible student heuristic)."""
    def __init__(self, tag): self.id = tag; self.last = []
    def start_simulation(self, na, ns, ctr, v, tb, T): self.v = float(v); self.last = []
    def get_bid(self, b):
        base = self.v * 0.6 if not self.last else min(self.v * 0.9,
                                                       (sum(self.last) / len(self.last)) * 1.1)
        return base
    def notify_round_results(self, r):
        self.last = [p for _w, _s, p in r if p > 0] or [0.0]
    def get_id(self): return self.id


def ours(tag):
    a = BiddingAgent1(); a.id = tag; return a


FIELDS = {
    "vs 3x truthful": lambda: [ours("ours"), Truthful("t1"), Truthful("t2"), Truthful("t3")],
    "vs 3x shade0.7": lambda: [ours("ours"), Shade("s1", 0.7), Shade("s2", 0.7), Shade("s3", 0.7)],
    "vs mixed (truthful/shade.85/shade.5)": lambda: [ours("ours"), Truthful("t1"),
                                                     Shade("s85", 0.85), Shade("s5", 0.5)],
    "vs 3x avg-tracker": lambda: [ours("ours"), AvgTracker("a1"), AvgTracker("a2"), AvgTracker("a3")],
    "self-play (4x ours)": lambda: [ours("o0"), ours("o1"), ours("o2"), ours("o3")],
}

print(f"AGENT-1 ROBUSTNESS -- replica (Task 1), seeds 0..{N - 1}, N={N}, T={T}\n")
for name, make in FIELDS.items():
    ours_u, ranks, mins, bad = [], [], [], 0
    for s in range(N):
        random.seed(s)
        field = make()
        u = sim(field, NS, T, enforce_budget=False)
        vals = list(u.values())
        if any(x != x or x in (float("inf"), float("-inf")) for x in vals):
            bad += 1; continue
        mins.append(min(vals))
        if name.startswith("self-play"):
            ours_u.append(u["o0"]); ranks.append(sorted(vals, reverse=True).index(u["o0"]) + 1)
        else:
            ours_u.append(u["ours"]); ranks.append(sorted(vals, reverse=True).index(u["ours"]) + 1)
    m = statistics.fmean(ours_u); c = 1.96 * statistics.pstdev(ours_u) / (len(ours_u) ** 0.5)
    avg_rank = statistics.fmean(ranks); min_seen = min(mins)
    firsts = sum(1 for r in ranks if r == 1)
    print(f"[{name}]")
    print(f"    ours util {m:9.1f} +- {c:6.1f} | avg rank {avg_rank:.2f}/4 | "
          f"#1 in {100 * firsts / len(ranks):4.1f}% | min-util-any-agent {min_seen:.1f} | "
          f"nonfinite {bad}")
