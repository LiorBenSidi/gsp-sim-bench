"""Validate the PROMOTED src hybrid (hw3.agent1.BiddingAgent1) reproduces the holdout 3/3 the
harness hybrid produced: block 400000, N=2000, single core. Expect hybrid d1 ~ +144 (beats all 3),
descent d1 ~ -108. If the src port matches, the shipped agent IS the validated strategy."""
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
from margin_agent import DescentAgent1                 # harness descent (shipped baseline)
from hw3.agent1 import BiddingAgent1                     # PROMOTED src hybrid

NS, T = CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS
BLOCK, N = 400_000, 2000


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


print(f"PORT VALIDATION  block {BLOCK}, T={T}, N={N}  (expect hybrid d1 ~ +144, all 3 > 0)\n")
for label, mk in (("descent(harness)", DescentAgent1), ("hybrid(src BiddingAgent1)", BiddingAgent1)):
    a1, a2, a3 = measure(mk)
    beat = all(x > 0 for x in (a1, a2, a3))
    print(f"  {label:26s}  d1 {a1:+8.1f}  d2 {a2:+8.1f}  d3 {a3:+8.1f}   beat-all-3={'YES' if beat else 'no'}")
