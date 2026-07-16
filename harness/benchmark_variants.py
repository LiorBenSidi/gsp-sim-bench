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
from d2_hunt import (  # noqa: E402
    StochRaiseSlot2Agent1,
    ValueFloorStoch07Agent1,
    ValueFloorStochAgent1,
)
from replica_sim import run_simulation_replica  # noqa: E402

from hw3.agent1 import BiddingAgent1  # noqa: E402  (currently strong07)
from hw3.descent import StochRaiseAgent1  # noqa: E402

# VC_ENGINE=replica uses the Task-1 replica (byte-identical to server.py per test_replica_parity,
# ~100x faster) -- correct for this Task-1-only Agent-1 sweep and avoids the multi-hour real-server
# runtimes that timed out. Default "real" keeps the exact grader for one-off confirmations.
_ENGINE = os.environ.get("VC_ENGINE", "real").strip().lower()


def _run_sim(field, num_slots, t):
    if _ENGINE == "replica":
        return run_simulation_replica(field, num_slots, t, enforce_budget=False)
    return grader.run_simulation(field, num_slots, t, enforce_budget=False)


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


# Higher-FLOOR stochastic-raise ESCALATION -- the direct lever to WIDEN the d2 margin.
# strong07 raises our slot-1 bid to FLOOR*v_lb when d2 sits in slot 0 above us, at FLOOR=0.7.
# Pushing FLOOR up (0.8/0.9/1.0) makes d2 pay MORE for the top slot -> suppresses d2 harder ->
# bigger margin. It stays SURGICAL (fires only vs an identified d2 in slot 0, ~7-15% of rounds),
# so unlike pure truthful (which over-bids every round and collapsed own utility) it targets d2
# specifically. FLOOR>0.4 can occasionally overtake d2 -- that is the aggression tradeoff we measure.
class _StochF08(StochRaiseAgent1):
    FLOOR = 0.8


class _StochF09(StochRaiseAgent1):
    FLOOR = 0.9


class _StochF10(StochRaiseAgent1):
    FLOOR = 1.0


class _Slot2F09(StochRaiseSlot2Agent1):  # slot>=1 firing + strong FLOOR
    FLOOR = 0.9


# FINE VALUE-FLOOR sweep -- the ONLY direction that swept all 3 at N=3000 (C=0.7: d2 +128, d1 +134,
# ours 38,207 > the peer's 36,638). Higher C (own-utility floor bid>=C*value) suppresses the field more
# (d1 went from -396 at C=0.6 to +134 at C=0.7); pure truthful (C=1.0) collapses own utility and
# loses. So the widest ROBUST margin lives somewhere in C in [0.70, 0.95]. This sweep pins it.
class _VF072(ValueFloorStochAgent1):
    C = 0.72


class _VF075(ValueFloorStochAgent1):
    C = 0.75


class _VF078(ValueFloorStochAgent1):
    C = 0.78


class _VF080(ValueFloorStochAgent1):
    C = 0.80


class _VF085(ValueFloorStochAgent1):
    C = 0.85


class _VF090(ValueFloorStochAgent1):
    C = 0.90


class _VF095(ValueFloorStochAgent1):
    C = 0.95


# name -> zero-arg factory for the Agent-1 variant under test (fine value-floor C sweep).
VARIANTS = {
    "strong07(shipped)": BiddingAgent1,          # baseline (loses d2 at N=3000)
    "valuefloor C=0.70": ValueFloorStoch07Agent1,  # the N=3000 sweep winner so far
    "valuefloor C=0.72": _VF072,
    "valuefloor C=0.75": _VF075,
    "valuefloor C=0.78": _VF078,
    "valuefloor C=0.80": _VF080,
    "valuefloor C=0.85": _VF085,
    "valuefloor C=0.90": _VF090,
    "valuefloor C=0.95": _VF095,
}
DUMMIES = [id_dummy_1.BiddingAgent1, id_dummy_2.BiddingAgent1, id_dummy_3.BiddingAgent1]


def bench_task1(factory, n):
    field = [_make(factory, "ours")] + [_make(d, f"dummy{i+1}") for i, d in enumerate(DUMMIES)]
    labels = [a.get_id() for a in field]
    per = {lab: [] for lab in labels}
    tick = ticker(n, "task1")
    for s in range(n):
        random.seed(s)                                      # FIXED seeds -> reproducible
        u = _run_sim(field, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS)
        for lab in labels:
            per[lab].append(u.get(lab, 0.0))
        tick(s + 1)
    return {lab: (statistics.fmean(v), 1.96 * statistics.pstdev(v) / (n ** 0.5)) for lab, v in per.items()}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    # VC_VARIANT selects a single variant by key (used by the matrix workflow to parallelize
    # one variant per job). Empty -> run the whole sweep sequentially (local use).
    only = os.environ.get("VC_VARIANT", "").strip()
    variants = VARIANTS
    if only:
        variants = {k: v for k, v in VARIANTS.items() if k == only}
        if not variants:
            print(f"unknown VC_VARIANT {only!r}; available: {list(VARIANTS)}")
            sys.exit(1)
    print("HW3 Agent-1 VARIANT sweep -- Task 1 (no budget), real fixtures/server.py.")
    print(f"Config: seeds 0..{n - 1}; T={CONSTANTS.T_ROUNDS}; {CONSTANTS.NUM_SLOTS} agents/"
          f"{CONSTANTS.NUM_SLOTS} slots; engine={_ENGINE}; field = variant + id_dummy_1/2/3.\n")
    for name, factory in variants.items():
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
