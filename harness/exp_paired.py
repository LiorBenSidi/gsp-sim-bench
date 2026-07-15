"""Paired-margin significance for the marginal cell (Task-1, 4-agent). CRN pairs each sim, so
the per-sim difference (ours - dummy) has far lower variance than the marginal CIs. We WIN
significantly iff the lower 95% bound of (ours - each dummy) is > 0.

Usage: PYTHONPATH=src python harness/exp_paired.py [num_sims]
"""
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

from hw3.agent1 import BiddingAgent1  # noqa: E402


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    diffs = {"dummy_1": [], "dummy_2": [], "dummy_3": []}
    agents = [BiddingAgent1(), id_dummy_1.BiddingAgent1(),
              id_dummy_2.BiddingAgent1(), id_dummy_3.BiddingAgent1()]
    agents[0].id = "ours"
    for s in range(n):
        random.seed(s)
        u = grader.run_simulation(agents, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS, enforce_budget=False)
        for d in diffs:
            diffs[d].append(u["ours"] - u[d])
    print(f"Task-1 4-agent paired margin (ours - dummy), {n} CRN sims:\n")
    print(f"  {'vs':<8} {'mean diff':>11} {'95% CI':>20} {'significant?':>14}")
    allsig = True
    for d, xs in diffs.items():
        m = statistics.fmean(xs)
        ci = 1.96 * statistics.pstdev(xs) / (len(xs) ** 0.5)
        lo, hi = m - ci, m + ci
        sig = "YES (win)" if lo > 0 else "no"
        allsig = allsig and lo > 0
        print(f"  {d:<8} {m:>11.1f}   [{lo:>8.1f}, {hi:>8.1f}] {sig:>14}")
    print(f"\n  => {'ALL beats significant' if allsig else 'NOT all significant'}")


if __name__ == "__main__":
    main()
