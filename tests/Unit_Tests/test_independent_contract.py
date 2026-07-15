"""
Independent behavioral test suite for HW3 GSP bidding bots.

Written from the GRADER CONTRACT ONLY (fixtures/server.py + template docstrings +
CONSTANTS.py). The author has NOT read src/hw3/strategy.py, agent1.py, agent2.py,
or any existing tests -- these tests assert BEHAVIOR the server relies on, not the
strategy's internal mechanism.

Contract source: fixtures/server.py
  - get_bid(current_budget_remaining) -> the server forces non-(int|float) or
    non-finite results to 0.0, then clamps into [0, current_budget_remaining].
    A well-behaved agent returns a python int/float that is finite and in range,
    and never raises.
  - start_simulation(...) is called UNGUARDED (server.py line 125). Any exception
    there aborts the whole evaluation run -> must never raise.
  - The SAME instance is reused across many simulations (server main loop). A new
    start_simulation must fully reset per-sim state.
  - notify_round_results gets ONLY the current round's winners as
    (agent_id, slot_won, price_paid) tuples (<= num_slots of them). Must not raise.
  - get_id() -> non-empty, stable string.
  - Each get_bid / notify_round_results call must finish well under TIME_CAP (50ms).
"""

import math
import random
import sys
import time

import pytest

from hw3.agent1 import BiddingAgent1
from hw3.agent2 import BiddingAgent2

TIME_CAP = 0.05        # CONSTANTS.TIME_CAP, seconds
NUM_SLOTS = 4          # CONSTANTS.NUM_SLOTS
LATENCY_BUDGET = 0.045 # assert well under the 50ms cap


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def make_ctr(num_slots):
    """A realistic descending CTR list: T * d^j, T=0.7, d=0.6 (server model)."""
    return [0.7 * (0.6 ** j) for j in range(num_slots)]


def bid_is_wellbehaved(bid, budget):
    """Contract: finite python int/float in [0, budget]."""
    if isinstance(bid, bool):          # bool sneaks through isinstance(int)
        return False
    if not isinstance(bid, (int, float)):
        return False
    if not math.isfinite(bid):
        return False
    if bid < -1e-9:
        return False
    if math.isfinite(budget) and bid > budget + 1e-6:
        return False
    return True


def started_agent1(value=50.0, num_agents=5, num_slots=NUM_SLOTS, T=3000):
    a = BiddingAgent1()
    a.start_simulation(num_agents, num_slots, make_ctr(num_slots),
                       value, float("inf"), T)
    return a


def started_agent2(value=50.0, budget=10000.0, num_agents=5,
                   num_slots=NUM_SLOTS, T=3000):
    a = BiddingAgent2()
    a.start_simulation(num_agents, num_slots, make_ctr(num_slots),
                       value, budget, T)
    return a


ALL_AGENT_FACTORIES = [
    ("BiddingAgent1", BiddingAgent1),
    ("BiddingAgent2", BiddingAgent2),
]


# --------------------------------------------------------------------------- #
# get_id                                                                       #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,cls", ALL_AGENT_FACTORIES)
def test_get_id_nonempty_string(name, cls):
    a = cls()
    gid = a.get_id()
    assert isinstance(gid, str), f"{name}.get_id() must be a str, got {type(gid)}"
    assert len(gid) > 0, f"{name}.get_id() must be non-empty"


@pytest.mark.parametrize("name,cls", ALL_AGENT_FACTORIES)
def test_get_id_stable_across_calls(name, cls):
    a = cls()
    first = a.get_id()
    for _ in range(5):
        assert a.get_id() == first, f"{name}.get_id() must be stable across calls"


# --------------------------------------------------------------------------- #
# start_simulation must never raise (called UNGUARDED by the server)          #
# --------------------------------------------------------------------------- #
def test_agent1_start_simulation_edge_inputs_no_raise():
    a = BiddingAgent1()
    # num_agents=1, num_slots=1, value=0, budget=inf, T=1
    a.start_simulation(1, 1, make_ctr(1), 0.0, float("inf"), 1)


def test_agent2_start_simulation_edge_inputs_no_raise():
    a = BiddingAgent2()
    # budget=0 is a legal draw edge; must not raise
    a.start_simulation(1, 1, make_ctr(1), 0.0, 0.0, 1)


@pytest.mark.parametrize("name,cls", ALL_AGENT_FACTORIES)
def test_start_simulation_zero_value_no_raise(name, cls):
    a = cls()
    a.start_simulation(3, NUM_SLOTS, make_ctr(NUM_SLOTS), 0.0, 10000.0, 3000)


