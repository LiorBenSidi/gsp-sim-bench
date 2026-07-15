"""BATCH validation of every d2-hunt candidate vs the shipped hybrid, CRN, on the replica (Task 1).

Two-stage discipline (avoid peeking at the holdout):
  Stage SCREEN (default): a SCRATCH block (offset 600000). Reports each candidate's paired margins
    vs d1/d2/d3, whether it BEATS ALL 3 (all means > 0), the delta vs shipped hybrid, and fire
    diagnostics. Pick survivors that beat all 3 without regressing d1/d3.
  Stage CONFIRM: rerun ONLY the survivors on the reserved holdout (offset 400000) -- set
    VC_OFF=400000 VC_ONLY=stoch_raise,stoch_slot2 (comma list) and require they still beat all 3.

Ship a candidate only if it beats all 3 on the holdout AND does not regress d1/d3 vs hybrid.

  # screen everything (moderate N first to save compute/heat):
  VC_N=800 VC_T=3000 VC_OFF=600000 PYTHONPATH=src python docs/explorations/validate_all_candidates.py
  # confirm survivors on the holdout:
  VC_N=3000 VC_T=3000 VC_OFF=400000 VC_ONLY=stoch_raise PYTHONPATH=src python docs/explorations/validate_all_candidates.py

Single core. Monitor machine temperature; kill if it climbs.
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
from d2_hunt import CANDIDATES

NS = CONSTANTS.NUM_SLOTS
T = int(os.environ.get("VC_T", "3000"))
N = int(os.environ.get("VC_N", "800"))
OFF = int(os.environ.get("VC_OFF", "600000"))
ONLY = [x for x in os.environ.get("VC_ONLY", "").split(",") if x]

registry = {"hybrid": BiddingAgent1, **CANDIDATES}
if ONLY:
    registry = {"hybrid": BiddingAgent1, **{k: v for k, v in CANDIDATES.items() if k in ONLY}}


def field(cls):
    a = cls(); a.id = "ours"
    d1 = id_dummy_1.BiddingAgent1(); d1.id = "d1"
    d2 = id_dummy_2.BiddingAgent1(); d2.id = "d2"
    d3 = id_dummy_3.BiddingAgent1(); d3.id = "d3"
    return a, [a, d1, d2, d3]


inst = {name: field(cls) for name, cls in registry.items()}   # reuse instances across sims
marg = {name: {"d1": [], "d2": [], "d3": []} for name in registry}
absu = {name: [] for name in registry}
fires = {name: [] for name in registry}
for s in range(N):
    for name in registry:
        ours, f = inst[name]
        random.seed(OFF + s)
        u = sim(f, NS, T, enforce_budget=False)
        absu[name].append(u["ours"])
        for k in ("d1", "d2", "d3"):
            marg[name][k].append(u["ours"] - u[k])
        fires[name].append(getattr(ours, "_sto_fires", 0))
    if (s + 1) % 100 == 0:
        print(f"  {s + 1}/{N}", file=sys.stderr, flush=True)


def ci(xs):
    return statistics.fmean(xs), 1.96 * statistics.pstdev(xs) / (len(xs) ** 0.5)


print(f"\nBATCH VALIDATION -- block {OFF} ({'HOLDOUT' if OFF == 400000 else 'scratch'}), "
      f"N={N}, T={T} (replica)\n")
hy = {k: statistics.fmean(marg['hybrid'][k]) for k in ('d1', 'd2', 'd3')}
for name in registry:
    means = {k: ci(marg[name][k]) for k in ('d1', 'd2', 'd3')}
    beat_all = all(means[k][0] > 0 for k in ('d1', 'd2', 'd3'))
    a_m, a_c = ci(absu[name])
    tag = "  <<< BEATS ALL 3" if beat_all else ""
    print(f"[{name:15}] abs {a_m:9.1f}±{a_c:6.1f}{tag}")
    for k in ('d1', 'd2', 'd3'):
        mm, cc = means[k]
        if name == "hybrid":
            dstr = ""
        else:
            # CRN paired delta vs hybrid on the SAME seed -- tight signal (same-family
            # correlation removes the field noise that dominates the raw margin CI).
            dseq = [marg[name][k][s] - marg['hybrid'][k][s] for s in range(N)]
            dm, dc = ci(dseq)
            sig = "*" if abs(dm) > dc else " "
            dstr = f"  (vs hybrid {dm:+8.1f} ± {dc:6.1f}{sig})"
        print(f"       ours-{k}: {mm:+9.1f} ± {cc:6.1f}  {'WIN ' if mm > 0 else 'LOSS'}"
              f"{'*' if abs(mm) > cc else ' '}{dstr}")
    af = statistics.fmean(fires[name])
    if af:
        print(f"       (avg stoch-raise fires/sim: {af:.1f})")
print("\n* on a margin = paired CI excludes 0.  '* ' on a (vs hybrid ...) = the CRN paired")
print("  candidate-minus-hybrid delta is significant (this is the decision-relevant number).")
print("BEATS ALL 3 = all three mean margins > 0 (grader criterion at high N).")
