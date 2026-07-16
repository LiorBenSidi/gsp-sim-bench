"""Agent-2 (Task 2, budget-constrained) pacing-cap sweep on the REAL server.

The replica is Task-1-only, so Agent 2 MUST use fixtures/server.py (enforce_budget=True). Goal:
(1) confirm the shipped agent does NOT regress, (2) find the pacing cap that ADVANCES Task 2 furthest.
The shipped agent bids `best_response * min(1.5, budget_frac/time_frac)` -- capping LOWER (1.0)
regressed (measured), so the lever to advance is a HIGHER cap (spend more aggressively when
under budget). PacedAgent2 re-exposes that cap; CAP=1.5 must reproduce the shipped agent exactly
(sanity-checked below). Fixed seeds 0..N-1 -> reproducible + comparable to the reference peer.

Usage: PYTHONPATH=src python harness/benchmark_agent2.py [num_sims]   (default 300; N=3000 = peer cfg)
"""
import os
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fixtures"))
sys.path.insert(0, str(ROOT / "src"))
import CONSTANTS  # noqa: E402
import id_dummy_1  # noqa: E402
import id_dummy_2  # noqa: E402
import id_dummy_3  # noqa: E402
import server as grader  # noqa: E402
from _progress import ticker  # noqa: E402

from hw3.agent2 import BiddingAgent2  # noqa: E402  (the shipped Agent 2)
from hw3.strategy import choose_bid  # noqa: E402


class PacedAgent2(BiddingAgent2):
    """Shipped Agent 2 with the pacing cap exposed as CAP (default 1.5 == shipped behavior). Only
    get_bid is overridden -- a verbatim copy of the shipped logic with `1.5` -> `self.CAP`."""

    CAP = 1.5

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
        bid = br * min(self.CAP, max(0.0, pacing))
        bid = min(max(0.0, bid), budget, self.value)
        if bid != bid or bid in (float("inf"), float("-inf")):
            return 0.0
        return float(bid)


class _Cap18(PacedAgent2):
    CAP = 1.8


class _Cap20(PacedAgent2):
    CAP = 2.0


class _Cap25(PacedAgent2):
    CAP = 2.5


class _Cap30(PacedAgent2):
    CAP = 3.0


VARIANTS = {
    "shipped (cap1.5)": BiddingAgent2,   # the real shipped Agent 2 -- baseline / no-regression anchor
    "cap 1.8":          _Cap18,
    "cap 2.0":          _Cap20,
    "cap 2.5":          _Cap25,
    "cap 3.0":          _Cap30,
}
DUMMIES = [id_dummy_1.BiddingAgent2, id_dummy_2.BiddingAgent2, id_dummy_3.BiddingAgent2]


def _make(factory, uid):
    a = factory()
    a.id = uid
    return a


def bench_task2(factory, n):
    field = [_make(factory, "ours")] + [_make(d, f"dummy{i+1}") for i, d in enumerate(DUMMIES)]
    labels = [a.get_id() for a in field]
    per = {lab: [] for lab in labels}
    tick = ticker(n, "task2")
    for s in range(n):
        random.seed(s)                                      # FIXED seeds -> reproducible
        u = grader.run_simulation(field, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS, enforce_budget=True)
        for lab in labels:
            per[lab].append(u.get(lab, 0.0))
        tick(s + 1)
    return {lab: (statistics.fmean(v), 1.96 * statistics.pstdev(v) / (n ** 0.5)) for lab, v in per.items()}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    only = os.environ.get("VC_VARIANT", "").strip()
    variants = VARIANTS
    if only:
        variants = {k: v for k, v in VARIANTS.items() if k == only}
        if not variants:
            print(f"unknown VC_VARIANT {only!r}; available: {list(VARIANTS)}")
            sys.exit(1)
    print("HW3 Agent-2 pacing-cap sweep -- Task 2 (budget), real fixtures/server.py.")
    print(f"Config: seeds 0..{n - 1}; T={CONSTANTS.T_ROUNDS}; {CONSTANTS.NUM_SLOTS} agents/"
          f"{CONSTANTS.NUM_SLOTS} slots; field = variant + id_dummy_1/2/3 (Task-2 budget variants).\n")
    for name, factory in variants.items():
        rows = bench_task2(factory, n)
        ours = rows["ours"][0]
        beats_all = all(ours > rows[d][0] for d in ("dummy1", "dummy2", "dummy3"))
        flag = "  <<< BEATS ALL 3" if beats_all else "  (loses at least one)"
        print(f"== {name}   [N={n}] =={flag}")
        for lab, (m, ci) in sorted(rows.items(), key=lambda kv: kv[1][0], reverse=True):
            star = " <- ours" if lab == "ours" else ""
            print(f"   {lab:<8}{m:>12.1f}  ± {ci:>7.1f}{star}")
        print()
    print("Higher ours = better (Task 2 is a pure own-utility race; leftover budget is worthless).")


if __name__ == "__main__":
    main()
