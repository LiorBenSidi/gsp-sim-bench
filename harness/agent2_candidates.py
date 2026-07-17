"""Agent-2 headroom screen. The shipped BiddingAgent2 caps every bid at `value`, so with a big
budget it under-spends (~31% left) and sits in cheap low-CTR slots. These candidates relax that cap
(bid up to VMULT*value, and/or an end-game relax) and/or the pacing cap, to convert surplus budget
into CTR-weighted value -- IF that spending is positive-margin (bidding above value only pays when
the price you'd pay is still below your value). Each candidate plays the 3 Task-2 dummies over N
seeded sims (paired on seeds = same value draws => block-luck-robust vs the shipped baseline).
Multi-core. Reports own mean utility + mean unspent budget.

Run from the repo root. Usage: python harness/agent2_candidates.py <candidate> <N> <seed_offset>
"""
import json
import multiprocessing as mp
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fixtures"))  # server.py, CONSTANTS.py, id_dummy_*.py
sys.path.insert(0, str(ROOT / "src"))        # hw3

import CONSTANTS  # noqa: E402
import id_dummy_1  # noqa: E402
import id_dummy_2  # noqa: E402
import id_dummy_3  # noqa: E402
import server  # noqa: E402

from hw3.agent2 import BiddingAgent2  # noqa: E402
from hw3.descent import _RobustCore  # noqa: E402  (Agent 1's distribution-EU engine)
from hw3.strategy import choose_bid  # noqa: E402


class Tuned(BiddingAgent2):
    """BiddingAgent2 with a tunable value cap (VMULT), pacing cap (PACE_CAP), and an optional
    end-game value-cap relax (last EG_ROUNDS rounds, only while under-spent)."""
    PACE_CAP = 1.5
    VMULT = 1.0
    EG_ROUNDS = 0
    EG_VMULT = 1.0

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
        bid = br * min(self.PACE_CAP, max(0.0, pacing))
        vmult = self.VMULT
        if self.EG_ROUNDS and rounds_left <= self.EG_ROUNDS and budget_frac > time_frac:
            vmult = self.EG_VMULT
        bid = min(max(0.0, bid), budget, vmult * self.value)
        if bid != bid or bid in (float("inf"), float("-inf")):
            return 0.0
        return float(bid)


class _P20(Tuned):
    PACE_CAP = 2.0


class _P30(Tuned):
    PACE_CAP = 3.0


class _V110(Tuned):
    VMULT = 1.10


class _V125(Tuned):
    VMULT = 1.25


class _V150(Tuned):
    VMULT = 1.50


class _EG(Tuned):
    EG_ROUNDS = 300
    EG_VMULT = 1.5


class _EGdeep(Tuned):
    EG_ROUNDS = 600
    EG_VMULT = 2.0


class _V110P30(Tuned):
    VMULT = 1.10
    PACE_CAP = 3.0


class _V110EG(Tuned):
    VMULT = 1.10
    EG_ROUNDS = 300
    EG_VMULT = 1.5


class _DistEU(_RobustCore):
    """The lever Agent 2 never had: Agent 1's DISTRIBUTION-EU best response (accumulate each rival's
    whole bid distribution, best-respond to the joint scenario -- tames the random dummy) + Agent 2's
    budget pacing. `_RobustCore.start_simulation` ignores total_budget, so we store it ourselves."""
    CAP = 1.5

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        super().start_simulation(num_agents, num_slots, CTR_list, value, total_budget, T)
        self.total_budget = float(total_budget) if total_budget else 1.0

    def get_bid(self, current_budget_remaining):
        self._round += 1
        if not self.CTR_list or current_budget_remaining <= 0:
            return 0.0
        budget = float(current_budget_remaining)
        b, _eu, _p, _s = self._eu_bid(budget)  # distribution-EU BR (already capped to value/budget)
        if b != b or b in (float("inf"), float("-inf")):
            return 0.0
        rounds_left = max(1, self.T - self._round + 1)
        budget_frac = budget / self.total_budget if self.total_budget > 0 else 1.0
        time_frac = rounds_left / self.T
        pacing = budget_frac / time_frac if time_frac > 0 else 1.0
        bid = b * min(self.CAP, max(0.0, pacing))
        bid = min(max(0.0, bid), budget, self.value)
        if bid != bid or bid in (float("inf"), float("-inf")):
            return 0.0
        return float(bid)


class _DistEUp30(_DistEU):
    CAP = 3.0


CANDS = {
    "shipped": BiddingAgent2,          # baseline (VMULT=1.0, PACE_CAP=1.5)
    "pace20": _P20, "pace30": _P30,
    "vmult110": _V110, "vmult125": _V125, "vmult150": _V150,
    "endgame": _EG, "endgame_deep": _EGdeep,
    "vmult110_pace30": _V110P30, "vmult110_endgame": _V110EG,
    "disteu": _DistEU, "disteu_pace30": _DistEUp30,
}


def _chunk(args):
    import random
    name, seeds = args
    base = CANDS[name]

    class Rec(base):  # thin recorder: capture the last budget the server showed us (~= final unspent)
        def get_bid(self, current_budget_remaining):
            self._lastb = float(current_budget_remaining)
            return super().get_bid(current_budget_remaining)

    utils, unspent = [], []
    for s in seeds:
        random.seed(s)
        me = Rec()
        field = [me, id_dummy_1.BiddingAgent2(), id_dummy_2.BiddingAgent2(),
                 id_dummy_3.BiddingAgent2()]
        u = server.run_simulation(field, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS,
                                  enforce_budget=True)
        utils.append(u[me.get_id()])
        unspent.append(getattr(me, "_lastb", 0.0))
    return utils, unspent


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "shipped"
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    off = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    seeds = list(range(off, off + N))
    workers = os.cpu_count() or 2
    parts = [seeds[i::workers] for i in range(workers)]
    jobs = [(name, p) for p in parts if p]
    print(f"candidate={name} N={N} offset={off} workers={workers}", file=sys.stderr, flush=True)
    with mp.Pool(len(jobs)) as pool:
        res = pool.map(_chunk, jobs)
    utils = [u for r, _ in res for u in r]
    unspent = [x for _, r in res for x in r]
    print(json.dumps({"candidate": name, "n": N, "offset": off,
                      "mean_utility": statistics.fmean(utils),
                      "mean_unspent": statistics.fmean(unspent)}))


if __name__ == "__main__":
    main()
