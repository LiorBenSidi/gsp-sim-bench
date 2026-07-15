"""Empirical answer to: how many simulations for a given 95%-CI width, and does it depend on the
number of participants? Measures the per-sim std of our utility (drives the CI) in BOTH the
4-agent-vs-dummies field and a larger many-agent field, then prints the N needed for target
margins and to resolve the actual ours-vs-rival gaps.

95% CI half-width  E = 1.96 * sigma / sqrt(N)   ->   N = (1.96 * sigma / E)^2
So there is no single "minimum N"; N is set by sigma (metric noise) and E (precision wanted).

Usage: PYTHONPATH=src python harness/ci_sample_size.py [num_sims]
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


def _labelled(cls, uid):
    a = cls(); a.id = uid; return a


def measure(n, clones):
    """clones = extra copies of each dummy (0 -> 4-agent field; 3 -> 13-agent field)."""
    ours = _labelled(BiddingAgent1, "ours")
    field = [ours]
    for c in range(1 + clones):
        field.append(_labelled(id_dummy_1.BiddingAgent1, f"d1_{c}"))
        field.append(_labelled(id_dummy_2.BiddingAgent1, f"d2_{c}"))
        field.append(_labelled(id_dummy_3.BiddingAgent1, f"d3_{c}"))
    labels = [a.get_id() for a in field]
    per = {lab: [] for lab in labels}
    for s in range(n):
        random.seed(s)
        u = grader.run_simulation(field, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS, enforce_budget=False)
        for lab in labels:
            per[lab].append(u.get(lab, 0.0))
    return per, len(field)


def need_N(sigma, E):
    return (1.96 * sigma / E) ** 2


def report(title, per, n_agents):
    ours = per["ours"]
    sig = statistics.pstdev(ours)
    mean = statistics.fmean(ours)
    print(f"\n== {title}: {n_agents} agents ==")
    print(f"  our mean utility {mean:,.0f}   per-sim std (sigma) {sig:,.0f}")
    print("  N for a +/-E 95% CI on our absolute number:")
    for E in (2000, 1000, 500, 250):
        print(f"     E = +/-{E:<5} ->  N ~ {need_N(sig, E):>8,.0f} sims")
    # to resolve the gap vs the best rival (paired difference across the same sims)
    rivals = {k: v for k, v in per.items() if k != "ours"}
    best = max(rivals, key=lambda k: statistics.fmean(rivals[k]))
    diff = [o - r for o, r in zip(ours, rivals[best], strict=True)]  # same n sims
    gap = abs(statistics.fmean(diff))
    sdiff = statistics.pstdev(diff)
    n_to_detect = need_N(sdiff, gap) if gap > 0 else float("inf")
    print(f"  vs top rival ({best}): gap {gap:,.0f}, diff-std {sdiff:,.0f} "
          f"-> ~{n_to_detect:,.0f} sims to make the 95% CI exclude 0")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 800
    print(f"Sample-size analysis, {n} sims used to ESTIMATE sigma (Task 1, no budget).")
    per4, a4 = measure(n, 0)
    report("4-agent (vs the 3 dummies)", per4, a4)
    per13, a13 = measure(n, 3)
    report("13-agent (many participants)", per13, a13)
    print("\n  => sigma (hence the N you need) DOES change with the number of participants;")
    print("     participant count enters only through sigma, not as a separate term.")


if __name__ == "__main__":
    main()
