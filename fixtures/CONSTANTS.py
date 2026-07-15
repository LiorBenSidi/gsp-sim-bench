# --- CONSTANTS ---

NUM_SIMULATIONS = 30  # Number of full T-round games to run - you can set it as you wish to validate your results, we will use very high NUM_SIMULATIONS in our evaluation to get statistically significant results
T_ROUNDS = 3000        # Rounds per simulation
NUM_SLOTS = 4           # Number of ad slots available in each round

P_CTR_t = (0.7, 0.1)   # CTR distribution parameters
P_CTR_d = (0.6, 0.05) 

UNI_VALUE = (0,100)  # Uniform distribution for agent values

BUDGET_NORM = (10000, 750)  # Normal distribution for agent budgets

TIME_CAP = 0.05 # Time cap for each round in seconds