"""Challenger BiddingAgent1 for the parked beat-all-3 search (Candidate C' / robust layer, first
increment). NOT shipped -- evaluated as an exp_valueaware candidate under the no-regression ratchet.
Stdlib-only, O(1) memory per rival, well under the 50ms/call cap.

Core idea (vs the champion's best-response-to-last-round):
- Accumulate each rival's reconstructed-bid DISTRIBUTION across rounds (count/sum/sumsq/max/last),
  not just the last round.
- Predict each rival as a small set of plausible bids {mean-sd, mean, mean+sd, max}.
- Pick the bid maximizing EXPECTED utility over the joint product of those scenarios (a partner's
  candidate-set EU) -- robust to noise and to unseen opponents, and distribution-aware for the
  random bidder (dummy2) instead of chasing its last draw.
- No explicit cost-raise here: this is deliberately the plan's `raise_top-OFF` arm.
- Value-anchored cold open; falls back to a point prediction when the field is large (guards the
  many-agent regime and the per-call latency).
"""
import itertools

_EPS = 1e-3
_MAX_SCENARIOS = 256   # product-of-points cap; above it, fall back to the mean vector
_MAX_RIVALS_ENUM = 6   # above this many rivals, use point prediction (keeps get_bid cheap)


class RobustAgent1:
    def __init__(self):
        self.id = "ours"
        self.value = 0.0
        self.CTR_list = []
        self.num_slots = 0
        self.num_agents = 0
        self.T = 1
        self._round = 0
        self._last = []
        self._stats = {}   # rid -> [count, sum, sumsq, max, last]

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

    # ---- utility of a bid against a concrete rival vector (exact GSP semantics) ----
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
        """List of (rival_vector_desc, weight). Product of per-rival points, capped; else mean-only."""
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
        (the conservative-raise arm) reuse this and then adjust best_b -- so `robust`'s behavior
        stays byte-identical."""
        if not self.CTR_list or self.value <= 0:
            return 0.0, None, None, None
        if not self._stats:
            return float(min(self.value * 0.9, budget)), None, None, None   # value-anchored cold open
        points = self._rival_points()
        if not points:
            return float(min(self.value * 0.9, budget)), None, None, None
        scenarios = self._scenarios(points)
        # candidate bids: value fractions + just-above each rival's central estimate + 0
        cands = {0.0, self.value}
        for f in (0.25, 0.5, 0.7, 0.85, 0.95):
            cands.add(f * self.value)
        for p in points:
            central = p[len(p) // 2]
            if 0.0 < central < self.value:
                cands.add(min(self.value, central + _EPS))
        best_b, best_eu = 0.0, -1e30
        for b in cands:
            b = min(max(0.0, b), budget, self.value)
            eu = 0.0
            for vec, w in scenarios:
                eu += w * self._util(b, vec)
            if eu > best_eu:
                best_eu, best_b = eu, b
        return best_b, best_eu, points, scenarios

    def get_bid(self, budget):
        self._round += 1
        best_b, _eu, _pts, _sc = self._eu_bid(budget)
        if best_b != best_b or best_b in (float("inf"), float("-inf")):
            return 0.0
        return float(min(max(0.0, best_b), budget, self.value))

    def notify_round_results(self, round_results):
        self._last = round_results if round_results else []
        rows = [r for r in self._last if isinstance(r, (tuple, list)) and len(r) == 3]
        price_by_slot = {slot: float(price) for (_w, slot, price) in rows}
        for (winner, slot, _price) in rows:
            if slot >= 1 and winner != self.id:   # slot-0 bid is censored -> skip (v0.1 limitation)
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
