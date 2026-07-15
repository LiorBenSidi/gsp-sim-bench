"""Benchmark Agent-1 VARIANTS head-to-head on the real server (Task 1, no budget).

Purpose: decide whether an AGGRESSIVE / near-truthful Agent 1 beats all three dummies where the
shipped distribution-EU agent (strong07) does not. The field-coupling diagnostic showed a plain
bid=value agent sweeps at block 0 / N=150; this confirms it at high N on the exact grader config.

For EACH variant it runs the real fixtures/server.py over seeds 0..N-1, T=3000, field = the variant
+ id_dummy_1/2/3 (4 agents / 4 slots), and reports every agent's average utility with a 95% CI, plus
whether the variant BEATS ALL 3 dummies (the 40-pt criterion). Fixed seeds -> reproducible and
directly comparable to harness/benchmark.py and to a partner's run.

Task 2 (budget) is UNCHANGED (BiddingAgent2) across all variants -- run harness/benchmark.py for the
Task-2 numbers; this script only sweeps Agent 1.

Usage: PYTHONPATH=src python harness/benchmark_variants.py [num_sims]   (default 300)
       Recommended: N=5000 for a tight, decision-grade read (95% CI ~ ±950 on absolute utility).
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

from hw3.agent1 import BiddingAgent1  # noqa: E402  (currently strong07)


class TruthfulAgent1:
    """Aggressive / near-truthful Task-1 candidate: bid = shade * value (default truthful, shade=1.0;
    always capped at value so we never bid above value).

    Why (verified 2026-07-15, the field-coupling diagnostic): the 40-pt criterion is "beat EACH of
    the 3 dummies", which rewards SUPPRESSING the field (staying atop a compressed field), NOT
    maximizing our own utility. In GSP, low bids keep prices low so every rival keeps more utility;
    truthful bidding raises the price level and compresses everyone. A plain bid=value agent BEATS
    ALL THREE dummies (replica block 0, N=150: ours 39,798 > d2 36,123 > d1 34,279 > d3 31,698),
    where the distribution-EU best response (grabs cheap low slots, leaves d2 on top) LOSES d2.
    a peer's reported field matches this truthful row -> he is near-truthful. shade<1.0 sweeps the
    aggression axis. Lives in the harness (NOT src/hw3) until it wins -- keeps the bundle clean.
    Stdlib, O(1), far under the 50 ms cap."""

    def __init__(self, shade=1.0):
        self.id = "123456789_987654321"   # placeholder; bundler injects real IDs if promoted
        self.shade = float(shade)
        self.value = 0.0

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        self.value = float(value)

    def get_bid(self, current_budget_remaining):
        b = min(self.shade * self.value, float(current_budget_remaining), self.value)
        if b != b or b in (float("inf"), float("-inf")):
            return 0.0
        return float(max(0.0, b))

    def notify_round_results(self, round_results):
        pass

    def get_id(self):
        return self.id


def _make(factory, uid):
    a = factory()
    a.id = uid                     # keep get_id() AND internal self.id in sync (harness-bug guard)
    return a


# name -> zero-arg factory for the Agent-1 variant under test
VARIANTS = {
    "strong07 (shipped)": BiddingAgent1,
    "truthful  b=v":      lambda: TruthfulAgent1(1.0),
    "aggr      b=0.95v":  lambda: TruthfulAgent1(0.95),
    "aggr      b=0.90v":  lambda: TruthfulAgent1(0.90),
}
DUMMIES = [id_dummy_1.BiddingAgent1, id_dummy_2.BiddingAgent1, id_dummy_3.BiddingAgent1]


def bench_task1(factory, n):
    field = [_make(factory, "ours")] + [_make(d, f"dummy{i+1}") for i, d in enumerate(DUMMIES)]
    labels = [a.get_id() for a in field]
    per = {lab: [] for lab in labels}
    tick = ticker(n, "task1")
    for s in range(n):
        random.seed(s)                                      # FIXED seeds -> reproducible
        u = grader.run_simulation(field, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS, enforce_budget=False)
        for lab in labels:
            per[lab].append(u.get(lab, 0.0))
        tick(s + 1)
    return {lab: (statistics.fmean(v), 1.96 * statistics.pstdev(v) / (n ** 0.5)) for lab, v in per.items()}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    print("HW3 Agent-1 VARIANT sweep -- Task 1 (no budget), real fixtures/server.py.")
    print(f"Config: seeds 0..{n - 1}; T={CONSTANTS.T_ROUNDS}; {CONSTANTS.NUM_SLOTS} agents/"
          f"{CONSTANTS.NUM_SLOTS} slots; field = variant + id_dummy_1/2/3.\n")
    for name, factory in VARIANTS.items():
        rows = bench_task1(factory, n)
        ours = rows["ours"][0]
        beats_all = all(ours > rows[d][0] for d in ("dummy1", "dummy2", "dummy3"))
        flag = "  <<< BEATS ALL 3" if beats_all else "  (loses at least one)"
        print(f"== {name}   [N={n}] =={flag}")
        for lab, (m, ci) in sorted(rows.items(), key=lambda kv: kv[1][0], reverse=True):
            star = " <- ours" if lab == "ours" else ""
            print(f"   {lab:<8}{m:>12.1f}  ± {ci:>7.1f}{star}")
        print()
    print("BEATS ALL 3 = ours strictly > each dummy's average utility (the 40-pt criterion).")
    print("Task 2 is unchanged (BiddingAgent2) -- use harness/benchmark.py for Task-2 numbers.")


if __name__ == "__main__":
    main()
