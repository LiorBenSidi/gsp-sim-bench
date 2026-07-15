"""Sanity for the conservative-raise challenger RobustRaiseAgent1 (harness/robust_raise_agent.py) --
a candidate under evaluation, not shipped. Checks per-rival typing, that the cost-raise fires ONLY
against a directly-observed CONSTANT top and never overtakes, never fires vs a stochastic top, the
grader contract via the real server, per-sim reset, and latency."""
import math
import random
import sys
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "fixtures"))

import CONSTANTS  # noqa: E402
import id_dummy_1  # noqa: E402
import id_dummy_2  # noqa: E402
import id_dummy_3  # noqa: E402
import server as grader  # noqa: E402
from robust_raise_agent import RobustRaiseAgent1  # noqa: E402

CTR = [0.7, 0.42, 0.25, 0.15]


def _start(a, value=50.0):
    a.start_simulation(4, 4, CTR, value, float("inf"), 3000)


def test_typing_constant_stochastic_unknown():
    a = RobustRaiseAgent1(); _start(a)
    for _ in range(8):                                 # c sits in slot 1 at a CONSTANT bid 30
        a.notify_round_results([("x", 0, 30.0), ("c", 1, 20.0), ("z", 2, 5.0)])
    assert a._rival_type("c") == "CONSTANT"
    assert a._rival_type("unseen") == "UNKNOWN"        # never observed
    b = RobustRaiseAgent1(); _start(b)
    for i in range(12):                                # widely varying reconstructed bid
        b.notify_round_results([("x", 0, 10.0 + 3 * i), ("c", 1, 5.0), ("z", 2, 1.0)])
    assert b._rival_type("c") == "STOCHASTIC"


def _inject_top(a, top_bid=30.0, top_sd=0.0, low=5.0, my_round=20):
    """Put the agent in a slot-1-optimal state with a directly-observed top 'c'."""
    a._round = my_round
    n = 10
    a._stats = {
        "c": [n, top_bid * n, (top_bid ** 2 + top_sd ** 2) * n, top_bid + top_sd, top_bid],
        "lo": [n, low * n, low * low * n, low, low],
    }
    a._recent = {"c": deque([top_bid] * 8, maxlen=8), "lo": deque([low] * 8, maxlen=8)}
    a._obs_round = {"c": my_round - 1, "lo": my_round - 1}
    a._top0 = "c"


def test_raise_fires_against_constant_top_without_overtaking():
    a = RobustRaiseAgent1(delta_frac=0.0); _start(a, value=50.0)
    _inject_top(a, top_bid=30.0, top_sd=0.0)
    bid = a.get_bid(float("inf"))
    assert a._raise_fires == 1
    assert bid < 30.0                                  # never overtakes the top
    assert abs(bid - (30.0 - 1e-3)) < 1e-2             # sits just under it


def test_never_raises_against_stochastic_top():
    a = RobustRaiseAgent1(delta_frac=0.0); _start(a, value=50.0)
    _inject_top(a, top_bid=30.0, top_sd=9.0)           # high variance -> STOCHASTIC
    a.get_bid(float("inf"))
    assert a._raise_fires == 0


def test_warmup_fence_no_raise_early():
    a = RobustRaiseAgent1(delta_frac=0.0); _start(a, value=50.0)
    _inject_top(a, top_bid=30.0, top_sd=0.0, my_round=5)   # <= 10 -> fenced
    a.get_bid(float("inf"))
    assert a._raise_fires == 0


def test_per_sim_reset_clears_state():
    a = RobustRaiseAgent1(); _start(a)
    a.notify_round_results([("x", 0, 30.0), ("c", 1, 20.0)])
    a._top0 = "x"; a._raise_fires = 5
    _start(a, value=60.0)
    assert a._obs_round == {} and a._recent == {} and a._top0 is None
    assert a._raise_fires == 0 and a._round == 0 and a.value == 60.0


def test_runs_through_real_server_finite_and_bounded():
    random.seed(0)
    a = RobustRaiseAgent1(); a.id = "ours"
    field = [a,
             _l(id_dummy_1.BiddingAgent1, "d1"),
             _l(id_dummy_2.BiddingAgent1, "d2"),
             _l(id_dummy_3.BiddingAgent1, "d3")]
    u = grader.run_simulation(field, CONSTANTS.NUM_SLOTS, 200, enforce_budget=False)
    assert "ours" in u and math.isfinite(u["ours"])


def test_latency_under_cap():
    a = RobustRaiseAgent1(); _start(a)
    for _ in range(60):
        a.notify_round_results([("x", 0, 30.0), ("c", 1, 20.0), ("d", 2, 5.0)])
    worst = 0.0
    for _ in range(500):
        t = time.perf_counter()
        a.get_bid(float("inf"))
        worst = max(worst, time.perf_counter() - t)
    assert worst < 0.015, f"worst get_bid {worst*1000:.2f}ms exceeds 15ms margin"


def _l(cls, uid):
    a = cls(); a.id = uid
    return a
