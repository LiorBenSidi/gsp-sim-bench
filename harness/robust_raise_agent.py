"""Challenger BiddingAgent1: RobustAgent1's distribution-EU policy PLUS a conservative cost-raise.

Task 2 of the Fable-5 plan. The champion's cost-raise holds dummy1 (a constant bidder); robust's
distribution-EU wins dummy2 (the random bidder). This combines them WITHOUT the champion's latent
bug (raising against a stale estimate of a *stochastic* top). NOT shipped -- evaluated as an
exp_valueaware candidate under the ratchet. Stdlib-only, <50ms/call.

The raise fires ONLY when: our EU-optimal seat is slot 1, the current slot-0 top was DIRECTLY
observed recently AND types CONSTANT (deterministic), and bidding just under its identified true bid
neither overtakes it (r = b_top - eps < b_top, so our own slot/price are untouched) nor loses
scenario-EU beyond a tiny budget delta. Against a STOCHASTIC or UNKNOWN top it never fires -- so it
can only re-create the champion's proven zero-cost d1 suppression, never erode it, and never chase a
random top. See docs/dummy2-search-findings.md (Candidate C', the b* frontier).
"""
from collections import deque

from robust_agent import _EPS, RobustAgent1


class RobustRaiseAgent1(RobustAgent1):
    def __init__(self, delta_frac=0.0):
        super().__init__()
        self.delta_frac = float(delta_frac)   # 0.0 = raise only when scenario-EU-neutral

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        super().start_simulation(num_agents, num_slots, CTR_list, value, total_budget, T)
        self._obs_round = {}   # rid -> round of its most recent DIRECT observation (slot>=1)
        self._recent = {}      # rid -> deque(maxlen=8) of recent directly-observed bids
        self._top0 = None      # last round's slot-0 winner id
        self._raise_fires = 0  # instrumentation only; never read by strategy logic

    def notify_round_results(self, round_results):
        super().notify_round_results(round_results)   # updates self._stats
        rows = [r for r in (round_results or []) if isinstance(r, (tuple, list)) and len(r) == 3]
        price_by_slot = {slot: float(price) for (_w, slot, price) in rows}
        for (winner, slot, _price) in rows:
            if slot >= 1 and winner != self.id:
                bid = price_by_slot.get(slot - 1, 0.0)
                self._obs_round[winner] = self._round
                self._recent.setdefault(winner, deque(maxlen=8)).append(bid)
        self._top0 = next((w for (w, s, _p) in rows if s == 0), None)

    def _rival_type(self, rid):
        s = self._stats.get(rid)
        if not s:
            return "UNKNOWN"
        n, tot, sq, _mx, _last = s
        if n < 8:
            return "UNKNOWN"                       # not enough evidence -> never raise against it
        mean = tot / n
        sd = (sq / n - mean * mean) ** 0.5 if (sq / n - mean * mean) > 0 else 0.0
        tol = max(0.005 * mean, 1e-6)              # absolute floor guards mean ~ 0
        rec = self._recent.get(rid)
        spread = (max(rec) - min(rec)) if rec else 0.0
        if sd <= tol and spread <= tol:
            return "CONSTANT"                      # e.g. dummy1 (exact 0.85*v)
        if mean > 1e-9 and sd / mean >= 0.08:
            return "STOCHASTIC"                    # e.g. dummy2 (U(0.4,1)*v)
        return "UNKNOWN"                           # gray zone / reactive -> never raise against it

    def get_bid(self, budget):
        self._round += 1
        b_eu, eu_val, points, scenarios = self._eu_bid(budget)
        if scenarios is None:                      # cold open / no history -> parent behavior
            if b_eu != b_eu or b_eu in (float("inf"), float("-inf")):
                return 0.0
            return float(min(max(0.0, b_eu), budget, self.value))

        bid = b_eu
        if self._round > 10:                       # warm-up fence
            # (a) our EU-optimal seat is slot 1 (exactly one rival's central point above b_eu)
            central = sorted((p[len(p) // 2] for p in points), reverse=True)
            above = sum(1 for r in central if r > b_eu)
            t0 = self._top0
            if (above == 1 and t0 and t0 != self.id and self._rival_type(t0) == "CONSTANT"
                    and (self._round - self._obs_round.get(t0, -10**9)) <= 100):
                s = self._stats.get(t0)
                if s:
                    b_top = s[4]                                       # its exact last bid
                    r = min(self.value, max(0.0, b_top - _EPS))        # just under -> NO overtake
                    if r > b_eu:
                        rr = min(max(0.0, r), budget, self.value)
                        eu_r = sum(w * self._util(rr, vec) for vec, w in scenarios)
                        ctr0 = self.CTR_list[0] if self.CTR_list else 0.0
                        delta = self.delta_frac * self.value * ctr0
                        if eu_r >= eu_val - delta:                     # (c) EU guard
                            bid = rr
                            self._raise_fires += 1

        if bid != bid or bid in (float("inf"), float("-inf")):
            return 0.0
        return float(min(max(0.0, bid), budget, self.value))
