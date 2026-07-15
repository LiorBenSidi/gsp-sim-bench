"""Sanity for the margin-objective challengers (harness/margin_agent.py, Options A/B/C) --
candidates under evaluation, not shipped. The behavioral tests assert HAND-COMPUTED GSP outcomes
(values worked out from the auction rules, not from running the implementation)."""
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
from margin_agent import BindingMarginAgent1, DescentAgent1, MarginAgent1, gsp_alloc  # noqa: E402

CTR = [0.7, 0.42, 0.25, 0.15]


def _start(a, value=50.0):
    a.start_simulation(4, 4, CTR, value, float("inf"), 3000)


def _const_stats(a, top=42.5, low=5.0, n=10, my_round=20):
    """Two constant rivals: 'c' at `top`, 'lo' at `low`; agent warmed past WARMUP."""
    a._round = my_round
    a._stats = {"c": [n, top * n, top * top * n, top, top],
                "lo": [n, low * n, low * low * n, low, low]}
    a._recent = {"c": deque([top] * 8, maxlen=8), "lo": deque([low] * 8, maxlen=8)}
    a._obs_round = {"c": my_round - 1, "lo": my_round - 1}


# ---------- gsp_alloc against a brute-force reference ----------

def _brute(my_bid, rivals, value, ctr, ns):
    seq = sorted([("__me__", my_bid)] + rivals, key=lambda t: t[1], reverse=True)
    # stable sort keeps us BEFORE equal-bid rivals only if inserted first; enforce the
    # we-win-ties rule explicitly like the agent does:
    seq = ([t for t in rivals if t[1] > my_bid] + [("__me__", my_bid)]
           + [t for t in rivals if t[1] <= my_bid])
    ours, seated = 0.0, []
    for i, (rid, _b) in enumerate(seq[:min(ns, len(ctr))]):
        price = seq[i + 1][1] if i + 1 < len(seq) else 0.0
        if rid == "__me__":
            ours = (value - price) * ctr[i]
        else:
            seated.append((rid, i, price))
    return ours, seated


def test_gsp_alloc_matches_bruteforce():
    rivals = sorted([("a", 40.0), ("b", 17.5), ("d", 3.0)], key=lambda t: t[1], reverse=True)
    for my_bid in (0.0, 2.9, 3.0, 10.0, 17.5, 30.0, 40.0, 45.0):
        got = gsp_alloc(my_bid, rivals, 50.0, CTR, 4)
        want = _brute(my_bid, rivals, 50.0, CTR, 4)
        assert got == want, f"my_bid={my_bid}: {got} != {want}"


# ---------- Option A: the suppression seat emerges from the objective ----------

def test_marginA_zero_w_takes_cheap_seat():
    # v=50 vs constant 42.5 and 5. EU: slot1 paying 5 -> (50-5)*.42=18.9 beats slot0 paying
    # 42.5 -> 5.25. Pure EU (w=0) must take SLOT 1 (any bid strictly between the two rivals is
    # EU-equivalent -- our price is set by the rival below -- so assert the seat, not one bid).
    a = MarginAgent1(w=0.0); _start(a); _const_stats(a)
    bid = a.get_bid(float("inf"))
    assert 5.0 < bid < 42.5


def test_marginA_positive_w_raises_top_cost_for_free():
    # Same config, w=1: bidding 42.499 keeps our seat/price IDENTICAL (still slot 1 paying 5,
    # u=18.9) but makes 'c' pay OUR bid for slot 0 (spend 42.499*.7=29.7 vs 5.001*.7=3.5).
    # J(42.499)=48.6 > J(5.001)=22.4 -> the champion's cost-raise re-emerges from the objective.
    a = MarginAgent1(w=1.0); _start(a); _const_stats(a)
    bid = a.get_bid(float("inf"))
    assert abs(bid - (42.5 - 1e-3)) < 1e-6
    assert a._suppress_picks == 1                       # w changed the pick vs pure EU


