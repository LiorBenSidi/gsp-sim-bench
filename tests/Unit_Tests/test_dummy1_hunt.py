"""Unit tests for the d1-hunt candidates (harness/dummy1_hunt.py).

Two guarantees:
1. TunableDescentAgent1(tol_frac=0, eps=_EPS) is BYTE-IDENTICAL to the shipped DescentAgent1 --
   the tuning knobs default to a no-op, so any screen delta is the knob, not a reimplementation
   drift. Compared over a full replica simulation via float.hex().
2. ConstSuppressAgent1's suppression term credits ONLY constant-typed rivals; a stochastic rival
   contributes 0 (so dummy2 handling stays pure EU).
"""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "harness", ROOT / "fixtures", ROOT / "src"):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import CONSTANTS  # noqa: E402
import id_dummy_1  # noqa: E402
import id_dummy_2  # noqa: E402
import id_dummy_3  # noqa: E402
from dummy1_hunt import (  # noqa: E402
    ConstSuppressAgent1,
    DescentRaiseAgent1,
    DirectD1MarginAgent1,
    TunableDescentAgent1,
)
from margin_agent import DescentAgent1  # noqa: E402
from replica_sim import run_simulation_replica  # noqa: E402
from robust_agent import _EPS  # noqa: E402

NS, T = CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS


def _field(cls):
    a = cls(); a.id = "ours"
    d1 = id_dummy_1.BiddingAgent1(); d1.id = "d1"
    d2 = id_dummy_2.BiddingAgent1(); d2.id = "d2"
    d3 = id_dummy_3.BiddingAgent1(); d3.id = "d3"
    return [a, d1, d2, d3]


def test_tunable_descent_noop_matches_shipped_descent_byte_for_byte():
    # tol_frac=0, eps=_EPS -> must be indistinguishable from DescentAgent1 over a full sim.
    for s in (0, 7, 200_000, 400_000):
        random.seed(s)
        base = run_simulation_replica(_field(DescentAgent1), NS, T, enforce_budget=False)
        random.seed(s)
        tuned = run_simulation_replica(
            _field(lambda: TunableDescentAgent1(tol_frac=0.0, eps=_EPS)), NS, T, enforce_budget=False)
        for k in ("ours", "d1", "d2", "d3"):
            assert base[k].hex() == tuned[k].hex(), (
                f"seed {s} agent {k}: tuned no-op {tuned[k]!r} != shipped descent {base[k]!r}")


def test_const_suppress_credits_only_constant_rivals():
    a = ConstSuppressAgent1(w=0.2)
    a.start_simulation(4, NS, [0.7, 0.42, 0.25, 0.15], 50.0, float("inf"), 3000)
    # Reconstruction: the agent in slot k>=1 bid == the price of slot k-1. Keep c1 in slot 1 with a
    # FIXED slot-0 price (10.0) -> c1's reconstructed bid is constant 10.0. Keep s1 in slot 2 and
    # VARY the slot-1 price -> s1's reconstructed bid swings 2<->8 (high variance).
    for i in range(15):
        p1 = 2.0 + 6.0 * (i % 2)   # slot-1 price -> s1's (slot-2) reconstructed bid: 2 or 8
        a.notify_round_results([("ours", 0, 10.0), ("c1", 1, p1), ("s1", 2, 1.0), ("z", 3, 0.0)])
    assert a._rival_type("c1") == "CONSTANT"
    assert a._rival_type("s1") == "STOCHASTIC"
    # Suppression term must count c1's spend and IGNORE s1's spend.
    seated = [("c1", 0, 9.0), ("s1", 1, 5.0)]
    ctr = a.CTR_list
    assert abs(a._suppr(seated) - 9.0 * ctr[0]) < 1e-12   # only c1 credited, not s1
    # No constant rival seated -> zero suppression (pure EU).
    assert a._suppr([("s1", 0, 7.0)]) == 0.0


def test_direct_d1_suppr_is_negative_known_value_utility_of_constant_rivals_only():
    a = DirectD1MarginAgent1(lam=0.5, shade=0.85)
    a.start_simulation(4, NS, [0.7, 0.42, 0.25, 0.15], 50.0, float("inf"), 3000)
    # Type c1 CONSTANT (steady reconstructed bid 8.5 -> vhat = 8.5/0.85 = 10.0) and s1 STOCHASTIC.
    for i in range(15):
        p1 = 2.0 + 6.0 * (i % 2)   # slot-1 price -> s1's (slot-2) bid swings 2<->8
        a.notify_round_results([("ours", 0, 8.5), ("c1", 1, p1), ("s1", 2, 1.0), ("z", 3, 0.0)])
    assert a._rival_type("c1") == "CONSTANT"
    assert a._rival_type("s1") == "STOCHASTIC"
    # suppr must be -(c1's exact utility): vhat=10.0, seated in slot 0 at price 6.0 -> (10-6)*0.7=2.8.
    # s1 (stochastic) contributes nothing even though seated.
    ctr = a.CTR_list
    assert abs(a._suppr([("c1", 0, 6.0), ("s1", 1, 5.0)]) - (-(10.0 - 6.0) * ctr[0])) < 1e-9
    # objective weight w == lam (so J = own + lam*suppr = own - lam*d1_util).
    assert a.w == 0.5


def test_hybrid_cost_raise_fires_below_constant_top_without_overtaking():
    # Value 50; a constant rival d1 identified at bid 40 (its bid = the slot-0 price it sits under);
    # cheap rival below. EU prefers slot 1 (below d1: (50-5)*0.42=18.9 > slot-0 (50-40)*0.7=7), so
    # the cost-raise branch should fire: raise toward just under 40 (d1 then pays ~40) WITHOUT
    # overtaking into slot 0, and WITHOUT changing our own price (set by the agent below us).
    a = DescentRaiseAgent1()
    a.start_simulation(4, NS, [0.7, 0.42, 0.25, 0.15], 50.0, float("inf"), 3000)
    # Interleave get_bid/notify past WARMUP (_round only advances in get_bid) so the raise gate opens.
    for _ in range(15):
        a.get_bid(float("inf"))
        # ours slot 0 @ price 40 -> d1 (slot 1) reconstructed bid = 40 (constant); cheap slot 2.
        a.notify_round_results([("ours", 0, 40.0), ("d1", 1, 5.0), ("cheap", 2, 0.0)])
    assert a._rival_type("d1") == "CONSTANT"
    bid = a.get_bid(float("inf"))
    assert bid < 40.0, f"cost-raise must NOT overtake d1's bid (40); got {bid}"
    assert bid > 39.0, f"cost-raise should sit JUST under d1's bid (~39.999); got {bid}"
    assert getattr(a, "_raises", 0) >= 1, "cost-raise branch did not fire"
