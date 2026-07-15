"""Definitive paired treatment-effect test for raise_top (Task-1, 4-agent).

The huge per-sim variance in `ours - dummy` comes from each agent's private value being redrawn
every sim -- that swamps a ~300-point strategy effect. To ISOLATE the effect of raise_top we run
each seed TWICE: our agent with raise_top OFF, then ON. Our agent consumes no RNG, and the
dummies consume the global RNG stream identically either way (dummy2 draws once per round
regardless), so the SAME seed yields identical private values and identical dummy draws in both
runs. Every difference is therefore caused by raise_top alone -> the paired delta has tiny
variance.

We report, paired per seed:
  d_ours   = ours_ON   - ours_OFF        (does the raise cost US anything?)
  d_dummy1 = dummy1_ON - dummy1_OFF      (do we crush the top rival?)
  d_rank   = (ours-bestDummy)_ON - (ours-bestDummy)_OFF   (does our ranking margin improve?)

Usage: PYTHONPATH=src python harness/exp_treatment.py [num_sims]
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

from hw3.strategy import choose_bid  # noqa: E402


class Ours:
    """Task-1 agent parameterised by raise_top, matching src/hw3/agent1.py behavior."""

    def __init__(self, raise_top):
        self.id = "ours"
        self._rt = raise_top

    def start_simulation(self, na, ns, ctr, v, tb, T):
        self.na, self.ns, self.ctr, self.value, self.last = na, ns, list(ctr) if ctr else [], float(v), []

    def get_bid(self, budget):
        if not self.ctr:
            return 0.0
        if not self.last:
            return self.value * 0.9
        # pass num_agents exactly as agent1.py does (choose_bid accepts it; keeps the proxy faithful)
        return choose_bid(self.value, self.ctr, self.ns, self.last, self.id, self.value,
                          num_agents=self.na, raise_top=self._rt)

    def notify_round_results(self, rr):
        self.last = rr if rr else []

    def get_id(self):
        return self.id


class _Relabel:
    def __init__(self, inner, uid):
        self._i, self.id = inner, uid

    def start_simulation(self, *a):
        return self._i.start_simulation(*a)

    def get_bid(self, *a):
        return self._i.get_bid(*a)

    def notify_round_results(self, *a):
        return self._i.notify_round_results(*a)

    def get_id(self):
        return self.id


MANY = len(sys.argv) > 2 and sys.argv[2] == "many"


def _field(raise_top):
    if not MANY:
        return [Ours(raise_top), id_dummy_1.BiddingAgent1(),
                id_dummy_2.BiddingAgent1(), id_dummy_3.BiddingAgent1()]
    field = [Ours(raise_top)]
    for c in range(4):
        field.append(_Relabel(id_dummy_1.BiddingAgent1(), f"dummy_1#{c}"))
        field.append(_Relabel(id_dummy_2.BiddingAgent1(), f"dummy_2#{c}"))
        field.append(_Relabel(id_dummy_3.BiddingAgent1(), f"dummy_3#{c}"))
    return field


def _run(seed, raise_top):
    random.seed(seed)
    agents = _field(raise_top)
    return grader.run_simulation(agents, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS, enforce_budget=False)


def _ci(xs):
    m = statistics.fmean(xs)
    ci = 1.96 * statistics.pstdev(xs) / (len(xs) ** 0.5)
    return m, ci


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    d_ours, d_best, d_rank = [], [], []
    for s in range(n):
        off = _run(s, False)
        on = _run(s, True)
        d_ours.append(on["ours"] - off["ours"])
        best_on = max(v for k, v in on.items() if k != "ours")
        best_off = max(v for k, v in off.items() if k != "ours")
        d_best.append(best_on - best_off)
        d_rank.append((on["ours"] - best_on) - (off["ours"] - best_off))
    regime = "many-agent (13)" if MANY else "4-agent"
    print(f"raise_top treatment effect, Task-1 {regime}, {n} paired seeds (ON - OFF):\n")
    print(f"  {'delta':<12} {'mean':>10} {'95% CI':>22} {'sig?':>6}")
    for lab, xs in [("ours", d_ours), ("best-rival", d_best), ("rank-margin", d_rank)]:
        m, ci = _ci(xs)
        sig = "YES" if abs(m) > ci else ""
        print(f"  {lab:<12} {m:>10.1f}   [{m - ci:>8.1f}, {m + ci:>8.1f}] {sig:>6}")


if __name__ == "__main__":
    main()
