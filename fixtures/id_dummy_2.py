import random

class BiddingAgent1:
    def __init__(self):
        self.id = "dummy_2"
        self.value = 0

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        self.value = value

    def get_bid(self, current_budget_remaining):
        # Adds noise to the market by bidding randomly between 40% and 100% of value
        return self.value * random.uniform(0.4, 1.0)

    def notify_round_results(self, round_results):
        pass

    def get_id(self):
        return self.id
    

class BiddingAgent2:
    def __init__(self):
        self.id = "dummy_2"
        self.value = 0
        self.total_budget = 0

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        self.value = value
        self.total_budget = total_budget

    def get_bid(self, current_budget_remaining):
        # Phase 1: Aggressive bidding while budget > 40%
        if current_budget_remaining > (self.total_budget * 0.40):
            target_bid = self.value * 0.85
        # Phase 2: Survival mode
        else:
            target_bid = self.value * 0.35
            
        return min(target_bid, current_budget_remaining)

    def notify_round_results(self, round_results):
        pass

    def get_id(self):
        return self.id