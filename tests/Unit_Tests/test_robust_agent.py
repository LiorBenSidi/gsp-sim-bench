"""Sanity for the challenger RobustAgent1 (harness/robust_agent.py) -- a candidate under evaluation,
not the shipped agent. Checks the grader contract (bounded finite bids, per-sim reset) and that it
actually accumulates a rival's bid distribution across rounds."""
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "fixtures"))

import CONSTANTS  # noqa: E402
import id_dummy_1  # noqa: E402
import id_dummy_2  # noqa: E402
import id_dummy_3  # noqa: E402
import server as grader  # noqa: E402
from robust_agent import RobustAgent1  # noqa: E402


def _l(cls, uid):
    a = cls()
    a.id = uid
    return a


def test_runs_through_real_server_finite():
    random.seed(0)
    field = [_l(RobustAgent1, "ours"),
             _l(id_dummy_1.BiddingAgent1, "d1"),
             _l(id_dummy_2.BiddingAgent1, "d2"),
             _l(id_dummy_3.BiddingAgent1, "d3")]
    u = grader.run_simulation(field, CONSTANTS.NUM_SLOTS, 200, enforce_budget=False)
    assert "ours" in u and math.isfinite(u["ours"])


def test_bids_finite_and_never_above_value():
    a = RobustAgent1()
    a.start_simulation(4, 4, [0.7, 0.42, 0.25, 0.15], value=50.0, total_budget=float("inf"), T=100)
    assert 0.0 <= a.get_bid(float("inf")) <= 50.0  # cold open <= value
    for _ in range(30):
        # rival d2 sits in slot 1 at price 20 (so its reconstructed bid == price of slot 0 == 30)
        a.notify_round_results([("x", 0, 30.0), ("d2", 1, 20.0), ("y", 2, 5.0)])
        b = a.get_bid(float("inf"))
        assert isinstance(b, float) and math.isfinite(b) and 0.0 <= b <= 50.0


def test_per_sim_reset_clears_stats():
    a = RobustAgent1()
    a.start_simulation(4, 4, [0.7, 0.42, 0.25, 0.15], 50.0, float("inf"), 100)
    a.notify_round_results([("x", 0, 30.0), ("d2", 1, 20.0)])
    assert a._stats  # learned something
    a.start_simulation(4, 4, [0.7, 0.42, 0.25, 0.15], 60.0, float("inf"), 100)
    assert a._stats == {} and a._round == 0 and a.value == 60.0


def test_accumulates_rival_bid_distribution():
    a = RobustAgent1()
    a.start_simulation(4, 4, [0.7, 0.42, 0.25, 0.15], 50.0, float("inf"), 100)
    # d2 in slot 1 each round; its bid == price of slot 0 == 30 -> mean should converge to 30
    for _ in range(20):
        a.notify_round_results([("top", 0, 30.0), ("d2", 1, 20.0), ("z", 2, 5.0)])
    c, tot, _sq, mx, last = a._stats["d2"]
    assert c == 20 and abs(tot / c - 30.0) < 1e-9 and mx == 30.0 and last == 30.0
