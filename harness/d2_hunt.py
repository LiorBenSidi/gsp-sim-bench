"""d2-hunt candidate registry: strategies aimed at beating ALL 3 dummies (the binding one is d2).

Core lever (red-team, 2026-07-15): dummy2 bids u*v2 with u~U(0.4,1.0), so its bid is ALWAYS
>= 0.4*v2. Hence v_lb := max(observed d2 bids, slot-0 prices on d2-won-slot-0 rounds) is a provable
LOWER bound on v2, and raising our slot-1 bid to FLOOR*v_lb - eps (FLOOR<=0.4) is guaranteed <= d2's
actual bid => never overtakes => our seat/price unchanged while d2 (slot 0 above us) pays more.
Sign-definite: can only lower d2's utility, never ours. The d2 analogue of the shipped d1 cost-raise.

Candidates (all subclass the shipped DescentRaiseAgent1 so d1-descend + d1-cost-raise are preserved
byte-for-byte; each adds a d2/own-utility lever on top):
  - StochRaiseAgent1        : + slot-1 STOCHASTIC cost-raise, safe FLOOR=0.4 bound (sign-definite).
  - StochRaiseSlot2Agent1   : generalize the raise to ANY slot k>=1 (min-bound over all above rivals
                              so we never overtake) -> fires in more configs -> more d2 suppression.
  - StochRaiseStrong07Agent1: FLOOR=0.7 (d2's EXPECTED fraction) -> stronger raise but occasionally
                              overtakes d2 (NOT sign-definite; trades own-utility for d2 suppression).
  - ValueFloorStochAgent1   : StochRaise + a mild own-utility floor bid>=C*value (C<0.9), testing the
                              d1<->d2 sweet spot the earlier c*v sweep (c>=0.90) never reached.

NOT sim-validated yet -- built for a single batch validation pass (docs/explorations/
validate_all_candidates.py) when compute is available (cool machine or Actions reset). All stdlib,
O(1)/round, < 50ms.
"""
from hw3.descent import _EPS, StochRaiseAgent1, StochRaiseStrong07Agent1

# StochRaiseAgent1 (sign-definite FLOOR=0.4 base) and StochRaiseStrong07Agent1 (FLOOR=0.7, SHIPPED
# as BiddingAgent1) now live in src/hw3/descent.py so they bundle into the submission. The remaining
# research arms below stay here for the phase-3 d1-lever hunt.


class StochRaiseSlot2Agent1(StochRaiseAgent1):
    """Generalize the cost-raise to ANY slot k>=1: raise toward the MIN safe-lower-bound over ALL
    rivals above us (so a realized reorder never overtakes any of them), making the directly-above
    rival pay our bid. Fires in more configurations than the slot-1-only base -> more suppression."""

    def _maybe_raise(self, bid, central, above, budget):
        caps = []
        for rid, _c in above:
            cap = self._safe_lb(rid)
            if cap is None:                 # an un-boundable rival above -> cannot raise safely
                return bid
            caps.append((rid, cap))
        if not caps:
            return bid
        directly_above_rid = above[-1][0]   # smallest bid among above (central sorted desc)
        r = min(self.value, budget, max(0.0, min(c for _r, c in caps) - _EPS))
        if r > bid:
            if self._rival_type(directly_above_rid) == "STOCHASTIC":
                self._sto_util_removed += (r - bid) * (self.CTR_list[0] if self.CTR_list else 0)
                self._sto_fires += 1
            else:
                self._raises = getattr(self, "_raises", 0) + 1
            return r
        return bid


# StochRaiseStrong07Agent1 (FLOOR=0.7) is imported from hw3.descent (shipped as BiddingAgent1).


class ValueFloorStochAgent1(StochRaiseAgent1):
    """StochRaise + a mild own-utility floor: bid >= C*value (C<0.9). Raises E[ours] (helps the d2
    margin) while the descend/cost-raise still defend d1 -- probing the d1<->d2 sweet spot the earlier
    c*v sweep (c>=0.90, which lost d1) never reached. Overrides get_bid to floor AFTER the levers."""
    C = 0.6

    def get_bid(self, budget):
        bid = super().get_bid(budget)
        if self.value <= 0:
            return bid
        floor = min(self.C * self.value, budget, self.value)
        out = min(max(bid, floor), budget, self.value)
        if out != out or out in (float("inf"), float("-inf")):
            return 0.0
        return float(out)


class ValueFloorStoch05Agent1(ValueFloorStochAgent1):
    C = 0.5


class ValueFloorStoch07Agent1(ValueFloorStochAgent1):
    C = 0.7


# Registry consumed by docs/explorations/validate_all_candidates.py.
# Ordered cheapest/safest first. stoch_raise is the sign-definite baseline (highest confidence);
# the value-floor sweep probes the d1<->d2 sweet spot (riskier -- may cede d1).
CANDIDATES = {
    "stoch_raise": StochRaiseAgent1,            # sign-definite, free on d1 -- most likely safe win
    "stoch_slot2": StochRaiseSlot2Agent1,       # more fires -> more d2 suppression (still no-overtake)
    "stoch_strong07": StochRaiseStrong07Agent1,  # stronger d2 hit, may overtake d2 (not sign-definite)
    "valuefloor0.5": ValueFloorStoch05Agent1,   # mild own-utility floor (sweet-spot sweep)
    "valuefloor0.6": ValueFloorStochAgent1,
    "valuefloor0.7": ValueFloorStoch07Agent1,   # most aggressive floor -- highest d1-cede risk
}