def test_agent1_start_simulation_infinite_budget_usable():
    # Agent 1 always receives float('inf') budget from the server.
    a = started_agent1(value=73.0)
    bid = a.get_bid(float("inf"))
    assert bid_is_wellbehaved(bid, float("inf")), (
        f"Agent1 with inf budget returned non-wellbehaved bid: {bid!r}")


# --------------------------------------------------------------------------- #
# get_bid returns a well-behaved value                                         #
# --------------------------------------------------------------------------- #
def test_agent1_get_bid_wellbehaved():
    a = started_agent1(value=50.0)
    for _ in range(20):
        bid = a.get_bid(float("inf"))
        assert bid_is_wellbehaved(bid, float("inf")), f"bad bid {bid!r}"


def test_agent2_get_bid_within_budget():
    # Live budget is the get_bid argument; a well-behaved Agent2 respects it.
    a = started_agent2(value=90.0, budget=10000.0)
    for live_budget in (10000.0, 500.0, 50.0, 5.0, 0.5):
        bid = a.get_bid(live_budget)
        assert bid_is_wellbehaved(bid, live_budget), (
            f"Agent2 bid {bid!r} not in [0, {live_budget}] "
            f"(server would clamp, but a well-behaved agent caps itself)")


def test_agent2_get_bid_tiny_budget_high_value():
    # Value 100 (max), but only 1.0 of budget left: bid must be <= 1.0.
    a = started_agent2(value=100.0, budget=100.0)
    bid = a.get_bid(1.0)
    assert bid_is_wellbehaved(bid, 1.0), (
        f"Agent2 with 1.0 budget left bid {bid!r}; must not exceed live budget")


@pytest.mark.parametrize("name,cls", ALL_AGENT_FACTORIES)
def test_get_bid_returns_python_numeric_type(name, cls):
    # The server's type gate is isinstance(raw_bid, (int, float)); a numpy int
    # or other non-(int|float) is silently forced to 0.0, discarding the bid.
    a = cls()
    a.start_simulation(5, NUM_SLOTS, make_ctr(NUM_SLOTS), 60.0, 10000.0, 3000)
    bid = a.get_bid(10000.0)
    assert isinstance(bid, (int, float)) and not isinstance(bid, bool), (
        f"{name}.get_bid returned {type(bid)}; the server only accepts "
        f"python int/float and forces anything else to 0.0")


# --------------------------------------------------------------------------- #
# Per-simulation state reset (same instance reused across sims)                #
# --------------------------------------------------------------------------- #
def test_agent2_state_resets_between_sims():
    a = BiddingAgent2()
    # Sim 1: huge budget, max value, many rounds.
    a.start_simulation(8, NUM_SLOTS, make_ctr(NUM_SLOTS), 100.0, 1_000_000.0, 3000)
    for _ in range(30):
        a.get_bid(1_000_000.0)
        a.notify_round_results([(a.get_id(), 0, 12.34)])
    # Sim 2: tiny budget, tiny value, few rounds -- must NOT bleed from sim 1.
    a.start_simulation(2, 1, make_ctr(1), 1.0, 10.0, 5)
    bid = a.get_bid(10.0)
    assert bid_is_wellbehaved(bid, 10.0), (
        f"After reset to a tiny sim, Agent2 bid {bid!r} exceeds the new "
        f"budget 10.0 -- state from the previous huge sim leaked through")


def test_agent1_state_resets_between_sims():
    a = BiddingAgent1()
    a.start_simulation(8, NUM_SLOTS, make_ctr(NUM_SLOTS), 100.0, float("inf"), 3000)
    for _ in range(30):
        a.get_bid(float("inf"))
        a.notify_round_results([(a.get_id(), 0, 5.0)])
    # New sim with value 0 -> a value-proportional bid should collapse toward 0.
    a.start_simulation(2, 1, make_ctr(1), 0.0, float("inf"), 5)
    bid = a.get_bid(float("inf"))
    assert bid_is_wellbehaved(bid, float("inf")), f"bad bid after reset: {bid!r}"


# --------------------------------------------------------------------------- #
# notify_round_results robustness                                              #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,cls", ALL_AGENT_FACTORIES)
def test_notify_empty_list_no_raise(name, cls):
    a = cls()
    a.start_simulation(5, NUM_SLOTS, make_ctr(NUM_SLOTS), 40.0, 10000.0, 3000)
    a.notify_round_results([])  # e.g. round 0 / no winners provided


