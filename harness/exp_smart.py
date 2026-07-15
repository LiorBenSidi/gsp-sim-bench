"""Refinement test: 'smart' cost-raise that identifies the slot-0 winner's TRUE bid from
cross-round history and bids just under it -- forcing them to pay ~their full bid for slot 0
WITHOUT us overtaking -- vs the current self-referential 'raise_top' (which overtakes) and the
plain 'off' baseline.

Identification: whenever an agent sits in slot k>=1, the price paid for slot k-1 equals that
agent's exact bid. So each round we learn the exact bid of every non-top agent; we cache it per
id. The slot-0 winner's current bid is hidden, but its cached last-seen bid (exact & constant
for dummy1) lets us bid just under it.

Reports, per seed (CRN-paired), for each mode: ours, best-rival, rank-margin. Plus the paired
treatment smart-vs-raise_top (does smart cut our self-cost while keeping the rank gain?).

Usage: PYTHONPATH=src python harness/exp_smart.py [num_sims]
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

_EPS = 1e-3


def _best_slot(value, ctr, rivals, ns):
    n = min(ns, len(ctr))
    bk, bu = None, -1.0
    for k in range(n):
        price = rivals[k] if k < len(rivals) else 0.0
        if price > value:
            continue
        u = (value - price) * ctr[k]
        if u > bu:
            bk, bu = k, u
    return bk


class Proxy:
    def __init__(self, mode):
        self.mode, self.id = mode, "ours"

    def start_simulation(self, na, ns, ctr, v, tb, T):
        self.ns, self.ctr, self.value = ns, list(ctr) if ctr else [], float(v)
        self.last = []
        self.bid_by_id = {}   # agent_id -> last exact bid observed (from a round it wasn't top)
        self.top0 = None      # id of last round's slot-0 winner

    def notify_round_results(self, rr):
        rr = rr or []
        price_by_slot = {s: float(p) for (_w, s, p) in rr}
        winner_by_slot = {s: w for (w, s, _p) in rr}
        for s, w in winner_by_slot.items():
            if s >= 1:  # this agent's exact bid == price paid for the slot directly above it
                self.bid_by_id[w] = price_by_slot.get(s - 1, 0.0)
        self.top0 = winner_by_slot.get(0)
        self.last = rr

    def _rivals(self):
        price_by_slot = {s: float(p) for (_w, s, p) in self.last}
        winner_by_slot = {s: w for (w, s, _p) in self.last}
        rivals = []
        for k in range(self.ns):
            if k not in winner_by_slot:
                continue
            occ = (price_by_slot.get(0, 0.0) * 1.1 + 1.0) if k == 0 else price_by_slot.get(k - 1, 0.0)
            if winner_by_slot[k] != self.id:
                rivals.append(occ)
        return sorted(rivals, reverse=True)

    def get_bid(self, budget):
        if not self.ctr or self.value <= 0:
            return 0.0
        if not self.last:
            return self.value * 0.9
        rivals = self._rivals()
        k = _best_slot(self.value, self.ctr, rivals, self.ns)
        if k is None or k >= len(rivals):
            return 0.0
        floor = min(self.value, rivals[k] + _EPS)
        if k == 0:
            return floor
        if self.mode == "off" or k != 1:
            return floor
        if self.mode == "raise_top":
            return max(floor, min(self.value, rivals[0]))          # self-referential -> overtakes
        # smart: bid just under the slot-0 winner's TRUE (cached) bid -> raise their cost, no overtake
        true_top = self.bid_by_id.get(self.top0)
        if true_top is None:
            return max(floor, min(self.value, rivals[0]))          # unseen yet -> fall back
        raised = min(self.value, max(0.0, true_top - _EPS))
        return max(floor, raised)

    def get_id(self):
        return self.id


def run(mode, seed):
    random.seed(seed)
    agents = [Proxy(mode), id_dummy_1.BiddingAgent1(),
              id_dummy_2.BiddingAgent1(), id_dummy_3.BiddingAgent1()]
    return grader.run_simulation(agents, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS, enforce_budget=False)


def _ci(xs):
    m = statistics.fmean(xs)
    return m, 1.96 * statistics.pstdev(xs) / (len(xs) ** 0.5)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    modes = ["off", "raise_top", "smart"]
    ours = {m: [] for m in modes}
    rank = {m: [] for m in modes}
    d_smart_ours, d_smart_rank = [], []   # smart - raise_top, paired
    for s in range(n):
        res = {m: run(m, s) for m in modes}
        for m in modes:
            u = res[m]
            best = max(v for k, v in u.items() if k != "ours")
            ours[m].append(u["ours"])
            rank[m].append(u["ours"] - best)
        d_smart_ours.append(ours["smart"][-1] - ours["raise_top"][-1])
        d_smart_rank.append(rank["smart"][-1] - rank["raise_top"][-1])
    print(f"Task-1 4-agent, {n} CRN sims. absolute means (high variance) + paired smart-vs-raise_top:\n")
    print(f"  {'mode':<10} {'ours':>10} {'rank-margin':>13}")
    for m in modes:
        print(f"  {m:<10} {statistics.fmean(ours[m]):>10.1f} {statistics.fmean(rank[m]):>13.1f}")
    mo, co = _ci(d_smart_ours)
    mr, cr = _ci(d_smart_rank)
    print("\n  PAIRED (smart - raise_top):")
    print(f"    d_ours       {mo:>9.1f}  [{mo-co:>8.1f}, {mo+co:>8.1f}] {'sig' if abs(mo)>co else ''}")
    print(f"    d_rank-margin{mr:>9.1f}  [{mr-cr:>8.1f}, {mr+cr:>8.1f}] {'sig' if abs(mr)>cr else ''}")


if __name__ == "__main__":
    main()
