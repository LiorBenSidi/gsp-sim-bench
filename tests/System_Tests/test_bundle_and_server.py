"""End-to-end contract: the bundler produces a single stdlib-only file with both classes that
loads in isolation and returns a correct get_id; and the src agents run through the REAL grader
(fixtures/server.py) to completion with finite utilities and only valid bids. This is a
smoke/contract test -- 'beats the dummies' is a strategy goal tracked by the CRN harness, not a
pass/fail here."""
import importlib.util
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_bundle_produces_loadable_stdlib_only_file(tmp_path):
    out = tmp_path / "id_123_456.py"
    subprocess.run(
        [sys.executable, str(ROOT / "build" / "bundle.py"), "--id1", "123", "--id2", "456",
         "--out", str(out)],
        check=True, cwd=str(ROOT), env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""},
    )
    text = out.read_text()
    assert "class BiddingAgent1" in text and "class BiddingAgent2" in text
    assert "hw3" not in text  # internal imports inlined away
    mod = _load(str(out), "bundled_123_456")
    a1, a2 = mod.BiddingAgent1(), mod.BiddingAgent2()
    assert a1.get_id() == "123_456" and a2.get_id() == "123_456"  # <id1>_<id2>, NO id_ prefix (TA ruling)


def test_src_agents_run_through_real_server_with_finite_utilities():
    import CONSTANTS  # from fixtures (conftest puts it on the path)
    import id_dummy_1
    import server as grader

    from hw3.agent1 import BiddingAgent1
    agents = [BiddingAgent1(), id_dummy_1.BiddingAgent1()]
    utils = grader.run_simulation(agents, CONSTANTS.NUM_SLOTS, 100, enforce_budget=False)
    assert set(utils) == {a.get_id() for a in agents}
    assert all(math.isfinite(u) for u in utils.values())
