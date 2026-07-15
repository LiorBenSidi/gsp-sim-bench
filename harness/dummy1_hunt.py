"""d1-hunt candidates: recover DescentAgent1's dummy1 deficit (~-446 @ high N block 200000)
WITHOUT losing its dummy2 win (~+413). Three INDEPENDENT mechanisms, screened in-cloud under the
no-regression ratchet -- NOT shipped until one beats all 3 at high N. Stdlib-only, deterministic
(CRN-safe), <50ms/call.

The shipped baseline (src/hw3 DescentAgent1) descends below the constant top ONLY when the descent
strictly improves the single-round margin vs that rival. Against dummy1 (a constant 0.85*v bidder --
the ideal suppression victim) that strict gate leaves d1 slightly negative at high N. Each candidate
loosens a different bolt:

1. TunableDescentAgent1(tol_frac>0) -- EXTEND THE TRIGGER. Accept a descent when it is only
   near-EU-neutral (m_desc > m_stay - tol, tol = tol_frac*value*CTR0), so we suppress the constant
   top in MORE rounds. tol_frac=0 + eps=_EPS reproduces the shipped DescentAgent1 byte-for-byte.
2. TunableDescentAgent1(eps<_EPS) -- EXACT-VALUE EXPLOIT. dummy1's bid is known exactly, so sit as
   close under it as possible (tiny eps) -> it pays nearer its full bid -> maximum suppression per
   descent, same seat outcome.
3. ConstSuppressAgent1(w>0) -- CONSTANT-ONLY SUPPRESSION. A MarginCore whose suppression term
   credits ONLY constant-typed rivals (dummy1); stochastic rivals (dummy2) contribute 0, so d2 is
   handled as pure EU. A gentle, always-on d1 pressure that never touches the d2 policy.
"""
from margin_agent import DescentAgent1, MarginAgent1, gsp_alloc
from robust_agent import _EPS


class TunableDescentAgent1(DescentAgent1):
    """Ideas 1 & 2: DescentAgent1 with a tunable acceptance tolerance and descent-gap epsilon.
    tol_frac=0.0, eps=_EPS  ==  the shipped DescentAgent1 (verified byte-identical by unit test)."""

    def __init__(self, shade=0.85, tol_frac=0.0, eps=_EPS):
        super().__init__(shade=shade)
        self.tol_frac = float(tol_frac)   # accept descent if m_desc > m_stay - tol_frac*value*CTR0
        self.eps = float(eps)             # descent target = top_bid - eps (smaller -> closer under)

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
                        r = max(0.0, top_bid - self.eps)
                        ctr, ns = self.CTR_list, self.num_slots
                        tol = self.tol_frac * self.value * (ctr[0] if ctr else 0.0)
                        m_stay = m_desc = 0.0
                        for vec, wt in scens:
                            u_s, seated_s = gsp_alloc(bid, vec, self.value, ctr, ns)
                            u_d, seated_d = gsp_alloc(r, vec, self.value, ctr, ns)
                            m_stay += wt * (u_s - self._rival_util(top_rid, seated_s, vhat))
                            m_desc += wt * (u_d - self._rival_util(top_rid, seated_d, vhat))
                        if m_desc > m_stay - tol:              # relaxed acceptance (tol>=0)
                            bid = min(max(0.0, r), budget, self.value)
                            self._descents += 1
        if bid != bid or bid in (float("inf"), float("-inf")):
            return 0.0
        return float(bid)


class ConstSuppressAgent1(MarginAgent1):
    """Idea 3: MarginCore suppression aimed ONLY at constant-typed rivals (dummy1). The stochastic
    bidder (dummy2) contributes 0 to the suppression term, so its handling stays pure EU -- a gentle
    always-on d1 pressure that can't erode the d2 win. Small w (0.10 / 0.20)."""

    def _suppr(self, seated):
        return sum(price * self.CTR_list[slot] for rid, slot, price in seated
                   if self._rival_type(rid) == "CONSTANT")


