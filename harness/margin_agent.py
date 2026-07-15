"""Margin-objective challengers (Options A/B/C) for the beat-all-3 search. NOT shipped.

Why these exist: the conservative-raise arm (rraise0) proved a NO-OP -- its cost-raise needs our
EU-optimal seat to be slot 1 (below the top), but the robust EU policy is aggressive and usually
takes slot 0 itself, so the raise gate never opened (_raise_fires == 0 over 60k rounds). Suppression
has to come from the OBJECTIVE (which seat to take and at what bid), not from a bolt-on rule.

- Option A  MarginAgent1: maximize J(b) = E[own utility] + w * E[rival spend]. Making rivals pay
  more with their values fixed lowers THEIR utility -> widens our margin. Value-agnostic (works vs
  unseen agents too). This naturally re-creates the champion's cost-raise (bid just under a rival
  you sit below so IT pays your bid) whenever that is margin-positive -- with no seat precondition.
- Option B  DescentAgent1(MarginAgent1): surgical. When the EU seat is slot 0 directly above a
  CONSTANT-typed rival, evaluate dropping just below it and take the descent iff the expected
  margin vs THAT rival improves (uses v-hat = bid/shade for the typed rival; shade=0.85 = dummy1's
  public rule -- typed-exploit is legitimate for the 40-pt regime).
- Option C  BindingMarginAgent1(MarginAgent1): A, but the suppression term weights each rival by
  how BINDING it is (softmax of the running per-round margin estimate vs that rival) -- aim the
  suppression at the dummy we are closest to losing.

All stdlib-only, deterministic (no RNG -> CRN-safe), O(1) memory per rival. Typing logic mirrors
robust_raise_agent.RobustRaiseAgent1 (kept duplicated deliberately -- these are independent research
arms; a shared mixin would couple their evolution).
"""
import math
from collections import deque
from itertools import product as _iproduct

from robust_agent import _EPS, _MAX_RIVALS_ENUM, _MAX_SCENARIOS, RobustAgent1


def gsp_alloc(my_bid, rivals_sorted, value, ctr_list, num_slots):
    """Exact GSP outcome for our bid vs a concrete rival scenario.

    rivals_sorted: list of (rid, bid), bid descending. Ties: we win (rival counted above only if
    strictly greater), matching RobustAgent1._util. Returns (our_util, [(rid, slot, price), ...])
    for every seated rival. Slot j pays the bid of the next occupant below; the last pays 0.
    """
    n = min(num_slots, len(ctr_list))
    k = 0
    for _rid, b in rivals_sorted:
        if b > my_bid:
            k += 1
        else:
            break
    our_util = 0.0
    if k < n:
        our_price = rivals_sorted[k][1] if k < len(rivals_sorted) else 0.0
        our_util = (value - our_price) * ctr_list[k]
    seated = []
    for i, (rid, _b) in enumerate(rivals_sorted):
        slot = i if i < k else i + 1
        if slot >= n:
            break
        if i < k:                                    # rival above us
            price = rivals_sorted[i + 1][1] if i + 1 < k else my_bid
        else:                                        # rival below us
            price = rivals_sorted[i + 1][1] if i + 1 < len(rivals_sorted) else 0.0
        seated.append((rid, slot, price))
    return our_util, seated


