"""HW3 -- Electronic Commerce Models (00960211). GSP ad-auction bidding bot.
BiddingAgent1 (no budget) + BiddingAgent2 (budget). Submitted by 207490913, 318931672."""
import itertools
from collections import deque
from itertools import product as _iproduct
# ===================== Shared GSP bidding logic =====================
_EPS = 0.001

def reconstruct_rivals(last_results, my_id, num_slots):
    """Estimate rivals' bids from the previous round's (winner_id, slot, price) tuples.

    The occupant of slot k (k>=1) bid == the price paid for slot k-1; the top occupant's
    bid is hidden, so estimate it just above the slot-0 price. Exclude ourselves.
    Returns rival bids sorted descending.
    """
    price_by_slot = {slot: float(price) for _w, slot, price in last_results}
    winner_by_slot = {slot: w for w, slot, _p in last_results}
    rivals = []
    for k in range(num_slots):
        if k not in winner_by_slot:
            continue
        if k == 0:
            occ_bid = price_by_slot.get(0, 0.0) * 1.1 + 1.0
        else:
            occ_bid = price_by_slot.get(k - 1, 0.0)
        if winner_by_slot[k] != my_id:
            rivals.append(occ_bid)
    return sorted(rivals, reverse=True)

def best_response(value, ctr_list, rivals, budget, num_slots):
    """Pick the profit-maximizing reachable slot and the minimum bid that SECURES it.

    rivals is sorted descending. To land in slot k you need exactly k rivals above you, so
    bid just above rivals[k] (the rival you displace) -- you then pay rivals[k]. When there
    are fewer rivals than k (the free bottom slot), bid 0: you sit last and pay 0. For each k
    utility = (value - price)*CTR[k]; skip negative-utility slots (price > value). This
    compares every paid slot against the free floor honestly and never over-bids into a higher
    (more expensive) slot than the one chosen. Always returns a finite bid in [0, budget].
    """
    if not ctr_list or value <= 0:
        return 0.0
    n = min(num_slots, len(ctr_list))
    best_bid, best_u = (0.0, -1.0)
    for k in range(n):
        price = rivals[k] if k < len(rivals) else 0.0
        if price > value:
            continue
        u = (value - price) * ctr_list[k]
        if u <= best_u:
            continue
        if k < len(rivals):
            bid = min(value, rivals[k] + _EPS)
        else:
            bid = 0.0
        best_u, best_bid = (u, min(max(0.0, bid), budget))
    if best_u < 0:
        return 0.0
    return float(best_bid)

def choose_bid(value, ctr_list, num_slots, last_results, my_id, budget):
    """Best-respond to the reconstructed rival bids; guaranteed a finite float in [0, budget]."""
    rivals = reconstruct_rivals(last_results, my_id, num_slots)
    bid = best_response(value, ctr_list, rivals, budget, num_slots)
    if bid != bid or bid in (float('inf'), float('-inf')):
        return 0.0
    return float(bid)


# ===================== Distribution-EU + targeted descent (BiddingAgent1's policy engine) =====================
_EPS = 0.001
_MAX_SCENARIOS = 256
_MAX_RIVALS_ENUM = 6

