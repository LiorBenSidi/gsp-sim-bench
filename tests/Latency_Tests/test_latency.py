"""The 50ms/call cap is grade-critical (a single breach -> removed for the sim, utility / T).
Drive each agent for the full T=3000 rounds with a realistic 4-tuple history and assert the
worst single get_bid/notify call stays well under the cap (margin: <15ms, since the grading
machine is loaded)."""
import time

from hw3.agent1 import BiddingAgent1
from hw3.agent2 import BiddingAgent2

CTR = [0.7, 0.42, 0.25, 0.15]
CAP = 0.015  # 15ms margin under the 50ms grader cap


def _rotating_histories(t_rounds=3000, n_ids=13):
    """Worst case for the smart cost-raise: the 4 slot winners rotate through n_ids distinct
    agents, so the agent's cross-round bid tracker (_bid_by_id) grows to its max, and 'ours'
    lands sometimes on top (bid hidden) and sometimes below (bid observed). A fixed history would
    never exercise that growth."""
    ids = [f"a{i}" for i in range(n_ids)]
    hists = []
    for r in range(t_rounds):
        rot = [ids[(r + k) % n_ids] for k in range(4)]
        rot[1 if r % 2 else 0] = "ours"
        hists.append([(rot[0], 0, 30.0), (rot[1], 1, 12.0), (rot[2], 2, 4.0), (rot[3], 3, 0.0)])
    return hists


def _worst_call_time(cls, budget):
    a = cls()
    a.start_simulation(13, 4, CTR, 50.0, budget, 3000)  # many-agent -> larger tracked id-set
    try:
        a.id = "ours"  # so it recognises itself in the synthetic history
    except Exception:
        pass
    hists = _rotating_histories()
    worst = 0.0
    for r in range(3000):
        t = time.perf_counter(); a.get_bid(budget); worst = max(worst, time.perf_counter() - t)
        t = time.perf_counter(); a.notify_round_results(hists[r]); worst = max(worst, time.perf_counter() - t)
    return worst


def test_agent1_latency_under_cap():
    worst = _worst_call_time(BiddingAgent1, 1e12)
    assert worst < CAP, f"BiddingAgent1 worst call {worst * 1000:.3f}ms exceeds {CAP * 1000:.0f}ms"


def test_agent2_latency_under_cap():
    worst = _worst_call_time(BiddingAgent2, 10000.0)
    assert worst < CAP, f"BiddingAgent2 worst call {worst * 1000:.3f}ms exceeds {CAP * 1000:.0f}ms"
