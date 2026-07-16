import math
import random
import glob
import os
import importlib.util
import sys
import time
import concurrent.futures

import CONSTANTS


def generate_ctr_list(num_slots):
    """
    Generates Click-Through Rates based on two random variables:
    T ~ Normal(0.7, 0.1)
    d ~ Normal(0.6, 0.05)
    P[j] = T * d^(j-1)
    """
    T_val = random.gauss(CONSTANTS.P_CTR_t[0], CONSTANTS.P_CTR_t[1])
    d_val = random.gauss(CONSTANTS.P_CTR_d[0], CONSTANTS.P_CTR_d[1])
    
    # Clamp values to ensure valid probabilities between 0 and 1
    T_val = min(max(T_val, 0.01), 1.0)
    d_val = min(max(d_val, 0.01), 1.0)
    
    return [T_val * (d_val ** i) for i in range(num_slots)]

def draw_value():
    """Draws a private value from a Uniform(0, 100) distribution."""
    return random.uniform(CONSTANTS.UNI_VALUE[0], CONSTANTS.UNI_VALUE[1])

def load_agents(agent_class_name):
    """
    Dynamically loads all python files starting with 'id_' in the current directory.
    Instantiates and returns a list of the specified agent class.
    """
    agents = []
    for file_path in glob.glob("id_*.py"):
        module_name = os.path.basename(file_path)[:-3]
        
        try:
            # Dynamically import the module
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Check if the requested class (BiddingAgent1 or BiddingAgent2) exists in the file
            if hasattr(module, agent_class_name):
                agent_class = getattr(module, agent_class_name)
                agents.append(agent_class())
        except Exception as e:
            print(f"Warning: Could not load {agent_class_name} from {file_path}. Error: {e}")
            
    return agents

def run_gsp_auction(bids, num_slots):
    """
    Executes a Generalized Second Price (GSP) auction.
    bids: dict of {agent_id: bid_amount}
    Returns: list of tuples (agent_id, slot_won, price_paid)
    """
    # Sort agents by their bids in descending order
    sorted_agents = sorted(bids.keys(), key=lambda k: bids[k], reverse=True)
    
    results = []
    for j in range(num_slots):
        if j < len(sorted_agents):
            winner = sorted_agents[j]
            # In GSP, you pay the bid of the agent directly below you.
            if j + 1 < len(sorted_agents):
                price_paid = bids[sorted_agents[j + 1]]
            else:
                price_paid = 0.0
            
            results.append((winner, j, price_paid))
            
    return results

def _invoke_with_timeout(executor, func, args, a_id, t, disqualified_this_sim, call_name):
    """
    Runs func(*args) under the CONSTANTS.TIME_CAP limit (applies to both get_bid
    and notify_round_results).

    ENFORCE_TIME_CAP=True (grading-like): the call runs on the agent's dedicated
    single-thread executor. exceeding TIME_CAP disqualifies the agent for the
    rest of this simulation.

    ENFORCE_TIME_CAP=False (fast mode, for local strategy testing): the call is
    made directly (~20x faster, identical simulation results). Overruns are
    reported but NOT punished - run a final check with enforcement on before
    submitting.

    """
    if not CONSTANTS.ENFORCE_TIME_CAP:
        start = time.perf_counter()
        try:
            result = func(*args)
        except Exception as e:
            print(f"Agent {a_id} raised an exception in {call_name} on round {t}: {e}.")
            return None, False
        elapsed = time.perf_counter() - start
        if elapsed > CONSTANTS.TIME_CAP:
            print(f"WARNING: Agent {a_id} took {elapsed*1000:.0f}ms in {call_name} on round {t} "
                  f"(cap is {CONSTANTS.TIME_CAP*1000:.0f}ms) - this WOULD disqualify you in grading!")
        return result, True

    future = executor.submit(func, *args)
    try:
        return future.result(timeout=CONSTANTS.TIME_CAP), True
    except concurrent.futures.TimeoutError:
        print(f"Agent {a_id} exceeded {CONSTANTS.TIME_CAP}s on {call_name} (round {t}); disqualified for rest of simulation.")
        disqualified_this_sim[a_id] = t
        return None, False
    except Exception as e:
        print(f"Agent {a_id} raised an exception in {call_name} on round {t}: {e}.")
        return None, False

