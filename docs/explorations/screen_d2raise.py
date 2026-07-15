"""Screen the STOCHASTIC cost-raise (harness/d2_hunt.StochRaiseAgent1) vs the shipped hybrid
(hw3.agent1.BiddingAgent1), CRN, on a SCRATCH block (offset 600000 -- NOT the 400000 holdout, which
we reserve for a final confirm). Reports each variant's paired margins vs d1/d2/d3, the variant-minus-
hybrid delta, and diagnostics (avg stochastic-raise fires/sim + estimated d2-util removed/sim).
Replica (Task 1, fast). Single core.

  SD_N=800 SD_T=3000 SD_OFF=600000 PYTHONPATH=src python docs/explorations/screen_d2raise.py
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
from hw3.agent1 import BiddingAgent1          # shipped hybrid
from d2_hunt import StochRaiseAgent1          # experimental

NS = CONSTANTS.NUM_SLOTS
T = int(os.environ.get("SD_T", "3000"))
N = int(os.environ.get("SD_N", "800"))
OFF = int(os.environ.get("SD_OFF", "600000"))

VARIANTS = {"hybrid": BiddingAgent1, "stoch_raise": StochRaiseAgent1}


def field(cls):
    a = cls(); a.id = "ours"
    d1 = id_dummy_1.BiddingAgent1(); d1.id = "d1"
    d2 = id_dummy_2.BiddingAgent1(); d2.id = "d2"
    d3 = id_dummy_3.BiddingAgent1(); d3.id = "d3"
    return a, [a, d1, d2, d3]


marg = {v: {"d1": [], "d2": [], "d3": []} for v in VARIANTS}
absu = {v: [] for v in VARIANTS}
fires, removed = [], []
inst = {v: field(c) for v, c in VARIANTS.items()}   # reuse instances across sims (as the grader does)
for s in range(N):
    for vname in VARIANTS:
        ours, f = inst[vname]
        random.seed(OFF + s)
        u = sim(f, NS, T, enforce_budget=False)
        absu[vname].append(u["ours"])
        for k in ("d1", "d2", "d3"):
            marg[vname][k].append(u["ours"] - u[k])
        if vname == "stoch_raise":
            fires.append(getattr(ours, "_sto_fires", 0))
            removed.append(getattr(ours, "_sto_util_removed", 0.0))
    if (s + 1) % 100 == 0:
        print(f"  {s + 1}/{N}", file=sys.stderr, flush=True)


def ci(xs):
    return statistics.fmean(xs), 1.96 * statistics.pstdev(xs) / (len(xs) ** 0.5)


print(f"\nd2 STOCH-RAISE SCREEN -- block {OFF}, N={N}, T={T} (replica)\n")
for vname in VARIANTS:
    m, c = ci(absu[vname])
    print(f"[{vname}] abs {m:9.1f} ± {c:6.1f}")
    for k in ("d1", "d2", "d3"):
        mm, cc = ci(marg[vname][k])
        print(f"    ours-{k}: {mm:+9.1f} ± {cc:6.1f}  {'WIN ' if mm > 0 else 'LOSS'}{'*' if abs(mm) > cc else ' '}")
for k in ("d1", "d2", "d3"):
    d = [marg["stoch_raise"][k][i] - marg["hybrid"][k][i] for i in range(N)]
    dm, dc = ci(d)
    print(f"delta(stoch-hybrid) on {k}: {dm:+8.1f} ± {dc:6.1f}  {'*' if abs(dm) > dc else ' '}")
print(f"\ndiagnostics: avg fires/sim {statistics.fmean(fires):.1f} | "
      f"avg est d2-util removed/sim {statistics.fmean(removed):.1f} | "
      f"sims with >=1 fire {100 * sum(1 for x in fires if x) / len(fires):.0f}%")