class DirectD1MarginAgent1(MarginAgent1):
    """Idea 4: directly maximize E[own_util - lam*d1_util] using dummy1's KNOWN value
    (vhat = last_bid/shade for the identified CONSTANT rival). Sharper than ConstSuppress, which
    proxies suppression by SPEND (price*CTR) and is value-blind: here we compute the constant
    rival's EXACT utility (vhat-price)*CTR in each scenario -- the very quantity we must beat on
    average -- and trade our own utility against it with weight lam. Implemented by reusing
    MarginCore's objective J = E[own] + w*E[suppr] with w=lam and suppr = -(constant rival util),
    so maximizing J minimizes d1's utility. lam=0 -> pure EU. Sweep lam in {0.25, 0.50, 1.00}."""

    def __init__(self, lam=0.5, shade=0.85):
        super().__init__(w=float(lam))
        self.shade = float(shade)

    def _suppr(self, seated):
        total = 0.0
        for rid, slot, price in seated:
            s = self._stats.get(rid)
            if s and s[4] > 0 and self._rival_type(rid) == "CONSTANT":
                vhat = s[4] / self.shade                     # dummy1's exact value (bid/0.85)
                total += (vhat - price) * self.CTR_list[slot]  # its utility in this seat
        return -total   # NEGATIVE: maximizing J = own + lam*suppr minimizes d1's utility


class DescentRaiseAgent1(DescentAgent1):
    """Idea 5 (HYBRID): descent's descend (when our EU seat is slot 0 directly ABOVE a constant
    rival) PLUS a cost-raise (when our EU seat is slot 1 directly BELOW a constant rival). The
    cost-raise is the KEY d2-neutral lever: in GSP the slot-0 winner pays the bid of whoever sits
    directly below it (us), so bidding just under d1's identified true bid makes d1 pay ~its full
    bid for slot 0 while OUR own price -- set by the agent below US (slot 2) -- is unchanged. We
    keep our seat (no overtake, r < b_top), our utility is untouched, and d2 (seated below us) is
    unaffected -> d1 suppression that does NOT feed the d1<->d2 tradeoff the weighted mechanisms hit.

    Rationale: weighted suppression (csupp/directd1) suppresses d1 by DESCENDING (seat sacrifice),
    which cedes seats to d2 -> every weight that fixes d1 breaks d2 (~1:1). The cost-raise suppresses
    d1 from BELOW without a seat change, so it can add d1 margin without the d2 cost. Combines with
    descent's slot-0 descend for both configurations. This is the documented HYBRID resume path."""

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
                if not above and below:                        # EU seat = slot 0 -> descend (inherited)
                    top_rid, top_bid = below[0]
                    if (self._rival_type(top_rid) == "CONSTANT" and top_bid > 0
                            and (self._round - self._obs_round.get(top_rid, -10**9)) <= 100):
                        vhat = self._stats[top_rid][4] / self.shade
                        r = max(0.0, top_bid - _EPS)
                        ctr, ns = self.CTR_list, self.num_slots
                        m_stay = m_desc = 0.0
                        for vec, wt in scens:
                            u_s, seated_s = gsp_alloc(bid, vec, self.value, ctr, ns)
                            u_d, seated_d = gsp_alloc(r, vec, self.value, ctr, ns)
                            m_stay += wt * (u_s - self._rival_util(top_rid, seated_s, vhat))
                            m_desc += wt * (u_d - self._rival_util(top_rid, seated_d, vhat))
                        if m_desc > m_stay:
                            bid = min(max(0.0, r), budget, self.value)
                            self._descents += 1
                elif len(above) == 1:                          # EU seat = slot 1 -> cost-raise (new)
                    top_rid, _top_central = above[0]            # the single rival above us (slot 0)
                    if (self._rival_type(top_rid) == "CONSTANT"
                            and (self._round - self._obs_round.get(top_rid, -10**9)) <= 100):
                        b_top = self._stats[top_rid][4]         # d1's exact identified bid
                        r = min(self.value, max(0.0, b_top - _EPS))   # just under -> no overtake
                        if r > bid:                             # raise, still slot 1 -> d1 pays more
                            bid = min(max(0.0, r), budget, self.value)
                            self._raises = getattr(self, "_raises", 0) + 1
        if bid != bid or bid in (float("inf"), float("-inf")):
            return 0.0
        return float(bid)


