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
    """
    Task 1: No Budget Constraint.

    Unconstrained GSP bidder: distribution-EU best response + targeted descend + a cost-raise on an
    identified constant rival + a censoring-safe cost-raise on an identified stochastic rival.
    """

    def __init__(self):
        super().__init__(shade=0.85)
        self.id = "123456789_987654321"  # placeholder; bundler injects real IDs at build

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        """
        Called once at the beginning of a T-round simulation.
        """
        # CTR_list[j] is the click-through rate for slot j.
        # Slot 0 is the top position (highest CTR); slot -1 is the lowest.
        # These values are fixed for the entire simulation.
        # Total_budget is infinite for Agent 1.
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
