"""Decisive cross-block sign check: does descent's d2 win generalize beyond block 200000?
Compare champion vs descent at BLOCK 0, full T=3000, replica engine (byte-identical to real),
single process (safe thermally). Small N for speed. We already know block 200000 from prior runs:
  champion  d1 -395  d2 -1950  d3 +3994   (loses d1,d2)
  descent   d1 -446  d2  +413  d3 +4726   (wins d2,d3)
This asks: at block 0 (full T), does descent STILL beat d2 and champion still lose it?"""
import random
import statistics
import sys
from pathlib import Path

ROOT = Path("/Users/liorben/dev/ec-hw3-gsp-bidding-bot")
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "fixtures"))
sys.path.insert(0, str(ROOT / "src"))

import CONSTANTS
import id_dummy_1, id_dummy_2, id_dummy_3
from replica_sim import run_simulation_replica as sim
from margin_agent import DescentAgent1
from hw3.agent1 import BiddingAgent1 as Champion

NS, T = CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS
BLOCK, N = 0, 200


def field(mk):
    a = mk(); a.id = "ours"
    d1 = id_dummy_1.BiddingAgent1(); d1.id = "d1"
    d2 = id_dummy_2.BiddingAgent1(); d2.id = "d2"
    d3 = id_dummy_3.BiddingAgent1(); d3.id = "d3"
    return [a, d1, d2, d3]


def measure(mk):
    f = field(mk)
    m1, m2, m3 = [], [], []
    for s in range(BLOCK, BLOCK + N):
        random.seed(s)
        u = sim(f, NS, T, enforce_budget=False)
        m1.append(u["ours"] - u["d1"]); m2.append(u["ours"] - u["d2"]); m3.append(u["ours"] - u["d3"])
    return statistics.fmean(m1), statistics.fmean(m2), statistics.fmean(m3)


print(f"BLOCK {BLOCK}, T={T}, N={N}, replica engine  (paired vs each dummy; WIN = >0)\n")
for label, mk in (("champion", Champion), ("descent", DescentAgent1)):
    a1, a2, a3 = measure(mk)
    beat = all(x > 0 for x in (a1, a2, a3))
    print(f"  {label:9s}  d1 {a1:+8.1f}  d2 {a2:+8.1f}  d3 {a3:+8.1f}   beat-all-3={'YES' if beat else 'no'}")