@pytest.mark.parametrize("name,cls", ALL_AGENT_FACTORIES)
def test_notify_wellformed_including_own_win_no_raise(name, cls):
    a = cls()
    a.start_simulation(5, NUM_SLOTS, make_ctr(NUM_SLOTS), 40.0, 10000.0, 3000)
    own = a.get_id()
    # Up to num_slots winners; the agent may appear as one of them.
    results = [(own, 0, 8.5), ("other_a", 1, 4.0),
               ("other_b", 2, 2.0), ("other_c", 3, 0.0)]
    a.notify_round_results(results)


@pytest.mark.parametrize("name,cls", ALL_AGENT_FACTORIES)
def test_notify_single_winner_no_raise(name, cls):
    a = cls()
    a.start_simulation(2, NUM_SLOTS, make_ctr(NUM_SLOTS), 40.0, 10000.0, 3000)
    a.notify_round_results([("someone", 0, 0.0)])  # last-ranked pays 0.0


@pytest.mark.parametrize("name,cls", ALL_AGENT_FACTORIES)
def test_notify_malformed_short_tuples_no_raise(name, cls):
    # Robustness beyond the strict server contract (the server always sends
    # well-formed 3-tuples). A defensive agent survives short/empty tuples.
    a = cls()
    a.start_simulation(5, NUM_SLOTS, make_ctr(NUM_SLOTS), 40.0, 10000.0, 3000)
    a.notify_round_results([(a.get_id(), 0)])  # short tuple
    a.notify_round_results([()])               # empty tuple


# --------------------------------------------------------------------------- #
# Full-simulation loop: bid + notify every round for T rounds                  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,cls", ALL_AGENT_FACTORIES)
def test_full_round_loop_no_crash_and_valid_bids(name, cls):
    rng = random.Random(1234)
    T = 200
    value = 55.0
    budget = float("inf") if cls is BiddingAgent1 else 10000.0
    a = cls()
    a.start_simulation(5, NUM_SLOTS, make_ctr(NUM_SLOTS), value, budget, T)
    live = budget
    for t in range(T):
        bid = a.get_bid(live)
        assert bid_is_wellbehaved(bid, live), (
            f"{name} round {t}: bad bid {bid!r} for live budget {live}")
        # Build a plausible current-round result set of winners.
        winners = [(a.get_id(), 0, round(rng.uniform(0, value), 3))]
        for s in range(1, NUM_SLOTS):
            winners.append((f"rival_{s}", s, round(rng.uniform(0, value), 3)))
        a.notify_round_results(winners)
        # Emulate the server drawing down a finite budget slowly.
        if math.isfinite(live):
            live = max(0.0, live - 0.5)
            if live <= 0:
                break


# --------------------------------------------------------------------------- #
# Latency: each call well under the 50ms TIME_CAP                              #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name,cls", ALL_AGENT_FACTORIES)
def test_get_bid_latency_under_cap(name, cls):
    budget = float("inf") if cls is BiddingAgent1 else 10000.0
    a = cls()
    a.start_simulation(5, NUM_SLOTS, make_ctr(NUM_SLOTS), 60.0, budget, 3000)
    a.get_bid(budget)  # warm up (lazy init / imports)
    worst = 0.0
    for _ in range(50):
        t0 = time.perf_counter()
        a.get_bid(budget)
        worst = max(worst, time.perf_counter() - t0)
    assert worst < LATENCY_BUDGET, (
        f"{name}.get_bid worst-case {worst*1000:.2f}ms exceeds "
        f"{LATENCY_BUDGET*1000:.0f}ms (server cap {TIME_CAP*1000:.0f}ms)")


@pytest.mark.parametrize("name,cls", ALL_AGENT_FACTORIES)
def test_notify_latency_under_cap(name, cls):
    budget = float("inf") if cls is BiddingAgent1 else 10000.0
    a = cls()
    a.start_simulation(5, NUM_SLOTS, make_ctr(NUM_SLOTS), 60.0, budget, 3000)
    results = [(a.get_id(), 0, 5.0), ("r1", 1, 3.0), ("r2", 2, 1.0), ("r3", 3, 0.0)]
    a.notify_round_results(results)  # warm up
    worst = 0.0
    for _ in range(50):
        t0 = time.perf_counter()
        a.notify_round_results(results)
        worst = max(worst, time.perf_counter() - t0)
    assert worst < LATENCY_BUDGET, (
        f"{name}.notify_round_results worst-case {worst*1000:.2f}ms exceeds "
        f"{LATENCY_BUDGET*1000:.0f}ms")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