class DescentRaiseCondAgent1(DescentRaiseAgent1):
    """Option-3 candidate: the hybrid, but the slot-0 DESCEND is loosened (fire even when the d1
    margin barely improves, tol_frac >= 0) AND gated on a d2 PROTECTION -- only descend when doing
    so does not give a STOCHASTIC rival (dummy2) a better (higher-CTR) slot in expectation. The
    cost-raise (d2-neutral) is inherited unchanged. Idea: recover more d1 in the rounds where a
    descend is d2-safe, without conceding the d2 win in the rounds where it is not."""

    def __init__(self, shade=0.85, tol_frac=0.0, d2tol_frac=0.0):
        super().__init__(shade=shade)
        self.tol_frac = float(tol_frac)     # loosen the d1-margin gate
        self.d2tol_frac = float(d2tol_frac)  # allowed expected d2 CTR gain before we veto the descend

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
                ctr, ns = self.CTR_list, self.num_slots
                if not above and below:                        # EU seat = slot 0 -> conditional descend
                    top_rid, top_bid = below[0]
                    if (self._rival_type(top_rid) == "CONSTANT" and top_bid > 0
                            and (self._round - self._obs_round.get(top_rid, -10**9)) <= 100):
                        vhat = self._stats[top_rid][4] / self.shade
                        r = max(0.0, top_bid - _EPS)
                        stoch = {rid for rid in self._stats if self._rival_type(rid) == "STOCHASTIC"}
                        m_stay = m_desc = d2_gain = 0.0
                        for vec, wt in scens:
                            u_s, seated_s = gsp_alloc(bid, vec, self.value, ctr, ns)
                            u_d, seated_d = gsp_alloc(r, vec, self.value, ctr, ns)
                            m_stay += wt * (u_s - self._rival_util(top_rid, seated_s, vhat))
                            m_desc += wt * (u_d - self._rival_util(top_rid, seated_d, vhat))
                            sl_s = {rid: slot for rid, slot, _p in seated_s}
                            sl_d = {rid: slot for rid, slot, _p in seated_d}
                            for rid in stoch:                    # + = d2 gets a better (higher-CTR) slot
                                cs = ctr[sl_s[rid]] if rid in sl_s and sl_s[rid] < len(ctr) else 0.0
                                cd = ctr[sl_d[rid]] if rid in sl_d and sl_d[rid] < len(ctr) else 0.0
                                d2_gain += wt * (cd - cs)
                        tol = self.tol_frac * self.value * (ctr[0] if ctr else 0.0)
                        d2cap = self.d2tol_frac * (ctr[0] if ctr else 0.0)
                        if m_desc > m_stay - tol and d2_gain <= d2cap:   # d1-positive AND d2-safe
                            bid = min(max(0.0, r), budget, self.value)
                            self._descents += 1
                elif len(above) == 1:                          # EU seat = slot 1 -> cost-raise (inherited)
                    top_rid, _top_central = above[0]
                    if (self._rival_type(top_rid) == "CONSTANT"
                            and (self._round - self._obs_round.get(top_rid, -10**9)) <= 100):
                        b_top = self._stats[top_rid][4]
                        r = min(self.value, max(0.0, b_top - _EPS))
                        if r > bid:
                            bid = min(max(0.0, r), budget, self.value)
                            self._raises = getattr(self, "_raises", 0) + 1
        if bid != bid or bid in (float("inf"), float("-inf")):
            return 0.0
        return float(bid)
