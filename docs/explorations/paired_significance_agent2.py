"""Task-2 (budget-enforced) analogue of paired_significance.py.

The replica engine is Task-1 only (asserts enforce_budget is False and gives every agent infinite
budget), so Task 2 -- where the N(10000,750) budget is BINDING over T rounds -- must run on the real
threaded server.py. That's slow, so N/T are configurable via env (AG2_N, AG2_T). We capture the
grader's stdout and count latency-DQ sims (machine-load artifacts) so a contaminated run is visible.

Reports, over seeds 0..N-1, each paired margin ours(Agent2) - dummy_k(Agent2) with CRN + 95% CI +
whether it excludes 0 -- the correct 'does Agent 2 beat each dummy' test. Single core.

  AG2_N=300 AG2_T=2000 PYTHONPATH=src python docs/explorations/paired_significance_agent2.py
"""
import io
import os
import random
import statistics
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path("/Users/liorben/dev/ec-hw3-gsp-bidding-bot")
sys.path.insert(0, str(ROOT / "fixtures"))
sys.path.insert(0, str(ROOT / "src"))

import CONSTANTS
import id_dummy_1
import id_dummy_2
import id_dummy_3
import server as grader

from hw3.agent2 import BiddingAgent2

NS = CONSTANTS.NUM_SLOTS
T = int(os.environ.get("AG2_T", "2000"))
N = int(os.environ.get("AG2_N", "300"))

a = BiddingAgent2(); a.id = "ours"
d1 = id_dummy_1.BiddingAgent2(); d1.id = "d1"
d2 = id_dummy_2.BiddingAgent2(); d2.id = "d2"
d3 = id_dummy_3.BiddingAgent2(); d3.id = "d3"
field = [a, d1, d2, d3]

pair = {"d1": [], "d2": [], "d3": []}
absu = {"ours": [], "d1": [], "d2": [], "d3": []}
dq_sims = 0
for s in range(N):
    random.seed(s)
    buf = io.StringIO()
    with redirect_stdout(buf):
        u = grader.run_simulation(field, NS, T, enforce_budget=True)
    if "disqualified" in buf.getvalue():
        dq_sims += 1
    for k in absu:
        absu[k].append(u[k])
    for k in pair:
        pair[k].append(u["ours"] - u[k])
    if (s + 1) % 50 == 0:
        print(f"  {s + 1}/{N}  (dq_sims={dq_sims})", file=sys.stderr, flush=True)


def ci(xs):
    return statistics.fmean(xs), 1.96 * statistics.pstdev(xs) / (len(xs) ** 0.5)


print(f"\nTASK 2 (enforce_budget=True) -- seeds 0..{N - 1}, N={N}, T={T}, dq_sims={dq_sims}\n")
print("ABSOLUTE per-agent CI:")
for k in ("ours", "d1", "d2", "d3"):
    m, c = ci(absu[k]); print(f"  {k:5s} {m:10.1f} +- {c:7.1f}")
print("\nPAIRED margin ours - dummy_k (CRN -- the correct test):")
for k in ("d1", "d2", "d3"):
    m, c = ci(pair[k])
    sig = "SIGNIFICANT (CI excludes 0)" if abs(m) > c else "not significant (CI includes 0)"
    print(f"  ours - {k}: {m:+9.1f} +- {c:6.1f}   -> {'WIN' if m > 0 else 'LOSS'}, {sig}")