class _RobustCore:
    """Distribution-EU best response. Accumulate each rival's reconstructed-bid distribution and
    best-respond to the joint product of a few plausible-bid scenarios per rival."""

    def __init__(self):
        self.id = 'ours'
        self.value = 0.0
        self.CTR_list = []
        self.num_slots = 0
        self.num_agents = 0
        self.T = 1
        self._round = 0
        self._last = []
        self._stats = {}

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        self.num_agents = num_agents
        self.num_slots = num_slots
        self.CTR_list = list(CTR_list) if CTR_list else []
        self.value = float(value)
        self.T = int(T) if T else 1
        self._round = 0
        self._last = []
        self._stats = {}

    def get_id(self):
        return self.id

    def _util(self, my_bid, rivals_desc):
        k = 0
        for r in rivals_desc:
            if r > my_bid:
                k += 1
            else:
                break
        if k >= len(self.CTR_list):
            return 0.0
        price = rivals_desc[k] if k < len(rivals_desc) else 0.0
        return (self.value - price) * self.CTR_list[k]

    def _rival_points(self):
        """Per rival, a short list of plausible bids from its accumulated stats."""
        pts = []
        for _rid, s in self._stats.items():
            c, tot, sq, mx, last = s
            if c <= 0:
                continue
            mean = tot / c
            var = sq / c - mean * mean
            sd = var ** 0.5 if var > 0 else 0.0
            cand = {mean, max(0.0, mean - sd), mean + sd, mx, last}
            pts.append(sorted(cand, reverse=True))
        return pts

    def _scenarios(self, points):
        """List of (rival_vector_desc, weight). Product of per-rival points, capped; else mean."""
        sizes = [len(p) for p in points]
        total = 1
        for n in sizes:
            total *= max(1, n)
        if len(points) > _MAX_RIVALS_ENUM or total > _MAX_SCENARIOS:
            mean_vec = sorted((p[len(p) // 2] for p in points), reverse=True)
            return [(mean_vec, 1.0)]
        w = 1.0 / total if total else 1.0
        out = []
        for combo in itertools.product(*points):
            out.append((sorted(combo, reverse=True), w))
        return out

    def _eu_bid(self, budget):
        """Core distribution-EU policy. Returns (best_b, best_eu, points, scenarios). On the
        cold-open / no-history paths returns (value-anchored bid, None, None, None). Subclasses
        reuse this and then adjust best_b -- so the pure-EU behavior stays byte-identical."""
        if not self.CTR_list or self.value <= 0:
            return (0.0, None, None, None)
        if not self._stats:
            return (float(min(self.value * 0.9, budget)), None, None, None)
        points = self._rival_points()
        if not points:
            return (float(min(self.value * 0.9, budget)), None, None, None)
        scenarios = self._scenarios(points)
        cands = {0.0, self.value}
        for f in (0.25, 0.5, 0.7, 0.85, 0.95):
            cands.add(f * self.value)
        for p in points:
            central = p[len(p) // 2]
            if 0.0 < central < self.value:
                cands.add(min(self.value, central + _EPS))
        best_b, best_eu = (0.0, -1e+30)
        for b in cands:
            b = min(max(0.0, b), budget, self.value)
            eu = 0.0
            for vec, w in scenarios:
                eu += w * self._util(b, vec)
            if eu > best_eu:
                best_eu, best_b = (eu, b)
        return (best_b, best_eu, points, scenarios)

    def get_bid(self, budget):
        self._round += 1
        best_b, _eu, _pts, _sc = self._eu_bid(budget)
        if best_b != best_b or best_b in (float('inf'), float('-inf')):
            return 0.0
        return float(min(max(0.0, best_b), budget, self.value))

    def notify_round_results(self, round_results):
        self._last = round_results if round_results else []
        rows = [r for r in self._last if isinstance(r, (tuple, list)) and len(r) == 3]
        price_by_slot = {slot: float(price) for _w, slot, price in rows}
        for winner, slot, _price in rows:
            if slot >= 1 and winner != self.id:
                bid = price_by_slot.get(slot - 1, 0.0)
                s = self._stats.get(winner)
                if s is None:
                    self._stats[winner] = [1, bid, bid * bid, bid, bid]
                else:
                    s[0] += 1
                    s[1] += bid
                    s[2] += bid * bid
                    s[3] = max(s[3], bid)
                    s[4] = bid

def gsp_alloc(my_bid, rivals_sorted, value, ctr_list, num_slots):
    """Exact GSP outcome for our bid vs a concrete rival scenario.

    rivals_sorted: list of (rid, bid), bid descending. Ties: we win (rival counted above only if
    strictly greater), matching _RobustCore._util. Returns (our_util, [(rid, slot, price), ...])
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
        if i < k:
            price = rivals_sorted[i + 1][1] if i + 1 < k else my_bid
        else:
            price = rivals_sorted[i + 1][1] if i + 1 < len(rivals_sorted) else 0.0
        seated.append((rid, slot, price))
    return (our_util, seated)

class _MarginCore(_RobustCore):
    """Distribution-EU + value-agnostic suppression (rival spend) in the objective, plus rival
    typing and an identity-aware allocator. w=0 recovers pure EU (what DescentAgent1 uses)."""
    WARMUP = 10

    def __init__(self, w=1.0):
        super().__init__()
        self.w = float(w)

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        super().start_simulation(num_agents, num_slots, CTR_list, value, total_budget, T)
        self._obs_round = {}
        self._recent = {}
        self._suppress_picks = 0

    def notify_round_results(self, round_results):
        super().notify_round_results(round_results)
        rows = [r for r in round_results or [] if isinstance(r, (tuple, list)) and len(r) == 3]
        price_by_slot = {slot: float(price) for _w, slot, price in rows}
        for winner, slot, _price in rows:
            if slot >= 1 and winner != self.id:
                bid = price_by_slot.get(slot - 1, 0.0)
                self._obs_round[winner] = self._round
                self._recent.setdefault(winner, deque(maxlen=8)).append(bid)

    def _rival_type(self, rid):
        s = self._stats.get(rid)
        if not s:
            return 'UNKNOWN'
        n, tot, sq, _mx, _last = s
        if n < 8:
            return 'UNKNOWN'
        mean = tot / n
        var = sq / n - mean * mean
        sd = var ** 0.5 if var > 0 else 0.0
        tol = max(0.005 * mean, 1e-06)
        rec = self._recent.get(rid)
        spread = max(rec) - min(rec) if rec else 0.0
        if sd <= tol and spread <= tol:
            return 'CONSTANT'
        if mean > 1e-09 and sd / mean >= 0.08:
            return 'STOCHASTIC'
        return 'UNKNOWN'

    def _points_ids(self):
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
            vec = sorted(((rid, p[len(p) // 2]) for rid, p in pids), key=lambda t: t[1], reverse=True)
            return [(vec, 1.0)]
        wt = 1.0 / total
        rids = [rid for rid, _p in pids]
        out = []
        for combo in _iproduct(*(p for _rid, p in pids)):
            vec = sorted(zip(rids, combo), key=lambda t: t[1], reverse=True)
            out.append((vec, wt))
        return out

    def _suppr(self, seated):
        """Suppression credit for one scenario outcome: total rival spend."""
        return sum((price * self.CTR_list[slot] for _rid, slot, price in seated))

    def _candidates(self, pids, budget):
        cands = {0.0, self.value}
        for f in (0.25, 0.5, 0.7, 0.85, 0.95):
            cands.add(f * self.value)
        for _rid, p in pids:
            c0 = p[len(p) // 2]
            if 0.0 < c0 < self.value:
                cands.add(min(self.value, c0 + _EPS))
                cands.add(max(0.0, c0 - _EPS))
        return cands

    def get_bid(self, budget):
        self._round += 1
        if self._round <= self.WARMUP or not self._stats:
            b, _eu, _p, _s = self._eu_bid(budget)
            if b != b or b in (float('inf'), float('-inf')):
                return 0.0
            return float(min(max(0.0, b), budget, self.value))
        if not self.CTR_list or self.value <= 0:
            return 0.0
        pids = self._points_ids()
        if not pids:
            return float(min(self.value * 0.9, budget))
        scens = self._scen_ids(pids)
        best_b, best_j, best_b_eu, best_eu = (0.0, -1e+30, 0.0, -1e+30)
        for b in self._candidates(pids, budget):
            b = min(max(0.0, b), budget, self.value)
            j = eu = 0.0
            for vec, wt in scens:
                u, seated = gsp_alloc(b, vec, self.value, self.CTR_list, self.num_slots)
                eu += wt * u
                j += wt * (u + self.w * self._suppr(seated))
            if j > best_j:
                best_j, best_b = (j, b)
            if eu > best_eu:
                best_eu, best_b_eu = (eu, b)
        if best_b != best_b_eu:
            self._suppress_picks += 1
        if best_b != best_b or best_b in (float('inf'), float('-inf')):
            return 0.0
        return float(min(max(0.0, best_b), budget, self.value))

class DescentAgent1(_MarginCore):
    """Pure-EU seat choice, except one surgical override -- if the EU seat is the top slot directly
    above a CONSTANT rival, descend to just below it iff the expected margin vs THAT rival improves
    (uses v-hat = last-bid/shade for the typed rival; shade=0.85 = a fixed-fraction rule)."""

    def __init__(self, shade=0.85):
        super().__init__(w=0.0)
        self.shade = float(shade)
        self._descents = 0

    def get_bid(self, budget):
        self._round += 1
        b_eu, _eu, _pts, _sc = self._eu_bid(budget)
        if b_eu != b_eu or b_eu in (float('inf'), float('-inf')):
            return 0.0
        bid = min(max(0.0, b_eu), budget, self.value)
        if self._round > self.WARMUP and self._stats and self.CTR_list:
            pids = self._points_ids()
            if pids:
                scens = self._scen_ids(pids)
                central = sorted(((rid, p[len(p) // 2]) for rid, p in pids), key=lambda t: t[1], reverse=True)
                above = [t for t in central if t[1] > bid]
                below = [t for t in central if t[1] <= bid]
                if not above and below:
                    top_rid, top_bid = below[0]
                    if self._rival_type(top_rid) == 'CONSTANT' and top_bid > 0 and (self._round - self._obs_round.get(top_rid, -10 ** 9) <= 100):
                        vhat = self._stats[top_rid][4] / self.shade
                        r = max(0.0, top_bid - _EPS)
                        m_stay = m_desc = 0.0
                        ctr, ns = (self.CTR_list, self.num_slots)
                        for vec, wt in scens:
                            u_s, seated_s = gsp_alloc(bid, vec, self.value, ctr, ns)
                            u_d, seated_d = gsp_alloc(r, vec, self.value, ctr, ns)
                            m_stay += wt * (u_s - self._rival_util(top_rid, seated_s, vhat))
                            m_desc += wt * (u_d - self._rival_util(top_rid, seated_d, vhat))
                        if m_desc > m_stay:
                            bid = min(max(0.0, r), budget, self.value)
                            self._descents += 1
        if bid != bid or bid in (float('inf'), float('-inf')):
            return 0.0
        return float(bid)

    def _rival_util(self, rid, seated, vhat):
        for srid, slot, price in seated:
            if srid == rid:
                return (vhat - price) * self.CTR_list[slot]
        return 0.0

class DescentRaiseAgent1(DescentAgent1):
    """Descent's descend (when our EU seat is slot 0 directly ABOVE a constant rival) PLUS a
    cost-raise (when our EU seat is slot 1 directly BELOW a constant rival). The cost-raise is a
    d2-neutral d1-suppression lever: in GSP the slot-0 winner pays the bid of whoever sits directly
    below it (us), so bidding just under the constant top's identified bid makes it pay ~its full
    bid for slot 0 while OUR own price -- set by the agent below US -- and our seat are unchanged.
    We keep slot 1 (no overtake, r < b_top), our utility is untouched, and a rival seated below us
    is unaffected. This recovers the constant rival's (dummy1's) margin without the seat sacrifice
    that a descend would cost, so it does not feed the d1<->d2 tradeoff pure suppression hits."""

    def get_bid(self, budget):
        self._round += 1
        b_eu, _eu, _pts, _sc = self._eu_bid(budget)
        if b_eu != b_eu or b_eu in (float('inf'), float('-inf')):
            return 0.0
        bid = min(max(0.0, b_eu), budget, self.value)
        if self._round > self.WARMUP and self._stats and self.CTR_list:
            pids = self._points_ids()
            if pids:
                scens = self._scen_ids(pids)
                central = sorted(((rid, p[len(p) // 2]) for rid, p in pids), key=lambda t: t[1], reverse=True)
                above = [t for t in central if t[1] > bid]
                below = [t for t in central if t[1] <= bid]
                if not above and below:
                    top_rid, top_bid = below[0]
                    if self._rival_type(top_rid) == 'CONSTANT' and top_bid > 0 and (self._round - self._obs_round.get(top_rid, -10 ** 9) <= 100):
                        vhat = self._stats[top_rid][4] / self.shade
                        r = max(0.0, top_bid - _EPS)
                        ctr, ns = (self.CTR_list, self.num_slots)
                        m_stay = m_desc = 0.0
                        for vec, wt in scens:
                            u_s, seated_s = gsp_alloc(bid, vec, self.value, ctr, ns)
                            u_d, seated_d = gsp_alloc(r, vec, self.value, ctr, ns)
                            m_stay += wt * (u_s - self._rival_util(top_rid, seated_s, vhat))
                            m_desc += wt * (u_d - self._rival_util(top_rid, seated_d, vhat))
                        if m_desc > m_stay:
                            bid = min(max(0.0, r), budget, self.value)
                            self._descents += 1
                elif len(above) == 1:
                    top_rid, _top_central = above[0]
                    if self._rival_type(top_rid) == 'CONSTANT' and self._round - self._obs_round.get(top_rid, -10 ** 9) <= 100:
                        b_top = self._stats[top_rid][4]
                        r = min(self.value, max(0.0, b_top - _EPS))
                        if r > bid:
                            bid = min(max(0.0, r), budget, self.value)
                            self._raises = getattr(self, '_raises', 0) + 1
        if bid != bid or bid in (float('inf'), float('-inf')):
            return 0.0
        return float(bid)

class StochRaiseAgent1(DescentRaiseAgent1):
    """DescentRaiseAgent1 (d1-descend + d1-cost-raise, preserved) PLUS a slot-1 STOCHASTIC-rival
    cost-raise -- the d2 analogue of the d1 cost-raise.

    Lever: dummy2 bids u*v2 with u ~ U(0.4, 1.0), so its bid is ALWAYS >= FLOOR*v2 for FLOOR<=0.4.
    Hence v_lb := max(observed d2 bids, slot-0 prices on its slot-0 wins) is a provable LOWER bound
    on v2, and raising our slot-1 bid toward FLOOR*v_lb - eps stays <= d2's actual bid => we never
    overtake => our seat/price is unchanged while d2 (slot 0, above us) pays more. At FLOOR<=0.4 the
    raise is sign-definite (can only lower d2's utility, never ours); subclasses may push FLOOR
    higher to trade a little own-utility for a stronger d2 hit."""
    FLOOR = 0.4

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        super().start_simulation(num_agents, num_slots, CTR_list, value, total_budget, T)
        self._sto_vlb = {}
        self._sto_fires = 0
        self._sto_util_removed = 0.0

    def notify_round_results(self, round_results):
        super().notify_round_results(round_results)
        rows = [r for r in round_results or [] if isinstance(r, (tuple, list)) and len(r) == 3]
        price_by_slot = {slot: float(price) for _w, slot, price in rows}
        for winner, slot, _price in rows:
            if winner == self.id:
                continue
            if slot >= 1:
                b = price_by_slot.get(slot - 1, 0.0)
                if b > self._sto_vlb.get(winner, 0.0):
                    self._sto_vlb[winner] = b
            if slot == 0:
                p0 = price_by_slot.get(0, 0.0)
                if p0 > self._sto_vlb.get(winner, 0.0):
                    self._sto_vlb[winner] = p0

    def _fresh(self, rid):
        return self._round - self._obs_round.get(rid, -10 ** 9) <= 100

    def _safe_lb(self, rid):
        """A no-overtake safe cap on rid's bid this round, or None if it can't be safely bounded."""
        t = self._rival_type(rid)
        if t == 'CONSTANT' and self._fresh(rid):
            return self._stats[rid][4]
        if t == 'STOCHASTIC' and self._fresh(rid):
            return self.FLOOR * self._sto_vlb.get(rid, 0.0)
        return None

    def _maybe_descend(self, bid, scens, central, below, budget):
        """d1 descend: EU seat = slot 0 above a CONSTANT rival -> descend if the margin improves."""
        top_rid, top_bid = below[0]
        if not (self._rival_type(top_rid) == 'CONSTANT' and top_bid > 0 and self._fresh(top_rid)):
            return bid
        vhat = self._stats[top_rid][4] / self.shade
        r = max(0.0, top_bid - _EPS)
        m_stay = m_desc = 0.0
        for vec, wt in scens:
            u_s, seated_s = gsp_alloc(bid, vec, self.value, self.CTR_list, self.num_slots)
            u_d, seated_d = gsp_alloc(r, vec, self.value, self.CTR_list, self.num_slots)
            m_stay += wt * (u_s - self._rival_util(top_rid, seated_s, vhat))
            m_desc += wt * (u_d - self._rival_util(top_rid, seated_d, vhat))
        if m_desc > m_stay:
            self._descents += 1
            return min(max(0.0, r), budget, self.value)
        return bid

    def _maybe_raise(self, bid, central, above, budget):
        """Fire only in slot 1 (exactly one rival above). CONSTANT -> just under its exact bid;
        STOCHASTIC -> just under FLOOR*v_lb (censoring-safe, no overtake at FLOOR<=0.4)."""
        if len(above) != 1:
            return bid
        top_rid, _c = above[0]
        cap = self._safe_lb(top_rid)
        if cap is None:
            return bid
        r = min(self.value, budget, max(0.0, cap - _EPS))
        if r > bid:
            if self._rival_type(top_rid) == 'STOCHASTIC':
                self._sto_util_removed += (r - bid) * (self.CTR_list[0] if self.CTR_list else 0)
                self._sto_fires += 1
            else:
                self._raises = getattr(self, '_raises', 0) + 1
            return r
        return bid

    def get_bid(self, budget):
        self._round += 1
        b_eu, _eu, _pts, _sc = self._eu_bid(budget)
        if b_eu != b_eu or b_eu in (float('inf'), float('-inf')):
            return 0.0
        bid = min(max(0.0, b_eu), budget, self.value)
        if self._round > self.WARMUP and self._stats and self.CTR_list:
            pids = self._points_ids()
            if pids:
                scens = self._scen_ids(pids)
                central = sorted(((rid, p[len(p) // 2]) for rid, p in pids), key=lambda t: t[1], reverse=True)
                above = [t for t in central if t[1] > bid]
                below = [t for t in central if t[1] <= bid]
                if not above and below:
                    bid = self._maybe_descend(bid, scens, central, below, budget)
                elif above:
                    bid = self._maybe_raise(bid, central, above, budget)
        if bid != bid or bid in (float('inf'), float('-inf')):
            return 0.0
        return float(bid)

class StochRaiseStrong07Agent1(StochRaiseAgent1):
    """FLOOR=0.7 -- the EXPECTED bid fraction of a U(0.4, 1.0) stochastic rival, rather than the
    0.4 worst case. Raising to the expectation removes more of that rival's utility, at the cost of
    occasionally overtaking it (whenever its draw falls below 0.7), so the suppression is no longer
    sign-definite: it trades a little of our own utility for a stronger hit on the hardest rival."""
    FLOOR = 0.7


# ===================== Task 1 -- BiddingAgent1 (no budget) =====================
class BiddingAgent1(StochRaiseStrong07Agent1):
    """
    Task 1: No Budget Constraint.

    Unconstrained GSP bidder: distribution-EU best response + targeted descend + a cost-raise on an
    identified constant rival + a censoring-safe cost-raise on an identified stochastic rival.
    """

    def __init__(self):
        super().__init__(shade=0.85)
        self.id = '207490913_318931672'

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        """
        Called once at the beginning of a T-round simulation.
        """
        super().start_simulation(num_agents, num_slots, CTR_list, value, total_budget, T)

    def get_bid(self, current_budget_remaining):
        """
        Returns your bid for the current round.
        """
        return super().get_bid(current_budget_remaining)

    def notify_round_results(self, round_results):
        """
        Called at the end of every round.
        round_results is a list of tuples: (agent_id, slot_won, price_paid)
        Only the results of the current round are provided, but you can keep track of
        history if needed.
        Only the agents that won in the current round will be included in round_results.
        - slot_won=0 is the BEST slot (highest CTR = CTR_list[0])
        - slot_won=3 is the WORST slot (lowest CTR = CTR_list[3])
        - price_paid is the raw bid of the agent ranked just below the winner.
        Actual cost = price_paid * CTR_list[slot_won].
        """
        super().notify_round_results(round_results)

    def get_id(self):
        return self.id


# ===================== Task 2 -- BiddingAgent2 (budget-constrained) =====================
class BiddingAgent2:
    """
    Task 2: With Budget Constraint.
    Focus on pacing your bids to maximize utility over the entire T rounds
    without running out of budget prematurely.

    Budget-aware GSP bidder: the unconstrained best-response bid, modulated by how far
    ahead/behind we are on budget vs. time.
    """

    def __init__(self):
        self.id = '207490913_318931672'
        self.value = 0.0
        self.num_slots = 0
        self.CTR_list = []
        self.budget_remaining = 0.0
        self._last_results = []
        self._round = 0

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        """
        Called once at the beginning of a T-round simulation.
        """
        self.num_agents = num_agents
        self.num_slots = num_slots
        self.CTR_list = list(CTR_list) if CTR_list else []
        self.value = float(value)
        self.total_budget = float(total_budget)
        self.budget_remaining = float(total_budget)
        self.T = max(1, int(T))
        self._round = 0
        self._last_results = []

    def get_bid(self, current_budget_remaining):
        """
        Returns your bid for the current round.
        """
        self._round += 1
        if not self.CTR_list or current_budget_remaining <= 0:
            return 0.0
        budget = float(current_budget_remaining)
        if not self._last_results:
            return min(self.value * 0.9, budget)
        br = choose_bid(self.value, self.CTR_list, self.num_slots, self._last_results, self.id, budget)
        rounds_left = max(1, self.T - self._round + 1)
        budget_frac = budget / self.total_budget if self.total_budget > 0 else 1.0
        time_frac = rounds_left / self.T
        pacing = budget_frac / time_frac if time_frac > 0 else 1.0
        bid = br * min(1.5, max(0.0, pacing))
        bid = min(max(0.0, bid), budget, self.value)
        if bid != bid or bid in (float('inf'), float('-inf')):
            return 0.0
        return float(bid)

    def notify_round_results(self, round_results):
        """
        Called at the end of every round.
        round_results is a list of tuples: (agent_id, slot_won, price_paid)
        - slot_won=0 is the BEST slot (highest CTR = CTR_list[0])
        - price_paid is the raw bid of the agent ranked just below the winner.
        Actual cost = price_paid * CTR_list[slot_won].
        """
        self._last_results = round_results if round_results else []

    def get_id(self):
        return self.id
