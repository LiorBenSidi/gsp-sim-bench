"""TRUST GATE for harness/replica_sim.py: its Task-1 utilities must be BYTE-IDENTICAL to the real
fixtures/server.py under the same fixed seeds. If this ever fails, no replica-derived number is
evidence. Compares via float.hex() (distinguishes even -0.0) — not approx, not rounded ==.

Runs the real server (ThreadPool) at full T on a few seeds per experiment block, so it is slower
than the rest of the suite (~tens of seconds). Override the seed set with HW3_PARITY_SEEDS=comma,list.
"""
import contextlib
import io
import os
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "fixtures"))
sys.path.insert(0, str(ROOT / "src"))

import CONSTANTS  # noqa: E402
import id_dummy_1  # noqa: E402
import id_dummy_2  # noqa: E402
import id_dummy_3  # noqa: E402
import server as grader  # noqa: E402
from margin_agent import BindingMarginAgent1  # noqa: E402
from replica_sim import run_simulation_replica  # noqa: E402
from robust_agent import RobustAgent1  # noqa: E402
from robust_raise_agent import RobustRaiseAgent1  # noqa: E402

from hw3.agent1 import BiddingAgent1 as Champion  # noqa: E402

# a couple of seeds from each experiment block (screen@0 / confirm@200000 / holdout@400000)
_DEFAULT = list(range(0, 2)) + list(range(200_000, 200_002)) + list(range(400_000, 400_002))
SEEDS = ([int(x) for x in os.environ["HW3_PARITY_SEEDS"].split(",")]
         if os.environ.get("HW3_PARITY_SEEDS") else _DEFAULT)


def _field(cand_cls):
    c = cand_cls(); c.id = "ours"
    d1 = id_dummy_1.BiddingAgent1(); d1.id = "d1"
    d2 = id_dummy_2.BiddingAgent1(); d2.id = "d2"
    d3 = id_dummy_3.BiddingAgent1(); d3.id = "d3"
    return [c, d1, d2, d3]


@pytest.mark.parametrize("cand_cls,label", [(RobustAgent1, "robust"), (RobustRaiseAgent1, "rraise"),
                                            (BindingMarginAgent1, "bindC"), (Champion, "champion")])
def test_replica_byte_parity(cand_cls, label):
    ns, t = CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS

    real_field = _field(cand_cls)   # built ONCE, reused across seeds (mirrors run_field)
    real = {}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for s in SEEDS:
            random.seed(s)
            real[s] = grader.run_simulation(real_field, ns, t, enforce_budget=False)
    out = buf.getvalue().lower()
    assert "disqualif" not in out and "exceed" not in out, \
        f"[{label}] the real run hit a timeout/disqualify — replica's no-timeout assumption is invalid here"

    repl_field = _field(cand_cls)
    repl = {}
    for s in SEEDS:
        random.seed(s)
        repl[s] = run_simulation_replica(repl_field, ns, t, enforce_budget=False)

    for s in SEEDS:
        ru, pu = real[s], repl[s]
        assert set(ru) == set(pu) == {"ours", "d1", "d2", "d3"}, f"[{label}] seed {s}: key set mismatch"
        for aid in ("ours", "d1", "d2", "d3"):
            assert ru[aid].hex() == pu[aid].hex(), (
                f"[{label}] seed {s} agent {aid}: real {ru[aid]!r} ({ru[aid].hex()}) "
                f"!= replica {pu[aid]!r} ({pu[aid].hex()})")
