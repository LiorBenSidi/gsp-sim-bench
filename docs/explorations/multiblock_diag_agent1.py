"""Per-block diagnosis of the SHIPPED hybrid (Agent 1) vs all 3 dummies, to see whether d1/d2 are
consistently near-0 or ever clearly negative. Replica engine (Task 1, byte-identical to server.py,
fast). Prints each disjoint seed block's paired margins ours-dummy_k + a pooled estimate.

  MB_NB=4 MB_N=2000 MB_T=3000 PYTHONPATH=src python docs/explorations/multiblock_diag_agent1.py
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
import id_dummy_1
import id_dummy_2
import id_dummy_3
from replica_sim import run_simulation_replica as sim
from hw3.agent1 import BiddingAgent1

NS = CONSTANTS.NUM_SLOTS
T = int(os.environ.get("MB_T", "3000"))
N = int(os.environ.get("MB_N", "2000"))
NB = int(os.environ.get("MB_NB", "4"))
OFFSETS = [0, 100000, 200000, 300000, 400000, 500000][:NB]

a = BiddingAgent1(); a.id = "ours"
d1 = id_dummy_1.BiddingAgent1(); d1.id = "d1"
d2 = id_dummy_2.BiddingAgent1(); d2.id = "d2"
d3 = id_dummy_3.BiddingAgent1(); d3.id = "d3"
field = [a, d1, d2, d3]


def ci(xs):
    return statistics.fmean(xs), 1.96 * statistics.pstdev(xs) / (len(xs) ** 0.5)


pooled = {"d1": [], "d2": [], "d3": []}
print(f"HYBRID vs dummies -- {NB} blocks x N={N}, T={T} (replica)\n")
for off in OFFSETS:
    m = {"d1": [], "d2": [], "d3": []}
    for s in range(N):
        random.seed(off + s)
        u = sim(field, NS, T, enforce_budget=False)
        for k in m:
            m[k].append(u["ours"] - u[k]); pooled[k].append(u["ours"] - u[k])
    parts = []
    for k in ("d1", "d2", "d3"):
        mm, cc = ci(m[k])
        parts.append(f"{k} {mm:+8.1f}±{cc:6.1f}{'*' if abs(mm) > cc else ' '}")
    print(f"  block {off:>7}: " + " | ".join(parts))
    sys.stdout.flush()

print("\nPOOLED (all blocks):")
for k in ("d1", "d2", "d3"):
    mm, cc = ci(pooled[k])
    sig = "SIGNIFICANT" if abs(mm) > cc else "TIE (CI incl 0)"
    print(f"  ours-{k}: {mm:+9.1f} ± {cc:6.1f}  {'WIN' if mm > 0 else 'LOSS'}, {sig}")
print("\n(* = block-level CI excludes 0)")