def run_simulation(all_agents, num_slots, T, enforce_budget=False):
    """
    Runs a single simulation of T rounds.
    """
    if not all_agents:
        return {}

    ctr_list = generate_ctr_list(num_slots)
    num_agents = len(all_agents)
    
    agent_values = {}
    agent_budgets = {}
    agent_utilities = {agent.get_id(): 0.0 for agent in all_agents}
    disqualified_this_sim = {}  # a_id -> round index when disqualified

    executors = {a.get_id(): concurrent.futures.ThreadPoolExecutor(max_workers=1) for a in all_agents}
    
    for agent in all_agents:
        val = draw_value()
        agent_values[agent.get_id()] = val

        budget = random.gauss(CONSTANTS.BUDGET_NORM[0], CONSTANTS.BUDGET_NORM[1]) if enforce_budget else float('inf')
        agent_budgets[agent.get_id()] = budget 
        
        # Notify agent that a new simulation is starting
        agent.start_simulation(num_agents, num_slots, ctr_list, val, budget, T)

    # Run the T rounds
    for t in range(T):
        current_bids = {}
        
        # Collect Bids
        for agent in all_agents:
            a_id = agent.get_id()

            if a_id in disqualified_this_sim:
                current_bids[a_id] = 0.0
                continue

            if agent_budgets[a_id] > 0:
                raw_bid, ok = _invoke_with_timeout(
                    executors[a_id], agent.get_bid, (agent_budgets[a_id],),
                    a_id, t, disqualified_this_sim, "get_bid"
                )
                if not ok or not isinstance(raw_bid, (int, float)) or not math.isfinite(raw_bid):
                    raw_bid = 0.0
                current_bids[a_id] = min(max(0.0, raw_bid), agent_budgets[a_id])
            else:
                current_bids[a_id] = 0.0

        # Resolve Auction (GSP)
        round_results = run_gsp_auction(current_bids, num_slots)
        
        # Process Payments and Utilities
        public_history = []
        for winner_id, slot, price in round_results:
            public_history.append((winner_id, slot, price))
            
            cost = price * ctr_list[slot]
            agent_budgets[winner_id] -= cost
            
            value_gained = agent_values[winner_id] * ctr_list[slot]
            agent_utilities[winner_id] += (value_gained - cost)

        # Notify all agents of the public results
        for agent in all_agents:
            a_id = agent.get_id()
            if a_id in disqualified_this_sim:
                continue
            _invoke_with_timeout(
                executors[a_id], agent.notify_round_results, (list(public_history),),
                a_id, t, disqualified_this_sim, "notify_round_results"
            )

    # Penalty: utility earned before disqualification, diluted over the FULL round count, not rounds played
    for a_id in disqualified_this_sim:
        agent_utilities[a_id] = agent_utilities[a_id] / T

    for ex in executors.values():
        ex.shutdown(wait=False)  # don't block on a thread that may be permanently stuck

    return agent_utilities

def print_threshold_check(task_label, avg_utils):
    """
    Prints, for every non-dummy agent, whether it meets the non-competitive
    pass criterion: average utility >= (1 - PASS_TOLERANCE) of EACH dummy
    agent's average utility.
    """
    dummies = {a: u for a, u in avg_utils.items() if a.startswith("dummy")}
    students = {a: u for a, u in avg_utils.items() if not a.startswith("dummy")}
    if not dummies or not students:
        return

    print(f"\n--- {task_label}: threshold check (non-competitive part, based on {CONSTANTS.NUM_SIMULATIONS} simulations) ---")
    for s_id, s_u in students.items():
        all_ok = True
        for d_id, d_u in sorted(dummies.items()):
            # sign-safe tolerance: threshold is PASS_TOLERANCE below the dummy's average
            threshold = d_u - CONSTANTS.PASS_TOLERANCE * abs(d_u)
            ok = s_u >= threshold
            all_ok = all_ok and ok
            print(f"  vs {d_id}: {s_u:12,.2f} vs {d_u:12,.2f} (need >= {threshold:12,.2f}) -> {'OK' if ok else 'BELOW'}")
        print(f"  Agent {s_id}: {'PASSED' if all_ok else 'DID NOT PASS'} the {task_label} threshold check.")
    
def main():
    print("--- Loading Agents ---")
    
    agents_task1 = load_agents("BiddingAgent1")
    print(f"Loaded {len(agents_task1)} agents for Task 1 (Unconstrained).")
    
    agents_task2 = load_agents("BiddingAgent2")
    print(f"Loaded {len(agents_task2)} agents for Task 2 (Budget Constrained).")
    
    if not agents_task1 and not agents_task2:
        print("No agents found. Please ensure files start with 'id_' and are in the same directory.")
        return

    print("\n--- Starting Ad Auction Evaluation ---")

    if agents_task1:
        print("\nEvaluating Task 1 (Unconstrained)...")
        cumulative_utilities_t1 = {a.get_id(): 0 for a in agents_task1}
        participation_count_t1 = {a.get_id(): 0 for a in agents_task1}

        for sim in range(CONSTANTS.NUM_SIMULATIONS):
            utils = run_simulation(agents_task1, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS,
                            enforce_budget=False)
            for a_id, u in utils.items():
                cumulative_utilities_t1[a_id] += u
                participation_count_t1[a_id] += 1
                
        # Sort and print results
        avg_utils_t1 = {}
        sorted_results_t1 = sorted(cumulative_utilities_t1.items(), key=lambda item: item[1] / max(1, participation_count_t1[item[0]]), reverse=True)
        for a_id, total_u in sorted_results_t1:
            avg_u = total_u / participation_count_t1[a_id] if participation_count_t1[a_id] > 0 else 0
            avg_utils_t1[a_id] = avg_u
            print(f"Agent {a_id:<25} | Average Utility: {avg_u:8.2f} ")
        print_threshold_check("Task 1", avg_utils_t1)

    if agents_task2:
        print("\nEvaluating Task 2 (Budget Constrained)...")
        cumulative_utilities_t2 = {a.get_id(): 0 for a in agents_task2}
        participation_count_t2 = {a.get_id(): 0 for a in agents_task2}
        
        for sim in range(CONSTANTS.NUM_SIMULATIONS):
            utils = run_simulation(agents_task2, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS, enforce_budget=True)
            for a_id, u in utils.items():
                cumulative_utilities_t2[a_id] += u
                participation_count_t2[a_id] += 1
                
        # Sort and print results
        avg_utils_t2 = {}
        sorted_results_t2 = sorted(cumulative_utilities_t2.items(), key=lambda item: item[1] / max(1, participation_count_t2[item[0]]), reverse=True)
        for a_id, total_u in sorted_results_t2:
            avg_u = total_u / participation_count_t2[a_id] if participation_count_t2[a_id] > 0 else 0
            avg_utils_t2[a_id] = avg_u
            print(f"Agent {a_id:<25} | Average Utility: {avg_u:8.2f}")
        print_threshold_check("Task 2", avg_utils_t2)

if __name__ == "__main__":
    main()