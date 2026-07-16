"""Reproducible average-utility benchmark for comparing pairs by RESULT (no need for each
other's code). Each pair runs THIS exact script with their own agents; because the seed set is
FIXED, both agents face identical private-value draws and identical dummy behavior, so the two
average-utility numbers are directly comparable (a fair, low-variance head-to-head).

Field: your agent + the 3 provided naive dummies (num_agents == num_slots == 4), the real
fixtures/server.py, seeds 0..N-1, T=3000. Reports Agent 1's average utility (Task 1) and Agent
2's average utility (Task 2) -- the two numbers to exchange.

Config is printed so both pairs can confirm they ran the identical benchmark.

Usage: PYTHONPATH=src python harness/benchmark.py [num_sims]   (default 300)
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
from _progress import ticker  # noqa: E402

from hw3.agent1 import BiddingAgent1  # noqa: E402
from hw3.agent2 import BiddingAgent2  # noqa: E402


def _labelled(cls, uid):
    """Give the agent a display id by setting its OWN .id attribute -- so get_id() AND the
    agent's internal self.id (used to recognise itself in the results) stay in sync. Wrapping
    get_id() alone desyncs them and makes a self-identifying agent treat itself as a rival."""
    a = cls()
    a.id = uid
    return a


def bench(our_cls, dummies, enforce_budget, n, label="sims"):
    field = [_labelled(our_cls, "ours")] + [_labelled(d, f"dummy{i+1}") for i, d in enumerate(dummies)]
    labels = [a.get_id() for a in field]
    per = {lab: [] for lab in labels}
    tick = ticker(n, label)
    for s in range(n):
        random.seed(s)  # FIXED seed set -> reproducible & fair across pairs
        u = grader.run_simulation(field, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS, enforce_budget=enforce_budget)
        for lab in labels:
            per[lab].append(u.get(lab, 0.0))
        tick(s + 1)
    rows = {lab: (statistics.fmean(v), 1.96 * statistics.pstdev(v) / (n ** 0.5)) for lab, v in per.items()}
    return rows


def show(title, rows):
    print(f"\n== {title} ==")
    print(f"  {'rank':<5}{'agent':<10}{'avg utility':>13}{'95% CI':>10}")
    for i, (lab, (m, ci)) in enumerate(sorted(rows.items(), key=lambda kv: kv[1][0], reverse=True), 1):
        star = "  <- OURS (the number to compare)" if lab == "ours" else ""
        print(f"  {i:<5}{lab:<10}{m:>13.1f}{ci:>10.1f}{star}")


def threshold_check(title, rows):
    """Mirror server.py's print_threshold_check: full points if ours >= (1 - PASS_TOLERANCE) of
    EACH dummy's average utility (the 2026-07-16 relief). Sign-safe threshold like the server."""
    tol = getattr(CONSTANTS, "PASS_TOLERANCE", 0.05)
    ours = rows["ours"][0]
    print(f"\n  -- {title}: 95% threshold check (pass if ours >= {(1 - tol) * 100:.0f}% of each dummy) --")
    all_ok = True
    for d in ("dummy1", "dummy2", "dummy3"):
        du = rows[d][0]
        threshold = du - tol * abs(du)
        ok = ours >= threshold
        all_ok = all_ok and ok
        ratio = (ours / du * 100) if du else float("inf")
        print(f"     vs {d}: {ours:11,.1f} vs {du:11,.1f}  ({ratio:5.1f}%, need >= {threshold:11,.1f}) -> {'OK' if ok else 'BELOW'}")
    print(f"     => {'PASSED' if all_ok else 'DID NOT PASS'} the {title} threshold (40-pt part).")
    return all_ok


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    print("HW3 reproducible benchmark -- exchange the OURS numbers to compare pairs.")
    print(f"Config: field = your agent + 3 dummies (4 agents/4 slots); seeds 0..{n - 1}; "
          f"T={CONSTANTS.T_ROUNDS}; real fixtures/server.py; ENFORCE_TIME_CAP={CONSTANTS.ENFORCE_TIME_CAP}.")
    t1 = bench(BiddingAgent1, [id_dummy_1.BiddingAgent1, id_dummy_2.BiddingAgent1, id_dummy_3.BiddingAgent1], False, n, "task1")
    show(f"TASK 1  (no budget)  [{n} sims]", t1)
    threshold_check("Task 1", t1)
    t2 = bench(BiddingAgent2, [id_dummy_1.BiddingAgent2, id_dummy_2.BiddingAgent2, id_dummy_3.BiddingAgent2], True, n, "task2")
    show(f"TASK 2  (budget)     [{n} sims]", t2)
    threshold_check("Task 2", t2)


if __name__ == "__main__":
    main()
