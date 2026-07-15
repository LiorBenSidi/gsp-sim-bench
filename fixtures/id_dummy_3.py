class BiddingAgent1:
    def __init__(self):
        self.id = "dummy_3"
        self.value = 0
        self.last_prices = []

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        self.value = value
        self.last_prices = []

    def get_bid(self, current_budget_remaining):
        # If there is no history yet, bid 75% of value
        if not self.last_prices:
            return self.value * 0.75
        
        # Sort prices and find the median clearing price
        sorted_prices = sorted(self.last_prices)
        median_price = sorted_prices[len(sorted_prices) // 2]
        
        # Try to outbid the median price by 10%
        target_bid = median_price * 1.1 
        
        # Safety check: never bid higher than our true value
        # If the target is too expensive, revert to a safe 80% bid
        if target_bid >= self.value:
            return self.value * 0.80
            
        return target_bid

    def notify_round_results(self, round_results ):
        # round_results is a list of tuples: (agent_id, slot_won, price_paid)
        # Extract all positive prices paid in the last round
        self.last_prices = [price for _, _, price in round_results if price > 0]
        
        # If no one paid anything (rare), insert a dummy 0 to avoid crashing
        if not self.last_prices:
            self.last_prices = [0.0]

    def get_id(self):
        return self.id
    

class BiddingAgent2:
    def __init__(self):
        self.id = "dummy_3"
        self.value = 0
        self.total_budget = 0
        self.last_prices = []

    def start_simulation(self, num_agents, num_slots, CTR_list, value, total_budget, T):
        self.value = value
        self.total_budget = total_budget
        self.last_prices = []

    def get_bid(self, current_budget_remaining):
        # Default starting bid if no history exists
        if not self.last_prices:
            base_bid = self.value * 0.60
        else:
            # Track the average clearing price and aim slightly above it
            avg_price = sum(self.last_prices) / len(self.last_prices)
            base_bid = avg_price * 1.10
            
        # Guarantee we never bid more than 90% of our true value
        base_bid = min(base_bid, self.value * 0.90)
        
        # Emergency Brake: If < 15% budget remains, drastically cut bids
        if current_budget_remaining < (self.total_budget * 0.15):
            base_bid *= 0.40
            
        return min(base_bid, current_budget_remaining)

    def notify_round_results(self, round_results):
        # Extract all positive prices paid in the last round
        self.last_prices = [price for _, _, price in round_results if price > 0]
        if not self.last_prices:
            self.last_prices = [0.0]

    def get_id(self):
        return self.id