class MarginAgent1(RobustAgent1):
    """Option A: distribution-EU + value-agnostic suppression (rival spend) in the objective."""

    WARMUP = 10

    def __init__(self, w=1.0):
        super().__init__()
        self.w = float(w)

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        super().start_simulation(num_agents, num_slots, CTR_list, value, total_budget, T)
        self._obs_round = {}
        self._recent = {}
        self._suppress_picks = 0     # diagnostics: rounds where w changed the chosen bid

    def notify_round_results(self, round_results):
        super().notify_round_results(round_results)
        rows = [r for r in (round_results or []) if isinstance(r, (tuple, list)) and len(r) == 3]
        price_by_slot = {slot: float(price) for (_w, slot, price) in rows}
        for (winner, slot, _price) in rows:
            if slot >= 1 and winner != self.id:
                bid = price_by_slot.get(slot - 1, 0.0)
                self._obs_round[winner] = self._round
                self._recent.setdefault(winner, deque(maxlen=8)).append(bid)

    # --- typing (mirrors RobustRaiseAgent1; see module docstring for why it's duplicated) ---
    def _rival_type(self, rid):
        s = self._stats.get(rid)
        if not s:
            return "UNKNOWN"
        n, tot, sq, _mx, _last = s
        if n < 8:
            return "UNKNOWN"
        mean = tot / n
        var = sq / n - mean * mean
        sd = var ** 0.5 if var > 0 else 0.0
        tol = max(0.005 * mean, 1e-6)
        rec = self._recent.get(rid)
        spread = (max(rec) - min(rec)) if rec else 0.0
        if sd <= tol and spread <= tol:
            return "CONSTANT"
        if mean > 1e-9 and sd / mean >= 0.08:
            return "STOCHASTIC"
        return "UNKNOWN"

    # --- identity-aware points / scenarios ---
    def _points_ids(self):
        # 3 points/rival (mean, mean +- sd) -> at most 3^R scenarios. Dropping the max/last points
        # (5 -> 3) is a ~5x compute cut with the distribution still captured; heavy per-round work
        # (a GSP alloc per scenario per candidate) makes this the load-bearing speed lever.
        out = []
        for rid, s in self._stats.items():
            c, tot, sq, _mx, _last = s
            if c <= 0:
                continue
            mean = tot / c
            var = sq / c - mean * mean
            sd = var ** 0.5 if var > 0 else 0.0
            pts = sorted({mean, max(0.0, mean - sd), mean + sd}, reverse=True)
            out.append((rid, pts))
        return out

    def _scen_ids(self, pids):
        """Scenarios as pre-sorted [(rid,bid) desc] lists + weight; capped like the parent."""
        total = 1
        for _rid, p in pids:
            total *= max(1, len(p))
        if len(pids) > _MAX_RIVALS_ENUM or total > _MAX_SCENARIOS:
            vec = sorted(((rid, p[len(p) // 2]) for rid, p in pids),
                         key=lambda t: t[1], reverse=True)
            return [(vec, 1.0)]
        wt = 1.0 / total
        rids = [rid for rid, _p in pids]
        out = []
        for combo in _iproduct(*(p for _rid, p in pids)):
            vec = sorted(zip(rids, combo, strict=True), key=lambda t: t[1], reverse=True)
            out.append((vec, wt))
        return out

    def _suppr(self, seated):
        """Suppression credit for one scenario outcome. Option A: total rival spend."""
        return sum(price * self.CTR_list[slot] for _rid, slot, price in seated)

    def _candidates(self, pids, budget):
        cands = {0.0, self.value}
        for f in (0.25, 0.5, 0.7, 0.85, 0.95):
            cands.add(f * self.value)
        for _rid, p in pids:
            c0 = p[len(p) // 2]
            if 0.0 < c0 < self.value:
                cands.add(min(self.value, c0 + _EPS))   # sit just above (capture its seat)
                cands.add(max(0.0, c0 - _EPS))          # sit just below (it pays OUR bid)
        return cands

    def get_bid(self, budget):
        self._round += 1
        if self._round <= self.WARMUP or not self._stats:
            b, _eu, _p, _s = self._eu_bid(budget)      # parent policy during warm-up
            if b != b or b in (float("inf"), float("-inf")):
                return 0.0
            return float(min(max(0.0, b), budget, self.value))
        if not self.CTR_list or self.value <= 0:
            return 0.0
        pids = self._points_ids()
        if not pids:
            return float(min(self.value * 0.9, budget))
        scens = self._scen_ids(pids)
        best_b, best_j, best_b_eu, best_eu = 0.0, -1e30, 0.0, -1e30
        for b in self._candidates(pids, budget):
            b = min(max(0.0, b), budget, self.value)
            j = eu = 0.0
            for vec, wt in scens:
                u, seated = gsp_alloc(b, vec, self.value, self.CTR_list, self.num_slots)
                eu += wt * u
                j += wt * (u + self.w * self._suppr(seated))
            if j > best_j:
                best_j, best_b = j, b
            if eu > best_eu:
                best_eu, best_b_eu = eu, b
        if best_b != best_b_eu:
            self._suppress_picks += 1
        if best_b != best_b or best_b in (float("inf"), float("-inf")):
            return 0.0
        return float(min(max(0.0, best_b), budget, self.value))


class DescentAgent1(MarginAgent1):
    """Option B: pure-EU seat choice, except one surgical override -- if the EU seat is slot 0
    directly above a CONSTANT rival, descend to just below it iff the margin vs THAT rival improves."""

    def __init__(self, shade=0.85):
        super().__init__(w=0.0)        # objective stays pure EU; the descent is the only deviation
        self.shade = float(shade)
        self._descents = 0

    def get_bid(self, budget):
        self._round += 1
        b_eu, _eu, _pts, _sc = self._eu_bid(budget)
        if b_eu != b_eu or b_eu in (float("inf"), float("-inf")):
            return 0.0
        bid = min(max(0.0, b_eu), budget, self.value)
        if self._round > self.WARMUP and self._stats and self.CTR_list:
            pids = self._points_ids()
            if pids:
                scens = self._scen_ids(pids)
                central = sorted(((rid, p[len(p) // 2]) for rid, p in pids),
                                 key=lambda t: t[1], reverse=True)
                above = [t for t in central if t[1] > bid]
                below = [t for t in central if t[1] <= bid]
                if not above and below:                       # EU seat = slot 0
                    top_rid, top_bid = below[0]               # rival directly beneath us
                    if (self._rival_type(top_rid) == "CONSTANT" and top_bid > 0
                            and (self._round - self._obs_round.get(top_rid, -10**9)) <= 100):
                        vhat = self._stats[top_rid][4] / self.shade
                        r = max(0.0, top_bid - _EPS)
                        m_stay = m_desc = 0.0
                        for vec, wt in scens:
                            u_s, seated_s = gsp_alloc(bid, vec, self.value, self.CTR_list, self.num_slots)
                            u_d, seated_d = gsp_alloc(r, vec, self.value, self.CTR_list, self.num_slots)
                            m_stay += wt * (u_s - self._rival_util(top_rid, seated_s, vhat))
                            m_desc += wt * (u_d - self._rival_util(top_rid, seated_d, vhat))
                        if m_desc > m_stay:
                            bid = min(max(0.0, r), budget, self.value)
                            self._descents += 1
        if bid != bid or bid in (float("inf"), float("-inf")):
            return 0.0
        return float(bid)

    def _rival_util(self, rid, seated, vhat):
        for srid, slot, price in seated:
            if srid == rid:
                return (vhat - price) * self.CTR_list[slot]
        return 0.0


class BindingMarginAgent1(MarginAgent1):
    """Option C: A's objective, but suppression aimed at the rival we are closest to losing to
    (softmax weights over running per-round margin estimates)."""

    TAU = 5.0   # per-round margin scale for the softmax

    def __init__(self, w=1.0):
        super().__init__(w=w)

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        super().start_simulation(num_agents, num_slots, CTR_list, value, total_budget, T)
        self._my_cum = 0.0
        self._riv_cum = {}

    def notify_round_results(self, round_results):
        super().notify_round_results(round_results)
        rows = [r for r in (round_results or []) if isinstance(r, (tuple, list)) and len(r) == 3]
        for (winner, slot, price) in rows:
            if slot >= len(self.CTR_list):
                continue
            if winner == self.id:
                self._my_cum += (self.value - float(price)) * self.CTR_list[slot]
            else:
                vhat = self._vhat(winner)
                if vhat is not None:
                    self._riv_cum[winner] = (self._riv_cum.get(winner, 0.0)
                                             + (vhat - float(price)) * self.CTR_list[slot])

    def _vhat(self, rid):
        s = self._stats.get(rid)
        if not s:
            return None
        if self._rival_type(rid) == "CONSTANT":
            return s[4] / 0.85           # typed-exploit: dummy1's public rule
        return s[3]                      # max observed bid = lower bound on its value

    def _suppr(self, seated):
        if not seated:
            return 0.0
        rounds = max(1, self._round)
        ws = {}
        for rid, _slot, _price in seated:
            m_rate = (self._my_cum - self._riv_cum.get(rid, 0.0)) / rounds
            ws[rid] = math.exp(max(-50.0, min(50.0, -m_rate / self.TAU)))
        z = sum(ws.values()) or 1.0
        scale = len(seated)              # keep the total on Option A's scale (avg weight = 1)
        return scale * sum((ws[rid] / z) * price * self.CTR_list[slot]
                           for rid, slot, price in seated)
