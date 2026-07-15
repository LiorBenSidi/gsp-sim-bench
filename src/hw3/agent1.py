"""HW3 Task 1 agent -- no budget constraint. Distribution-aware EU with two targeted, constant-rival
overrides (the DescentRaise policy): best-respond to each rival's reconstructed bid DISTRIBUTION,
and against an identified constant-fraction rival either (a) descend just below it when we sit
directly above it and that widens our margin, or (b) cost-raise -- bid just under it when we sit
directly below it, so it pays ~its full bid for the top slot while our own price and seat are
unchanged. Pure positioning (never touches pacing).

and against an identified stochastic rival (dummy2) cost-raise from slot 1 toward a censoring-safe
lower bound on its bid so it pays more for the top slot while we never overtake it.

This class is a thin wrapper: it keeps the grader-facing method signatures byte-identical to the
template (the server binds them positionally) and delegates to the descent-raise + stochastic-raise
engine."""
from hw3.descent import StochRaiseStrong07Agent1


class BiddingAgent1(StochRaiseStrong07Agent1):
    """Unconstrained GSP bidder: distribution-EU best response + targeted descend + d1 cost-raise +
    censoring-safe d2 (stochastic-rival) cost-raise."""

    def __init__(self):
        super().__init__(shade=0.85)
        self.id = "123456789_987654321"  # placeholder; bundler injects real IDs at build

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        super().start_simulation(num_agents, num_slots, CTR_list, value, total_budget, T)

    def get_bid(self, current_budget_remaining):
        return super().get_bid(current_budget_remaining)

    def notify_round_results(self, round_results):
        super().notify_round_results(round_results)

    def get_id(self):
        return self.id
