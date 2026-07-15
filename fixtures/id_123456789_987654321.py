import random

class BiddingAgent1:
    """
    Task 1: No Budget Constraint. 
    """
    def __init__(self):
        # TODO: Change this to your actual ID(s)
        self.id = "123456789_987654321" 
        self.value = 0
        self.num_slots = 0
        self.CTR_list = []
        
    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        """
        Called once at the beginning of a T-round simulation.
        """
        self.num_agents = num_agents
        self.num_slots = num_slots
        # CTR_list[j] is the click-through rate for slot j.
        # Slot 0 is the top position (highest CTR); slot -1 is the lowest.
        # These values are fixed for the entire simulation.
        self.CTR_list = CTR_list
        self.value = value
        self.T = T
        # Total_budget is infinite for Agent 1

    def get_bid(self, current_budget_remaining):
        """
        Returns your bid for the current round.
        """
        # TODO: Implement your GSP bidding strategy.        
        # Dummy implementation: bid a random percentage of your value
        return self.value * random.uniform(0.5, 1.0)

    def notify_round_results(self, round_results):
        """
        Called at the end of every round. 
        round_results is a list of tuples: (agent_id, slot_won, price_paid)
        Only the results of the current round are provided, but you can keep track of history if needed.
        Only the agents that won in the current round will be included in round_results.
        - slot_won=0 is the BEST slot (highest CTR = CTR_list[0])
        - slot_won=3 is the WORST slot (lowest CTR = CTR_list[3])
        - price_paid is the raw bid of the agent ranked just below the winner.
        Actual cost = price_paid * CTR_list[slot_won].
        """
        pass

    def get_id(self):
        return self.id


class BiddingAgent2:
    """
    Task 2: With Budget Constraint.
    Focus on pacing your bids to maximize utility over the entire T rounds 
    without running out of budget prematurely.
    """
    def __init__(self):
        # TODO: Change this to your actual ID(s)
        self.id = "123456789_987654321" 
        self.value = 0
        self.num_slots = 0
        self.CTR_list = []
        self.budget_remaining = 0
        
    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        """
        Called once at the beginning of a T-round simulation.
        """
        self.num_agents = num_agents
        self.num_slots = num_slots
        self.CTR_list = CTR_list
        self.value = value
        self.total_budget = total_budget
        self.budget_remaining = total_budget
        self.T = T
        self.current_round = 0

    def get_bid(self, current_budget_remaining):
        """
        Returns your bid for the current round.
        """
        self.budget_remaining = current_budget_remaining
        self.current_round += 1
        
        # TODO: Implement your GSP strategy  

        # Dummy implementation: bid a random percentage of your value, capped by budget
        desired_bid = self.value * random.uniform(0.5, 1.0)

        return min(desired_bid, self.budget_remaining)

    def notify_round_results(self, round_results):
        """
        Called at the end of every round. 
        """
        pass

    def get_id(self):
        return self.id