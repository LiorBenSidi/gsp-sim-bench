"""ENFORCE_TIME_CAP=True compliance (TA announcement 2026-07-16: "run your final check with True
before submitting"). Under real enforcement each get_bid / notify_round_results call is capped at
CONSTANTS.TIME_CAP (0.05s) and an overrun DISQUALIFIES the agent for the rest of that simulation
(bid 0, utility divided by the FULL T). This test runs a few full-T sims with enforcement ON for
BOTH agents and asserts neither is ever disqualified -- i.e. we stay well under the cap in the
grading configuration, not just in fast mode.
"""
import io
import random
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "fixtures"))
sys.path.insert(0, str(ROOT / "src"))
import CONSTANTS  # noqa: E402
import id_dummy_1  # noqa: E402
import id_dummy_2  # noqa: E402
import id_dummy_3  # noqa: E402
import server as grader  # noqa: E402

from hw3.agent1 import BiddingAgent1  # noqa: E402
from hw3.agent2 import BiddingAgent2  # noqa: E402

SEEDS = 5  # a few full-T sims per task -- enforcement uses threads (slow), so keep it small


def _run_enforced(our_cls, dummies, enforce_budget):
    """Run SEEDS full-T sims with ENFORCE_TIME_CAP=True; return the captured server output."""
    prev = CONSTANTS.ENFORCE_TIME_CAP
    CONSTANTS.ENFORCE_TIME_CAP = True
    buf = io.StringIO()
    try:
        for s in range(SEEDS):
            random.seed(s)
            field = [our_cls()] + [d() for d in dummies]
            for i, a in enumerate(field):
                a.id = "ours" if i == 0 else f"dummy{i}"
            with redirect_stdout(buf):
                grader.run_simulation(field, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS,
                                      enforce_budget=enforce_budget)
    finally:
        CONSTANTS.ENFORCE_TIME_CAP = prev
    return buf.getvalue()


def test_agent1_not_disqualified_under_enforcement():
    out = _run_enforced(BiddingAgent1, [id_dummy_1.BiddingAgent1, id_dummy_2.BiddingAgent1,
                                        id_dummy_3.BiddingAgent1], enforce_budget=False)
    assert "disqualif" not in out.lower(), f"Agent 1 was disqualified under ENFORCE_TIME_CAP=True:\n{out}"


def test_agent2_not_disqualified_under_enforcement():
    out = _run_enforced(BiddingAgent2, [id_dummy_1.BiddingAgent2, id_dummy_2.BiddingAgent2,
                                        id_dummy_3.BiddingAgent2], enforce_budget=True)
    assert "disqualif" not in out.lower(), f"Agent 2 was disqualified under ENFORCE_TIME_CAP=True:\n{out}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