# ---------- Option B: surgical descent below a constant top ----------

def test_descent_fires_when_margin_improves():
    # v=50 vs constant 20 ('c') and 5 ('lo'). EU seat = slot 0 (21 > 18.9). vhat=20/.85=23.53.
    # stay:    ours 21.0,  c at slot1 pays 5   -> util_c 7.78, margin 13.22
    # descend: ours 18.9,  c at slot0 pays r~20 -> util_c 2.47, margin 16.43  -> DESCEND.
    a = DescentAgent1(); _start(a); _const_stats(a, top=20.0)
    bid = a.get_bid(float("inf"))
    assert abs(bid - (20.0 - 1e-3)) < 1e-6
    assert a._descents == 1


def test_descent_stays_when_margin_wouldnt_improve():
    # Same but the below-price is HIGH (lo=18): staying at slot0 pays 20 -> ours 21.0 while
    # descending pays 18 -> ours only 13.44 and c's price barely moves relative to its CTR gain.
    # stay margin: 21 - (23.53-18)*.42 = 18.68; descend: 13.44 - (23.53-20)*.7 = 10.97 -> STAY.
    a = DescentAgent1(); _start(a); _const_stats(a, top=20.0, low=18.0)
    bid = a.get_bid(float("inf"))
    assert a._descents == 0
    assert bid > 20.0                                   # kept the EU seat above the top


# ---------- Option C: suppression aimed at the binding rival ----------

def test_bindC_weights_favor_binding_rival():
    a = BindingMarginAgent1(w=1.0); _start(a); a._round = 100
    seated = [("behind", 0, 10.0), ("ahead", 1, 10.0)]
    a._my_cum, a._riv_cum = 0.0, {"behind": 1000.0, "ahead": -1000.0}
    s1 = a._suppr(seated)                               # we trail 'behind' -> its slot-0 pay dominates
    a._riv_cum = {"behind": -1000.0, "ahead": 1000.0}
    s2 = a._suppr(seated)                               # now the binding rival sits at slot 1 (cheaper)
    assert s1 > s2


# ---------- contract / reset / latency for all three ----------

def _l(cls, uid):
    a = cls(); a.id = uid
    return a


def test_all_run_through_real_server_finite():
    for cls in (MarginAgent1, DescentAgent1, BindingMarginAgent1):
        random.seed(0)
        field = [_l(cls, "ours"), _l(id_dummy_1.BiddingAgent1, "d1"),
                 _l(id_dummy_2.BiddingAgent1, "d2"), _l(id_dummy_3.BiddingAgent1, "d3")]
        u = grader.run_simulation(field, CONSTANTS.NUM_SLOTS, 200, enforce_budget=False)
        assert math.isfinite(u["ours"]), cls.__name__


def test_per_sim_reset():
    a = BindingMarginAgent1(); _start(a)
    a.notify_round_results([("x", 0, 30.0), ("c", 1, 20.0)])
    a._my_cum = 7.0
    _start(a, value=60.0)
    assert a._stats == {} and a._recent == {} and a._obs_round == {}
    assert a._my_cum == 0.0 and a._riv_cum == {} and a.value == 60.0


def test_latency_under_cap():
    for cls in (MarginAgent1, BindingMarginAgent1):
        a = cls(); _start(a)
        for i in range(60):     # varied history -> multi-point scenarios (worst case)
            a.notify_round_results([("x", 0, 30.0 + i % 7), ("c", 1, 20.0 + i % 5), ("d", 2, 5.0 + i % 3)])
        worst = 0.0
        for _ in range(300):
            t = time.perf_counter()
            a.get_bid(float("inf"))
            worst = max(worst, time.perf_counter() - t)
        assert worst < 0.015, f"{cls.__name__}: worst get_bid {worst*1000:.2f}ms exceeds 15ms margin"
