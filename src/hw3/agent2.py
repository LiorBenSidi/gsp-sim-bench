"""HW3 Task 2 agent -- budget-constrained. Best-response + self-correcting pacing so spend
spreads across all T rounds (leftover budget is worthless, so use it, don't hoard it)."""
from hw3.strategy import choose_bid


class BiddingAgent2:
    """
    Task 2: With Budget Constraint.
    Focus on pacing your bids to maximize utility over the entire T rounds
    without running out of budget prematurely.

    Budget-aware GSP bidder: the unconstrained best-response bid, modulated by how far
    ahead/behind we are on budget vs. time.
    """

    def __init__(self):
        self.id = "123456789_987654321"  # placeholder; bundler injects real IDs at build
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
        # CTR_list[j] is the click-through rate for slot j.
        # Slot 0 is the top position (highest CTR); slot -1 is the lowest.
        # These values are fixed for the entire simulation.
        # Reset EVERY sim -- instance reused across simulations. Never raise.
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
        # Ideal unconstrained bid, then pace it by budget-vs-time so spend is spread out.
        br = choose_bid(self.value, self.CTR_list, self.num_slots, self._last_results,
                        self.id, budget)
        rounds_left = max(1, self.T - self._round + 1)
        budget_frac = budget / self.total_budget if self.total_budget > 0 else 1.0
        time_frac = rounds_left / self.T
        pacing = budget_frac / time_frac if time_frac > 0 else 1.0
        # pacing > 1: under-spent, be more aggressive; < 1: over-spent, retreat to cheaper slots.
        bid = br * min(1.5, max(0.0, pacing))
        bid = min(max(0.0, bid), budget, self.value)
        if bid != bid or bid in (float("inf"), float("-inf")):
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
