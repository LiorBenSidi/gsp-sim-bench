"""Measure descent's block-0 T=500 20-seed own utility (the regression baseline setup) vs champion,
so we know BEFORE porting whether re-freezing task1_mean_util is upward or downward. Real server,
20 sims T=500 -- cheap, NOT heavy. Also prints per-dummy margins as a sanity check."""
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
import server as grader
from margin_agent import DescentAgent1
from hw3.agent1 import BiddingAgent1 as Champion

SEEDS, T = 20, 500


def run(make_ours):
    o, m1, m2, m3 = [], [], [], []
    a = make_ours(); a.id = "ours"
    d1 = id_dummy_1.BiddingAgent1(); d1.id = "d1"
    d2 = id_dummy_2.BiddingAgent1(); d2.id = "d2"
    d3 = id_dummy_3.BiddingAgent1(); d3.id = "d3"
    field = [a, d1, d2, d3]
    for s in range(SEEDS):
        random.seed(s)
        u = grader.run_simulation(field, CONSTANTS.NUM_SLOTS, T, enforce_budget=False)
        o.append(u["ours"]); m1.append(u["ours"] - u["d1"]); m2.append(u["ours"] - u["d2"]); m3.append(u["ours"] - u["d3"])
    return statistics.fmean(o), statistics.fmean(m1), statistics.fmean(m2), statistics.fmean(m3)


for label, mk in (("champion(src)", Champion), ("descent(harness)", DescentAgent1)):
    own, a1, a2, a3 = run(mk)
    print(f"{label:20s} own_mean={own:9.2f}  margins d1={a1:+8.1f} d2={a2:+8.1f} d3={a3:+8.1f}")
print("\nregression baseline task1_mean_util = 7265.23 (champion, must stay >= this - 1.0)")
