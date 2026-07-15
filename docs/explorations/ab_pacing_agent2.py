"""A/B the Agent-2 pacing cap on the real server (Task 2, enforce_budget=True).

Hypothesis: the shipped Agent 2 scales its best-response bid by min(1.5, budget_frac/time_frac).
When budget is NOT binding (budget_frac > time_frac) that INFLATES the bid above the myopic
profit-max bid -> in GSP that overtakes into a higher, more expensive slot the BR already judged
worse per-round, burning budget for less value. When budget IS binding the throttle-down (<1) is
the useful part. So we A/B cap=1.5 (shipped) vs cap=1.0 (throttle-only, never inflate).

Two fields per seed under common random numbers: [variant, d1, d2, d3] for each variant. Same
seeds -> same value/CTR/budget draws. Reports each variant's paired margins vs each dummy AND the
variant-vs-shipped paired margin. Single core, DQ-aware.

  AB_N=1000 AB_T=3000 PYTHONPATH=src python docs/explorations/ab_pacing_agent2.py
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
from hw3.strategy import choose_bid

NS = CONSTANTS.NUM_SLOTS
T = int(os.environ.get("AB_T", "3000"))
N = int(os.environ.get("AB_N", "1000"))


class CappedAgent2(BiddingAgent2):
    """Identical to the shipped Agent 2 but the pacing multiplier is capped at self.cap (default
    1.0 -> throttle-only, never inflate the BR bid above the myopic profit-max)."""
    cap = 1.0

    def get_bid(self, current_budget_remaining):
        self._round += 1
        if not self.CTR_list or current_budget_remaining <= 0:
            return 0.0
        budget = float(current_budget_remaining)
        if not self._last_results:
            return min(self.value * 0.9, budget)
        br = choose_bid(self.value, self.CTR_list, self.num_slots, self._last_results,
                        self.id, budget)
        rounds_left = max(1, self.T - self._round + 1)
        budget_frac = budget / self.total_budget if self.total_budget > 0 else 1.0
        time_frac = rounds_left / self.T
        pacing = budget_frac / time_frac if time_frac > 0 else 1.0
        bid = br * min(self.cap, max(0.0, pacing))
        bid = min(max(0.0, bid), budget, self.value)
        if bid != bid or bid in (float("inf"), float("-inf")):
            return 0.0
        return float(bid)


def run_field(make_ours):
    ours = make_ours(); ours.id = "ours"
    d1 = id_dummy_1.BiddingAgent2(); d1.id = "d1"
    d2 = id_dummy_2.BiddingAgent2(); d2.id = "d2"
    d3 = id_dummy_3.BiddingAgent2(); d3.id = "d3"
    field = [ours, d1, d2, d3]
    buf = io.StringIO()
    with redirect_stdout(buf):
        u = grader.run_simulation(field, NS, T, enforce_budget=True)
    return u, ("disqualified" in buf.getvalue())


VARIANTS = {"shipped(1.5)": BiddingAgent2, "capped(1.0)": CappedAgent2}
marg = {v: {"d1": [], "d2": [], "d3": []} for v in VARIANTS}
absu = {v: [] for v in VARIANTS}
dq = 0
for s in range(N):
    per = {}
    for vname, cls in VARIANTS.items():
        random.seed(s)                       # CRN: identical draws for each variant's field
        u, contaminated = run_field(cls)
        dq += int(contaminated)
        per[vname] = u["ours"]
        absu[vname].append(u["ours"])
        for k in ("d1", "d2", "d3"):
            marg[vname][k].append(u["ours"] - u[k])
    if (s + 1) % 50 == 0:
        print(f"  {s + 1}/{N} (dq={dq})", file=sys.stderr, flush=True)


def ci(xs):
    return statistics.fmean(xs), 1.96 * statistics.pstdev(xs) / (len(xs) ** 0.5)


print(f"\nAGENT-2 PACING A/B -- seeds 0..{N - 1}, N={N}, T={T}, dq={dq}\n")
for vname in VARIANTS:
    m, c = ci(absu[vname])
    print(f"[{vname}] abs util {m:9.1f} +- {c:6.1f}")
    for k in ("d1", "d2", "d3"):
        mm, cc = ci(marg[vname][k])
        sig = "SIG" if abs(mm) > cc else "ns "
        print(f"    ours-{k}: {mm:+9.1f} +- {cc:6.1f}  {sig}  {'WIN' if mm > 0 else 'LOSS'}")
# paired variant delta (capped - shipped), CRN across the two fields
delta = [absu["capped(1.0)"][i] - absu["shipped(1.5)"][i] for i in range(N)]
dm, dc = ci(delta)
print(f"\ncapped(1.0) - shipped(1.5) paired: {dm:+9.1f} +- {dc:6.1f}  "
      f"-> {'capped BETTER' if dm > 0 else 'shipped better'}, {'SIG' if abs(dm) > dc else 'ns'}")
