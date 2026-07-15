class BiddingAgent1:
    def __init__(self):
        self.id = "dummy_1"
        self.value = 0

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        self.value = value

    def get_bid(self, current_budget_remaining):
        # Always bids 85% of its value (simple constant shading)
        return self.value * 0.85

    def notify_round_results(self, round_results):
        # Ignores history completely
        pass

    def get_id(self):
        return self.id
    

class BiddingAgent2:
    def __init__(self):
        self.id = "dummy_1"
        self.value = 0
        self.total_budget = 0
        self.T = 0
        self.current_round = 0

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        self.value = value
        self.total_budget = total_budget
        self.T = T
        self.current_round = 0

    def get_bid(self, current_budget_remaining):
        self.current_round += 1
        rounds_left = self.T - self.current_round + 1
        
        # Avoid division by zero on the last round
        if self.T == 0 or rounds_left <= 0:
            return 0.0

        budget_fraction = current_budget_remaining / self.total_budget
        time_fraction = rounds_left / self.T
        
        # Pacing ratio: > 1 means we are rich in budget, < 1 means we are poor
        pacing_ratio = budget_fraction / time_fraction 
        
        # Base bid is 80% of true value. Scale it by the pacing ratio.
        target_bid = self.value * 0.80 * pacing_ratio
        
        # Never bid more than true value or remaining budget
        return min(target_bid, self.value, current_budget_remaining)

    def notify_round_results(self, round_results):
        pass

    def get_id(self):
        return self.id