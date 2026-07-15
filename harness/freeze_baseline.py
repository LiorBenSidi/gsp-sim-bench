"""Freeze a regression baseline: the candidate's mean utility over a FIXED seed set (small T for
test speed), for Task 1 and Task 2 in the 4-agent field. Writes tests/Regression_Tests/
baseline_utilities.json. Re-run intentionally when a strategy improvement is accepted.
Usage: PYTHONPATH=src python harness/freeze_baseline.py"""
import json
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
from hw3.agent2 import BiddingAgent2  # noqa: E402

SEEDS = 20
T = 500  # small for test speed; deterministic under random.seed


def mean_util(cls, dummies, enforce_budget):
    agents = [cls()] + [d() for d in dummies]
    vals = []
    for s in range(SEEDS):
        random.seed(s)
        u = grader.run_simulation(agents, CONSTANTS.NUM_SLOTS, T, enforce_budget=enforce_budget)
        vals.append(u[agents[0].get_id()])
    return statistics.fmean(vals)


def compute():
    d1 = [id_dummy_1.BiddingAgent1, id_dummy_2.BiddingAgent1, id_dummy_3.BiddingAgent1]
    d2 = [id_dummy_1.BiddingAgent2, id_dummy_2.BiddingAgent2, id_dummy_3.BiddingAgent2]
    return {
        "seeds": SEEDS, "T": T,
        "task1_mean_util": round(mean_util(BiddingAgent1, d1, False), 2),
        "task2_mean_util": round(mean_util(BiddingAgent2, d2, True), 2),
    }


if __name__ == "__main__":
    out = ROOT / "tests" / "Regression_Tests" / "baseline_utilities.json"
    data = compute()
    out.write_text(json.dumps(data, indent=2) + "\n")
    print(f"wrote {out}: {data}")
