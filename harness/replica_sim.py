"""Synchronous byte-parity replica of fixtures/server.py::run_simulation for TASK 1
(enforce_budget=False), used to iterate candidates in seconds instead of the real server's
~2h/5000-sim wall-clock (which is dominated by its per-call ThreadPoolExecutor, not agent logic).

PARITY CONTRACT (verified against fixtures/server.py:100-181): under a fixed `random.seed(s)` the
global-RNG draw order per sim is exactly:
  1. generate_ctr_list -> gauss(t), gauss(d)                       (server.py:107)
  2. per agent in list order: draw_value()=uniform(0,100); NO budget gauss when
     enforce_budget=False (line 121 short-circuits); then start_simulation immediately   (117-125)
  3. each round: get_bid in list order (dummy2 draws 1 uniform here) -> GSP resolve ->
     payments -> notify_round_results(list(history)) in list order                        (128-172)
`future.result()` serializes the server's thread pool, so direct in-order calls reproduce the exact
RNG sequence. We import the real generate_ctr_list / draw_value / run_gsp_auction so the auction math
and RNG helpers can NEVER drift from the grader.

NOT replicated: the budget gauss (Task 2) and the timeout/disqualify path (needs threads). The replica
is valid ONLY for agents proven under the 50ms cap by tests/Latency_Tests/test_latency.py; parity is
enforced by tests/System_Tests/test_replica_parity.py (byte-identical utilities vs the real server).
Non-timeout exceptions ARE replicated (get_bid raise -> bid 0.0; notify raise -> ignored), matching
server.py:96-98. Float determinism holds within one interpreter/platform (the parity test runs both
engines in-process); never compare hex across machines.
"""
import math

from server import draw_value, generate_ctr_list, run_gsp_auction  # the REAL grader helpers


def run_simulation_replica(all_agents, num_slots, T, enforce_budget=False):
    assert enforce_budget is False, "replica implements Task 1 (enforce_budget=False) only"
    if not all_agents:
        return {}

    ctr_list = generate_ctr_list(num_slots)                      # RNG: gauss pair
    agent_values, agent_budgets = {}, {}
    agent_utilities = {a.get_id(): 0.0 for a in all_agents}

    for agent in all_agents:                                     # value draw + start_simulation,
        val = draw_value()                                       # interleaved as server.py:117-125
        agent_values[agent.get_id()] = val
        agent_budgets[agent.get_id()] = float("inf")             # no budget gauss (short-circuit)
        agent.start_simulation(len(all_agents), num_slots, ctr_list, val, float("inf"), T)

    for _t in range(T):
        current_bids = {}
        for agent in all_agents:                                 # get_bid phase, list order
            a_id = agent.get_id()
            if agent_budgets[a_id] > 0:                          # mirror server.py:139
                try:
                    raw_bid = agent.get_bid(agent_budgets[a_id])
                except Exception:                                # server.py:96-98: logged, bid 0.0
                    raw_bid = None
                if not isinstance(raw_bid, (int, float)) or isinstance(raw_bid, bool) \
                        or not math.isfinite(raw_bid):
                    raw_bid = 0.0
                current_bids[a_id] = min(max(0.0, raw_bid), agent_budgets[a_id])
            else:
                current_bids[a_id] = 0.0

        round_results = run_gsp_auction(current_bids, num_slots)  # imported: identical + tie-break
        public_history = []
        for winner_id, slot, price in round_results:              # verbatim server.py:154-162
            public_history.append((winner_id, slot, price))
            cost = price * ctr_list[slot]
            agent_budgets[winner_id] -= cost
            value_gained = agent_values[winner_id] * ctr_list[slot]
            agent_utilities[winner_id] += (value_gained - cost)

        for agent in all_agents:                                 # notify phase, list order
            try:
                agent.notify_round_results(list(public_history))  # fresh copy per agent
            except Exception:
                pass

    return agent_utilities
