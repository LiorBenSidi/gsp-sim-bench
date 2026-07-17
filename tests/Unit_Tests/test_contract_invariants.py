"""Grader-contract invariants the agents must ALWAYS satisfy (independent of the strategy):
a returned bid is a plain finite float in [0, budget]; get_id is a non-empty string; the free
floor / negative-utility rules hold; and start_simulation fully resets per-sim state (server
reuses one instance across all simulations). These are facts about the contract, not the
bidding logic, so they are safe to assert directly."""
import math

from hw3.agent1 import BiddingAgent1
from hw3.agent2 import BiddingAgent2
from hw3.strategy import best_response, choose_bid, reconstruct_rivals

CTR = [0.7, 0.42, 0.25, 0.15]
NUM_SLOTS = 4


def _finite_float_in(x, lo, hi):
    return isinstance(x, float) and not isinstance(x, bool) and math.isfinite(x) and lo - 1e-9 <= x <= hi + 1e-9


def _drive(agent, value, budget, T, rounds, history_seq):
    """Run start_simulation + a few get_bid/notify cycles; return the list of bids."""
    agent.start_simulation(4, NUM_SLOTS, CTR, value, budget, T)
    bids = []
    for r in range(rounds):
        b = agent.get_bid(budget)
        bids.append(b)
        agent.notify_round_results(history_seq[r % len(history_seq)])
    return bids


HISTORY = [
    [],  # round 0: no info
    [("x", 0, 30.0), ("y", 1, 12.0), ("z", 2, 4.0), ("ours", 3, 0.0)],
    [("ours", 0, 40.0), ("x", 1, 20.0), ("y", 2, 6.0), ("z", 3, 0.0)],
]


def test_agent1_bids_are_finite_floats_and_nonneg():
    a = BiddingAgent1()
    for v in (0.0, 1.0, 37.5, 100.0):
        for b in _drive(a, v, float("inf"), 3000, 6, HISTORY):
            assert _finite_float_in(b, 0.0, float("inf"))
            assert b <= v + 1e-9  # never bids above own value


def test_agent2_bids_respect_budget_ceiling():
    a = BiddingAgent2()
    budget = 10000.0
    for v in (0.0, 5.0, 50.0, 100.0):
        for b in _drive(a, v, budget, 3000, 6, HISTORY):
            assert _finite_float_in(b, 0.0, budget)
            assert b <= v + 1e-9


def test_agent2_bids_zero_when_budget_exhausted():
    a = BiddingAgent2()
    a.start_simulation(4, NUM_SLOTS, CTR, 50.0, 10000.0, 3000)
    assert a.get_bid(0.0) == 0.0
    assert a.get_bid(-5.0) == 0.0


def test_get_id_is_nonempty_string_and_stable():
    for cls in (BiddingAgent1, BiddingAgent2):
        a = cls()
        assert isinstance(a.get_id(), str) and a.get_id()
        assert a.get_id() == a.get_id()


def test_choose_bid_never_targets_negative_utility_slot():
    # All slot prices exceed value -> the only non-losing action is not to compete (bid 0-ish).
    hist = [("x", 0, 90.0), ("y", 1, 85.0), ("z", 2, 80.0)]
    bid = choose_bid(10.0, CTR, NUM_SLOTS, hist, "ours", 10.0)
    assert _finite_float_in(bid, 0.0, 10.0)
    # Bidding at most our value guarantees we never pay more than value for any slot we win.


def test_best_response_respects_budget_cap():
    # A profitable top slot would want ~5, but a tiny budget must hard-cap the bid at budget.
    # (Tests the strategy fn directly -- both agents also re-clamp, which masks this otherwise.)
    bid = best_response(100.0, CTR, [5.0, 2.0], budget=3.0, num_slots=NUM_SLOTS)
    assert bid <= 3.0 + 1e-9 and bid >= 0.0


def test_best_response_stays_finite_and_nonneg_without_rivals():
    # Defensive: an empty rivals list must never be indexed and never yield a bad float.
    bid = best_response(50.0, CTR, [], budget=50.0, num_slots=NUM_SLOTS)
    assert _finite_float_in(bid, 0.0, 50.0)


def test_best_response_never_overbids_into_a_costlier_slot():
    # rivals=[89, 20]: slot 1 (price 20) is the profit-max seat. The bid must secure slot 1 --
    # strictly above the displaced rival's 20 and strictly below the 89 above us, so we never
    # overtake into the more expensive (slot 0) seat.
    bid = best_response(100.0, CTR, [89.0, 20.0], budget=1e12, num_slots=NUM_SLOTS)
    assert 20.0 < bid < 89.0


def test_reconstruct_rivals_excludes_self():
    hist = [("ours", 0, 30.0), ("y", 1, 12.0), ("z", 2, 4.0)]
    rivals = reconstruct_rivals(hist, "ours", NUM_SLOTS)
    # ours occupied slot 0; the two rivals (slots 1,2) must be present, ours excluded.
    assert len(rivals) == 2
    assert all(isinstance(x, float) and math.isfinite(x) for x in rivals)
    assert rivals == sorted(rivals, reverse=True)


def test_start_simulation_resets_state_between_sims():
    # The grader reuses one instance across sims -> a fresh start_simulation must wipe history,
    # round counter, and budget so a big first sim never bleeds into a small second one.
    a = BiddingAgent2()
    a.start_simulation(4, NUM_SLOTS, CTR, 80.0, 10000.0, 3000)
    for _ in range(50):
        a.get_bid(5000.0)
        a.notify_round_results(HISTORY[1])
    a.start_simulation(4, NUM_SLOTS, CTR, 20.0, 9000.0, 3000)
    assert a._round == 0
    assert a._last_results == []
    assert a.value == 20.0
    assert a.budget_remaining == 9000.0
    # cold-start bid uses only value (no stale history)
    assert _finite_float_in(a.get_bid(9000.0), 0.0, 9000.0)
