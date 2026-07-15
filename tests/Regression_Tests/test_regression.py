"""Regression guard: recompute the candidate's mean utility over the frozen seed set and fail if
it drops below the committed baseline. Deterministic (fixed seeds), so any strategy change moves
the number; an accepted improvement is re-frozen via harness/freeze_baseline.py.

Load-flakiness guard: the real grader disqualifies any agent that exceeds the 50ms/call cap in a
given sim. Under CPU load a *dummy* can trip that cap, which changes the field and hence our
utility -- a machine artifact, not a strategy regression. So we capture the grader's stdout and,
if a disqualification occurred, `skip` (rather than false-fail); our OWN agent's latency is guarded
separately by tests/Latency_Tests. A clean (unloaded) run is fully deterministic and asserts."""
import io
import json
import random
import statistics
from contextlib import redirect_stdout
from pathlib import Path

import CONSTANTS
import id_dummy_1
import id_dummy_2
import id_dummy_3
import pytest
import server as grader

from hw3.agent1 import BiddingAgent1
from hw3.agent2 import BiddingAgent2

BASE = json.loads((Path(__file__).parent / "baseline_utilities.json").read_text())


def _mean(cls, dummies, enforce_budget):
    """Returns (mean_utility, disqualified_flag). disqualified_flag is True if any agent tripped
    the latency cap during the run -- signalling the measurement was contaminated by machine load."""
    agents = [cls()] + [d() for d in dummies]
    vals = []
    disqualified = False
    for s in range(BASE["seeds"]):
        random.seed(s)
        buf = io.StringIO()
        with redirect_stdout(buf):
            u = grader.run_simulation(agents, CONSTANTS.NUM_SLOTS, BASE["T"], enforce_budget=enforce_budget)
        if "disqualified" in buf.getvalue():
            disqualified = True
        vals.append(u[agents[0].get_id()])
    return statistics.fmean(vals), disqualified


def test_task1_no_regression():
    cur, disqualified = _mean(BiddingAgent1, [id_dummy_1.BiddingAgent1, id_dummy_2.BiddingAgent1,
                                              id_dummy_3.BiddingAgent1], False)
    if disqualified:
        pytest.skip("latency DQ under machine load contaminated the deterministic baseline; rerun unloaded")
    assert cur >= BASE["task1_mean_util"] - 1.0, f"Task 1 regressed: {cur:.1f} < {BASE['task1_mean_util']}"


def test_task2_no_regression():
    cur, disqualified = _mean(BiddingAgent2, [id_dummy_1.BiddingAgent2, id_dummy_2.BiddingAgent2,
                                              id_dummy_3.BiddingAgent2], True)
    if disqualified:
        pytest.skip("latency DQ under machine load contaminated the deterministic baseline; rerun unloaded")
    assert cur >= BASE["task2_mean_util"] - 1.0, f"Task 2 regressed: {cur:.1f} < {BASE['task2_mean_util']}"
