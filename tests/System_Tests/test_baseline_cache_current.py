"""The committed champion baseline cache (harness/baseline_cache/) is loaded by screens instead of
re-running the champion field. It must match a fresh compute of the CURRENT champion, or a src/hw3
change would silently feed screens stale baseline rows. Cheap guard: recompute the first few sims of
each cache file's seed block and byte-compare via float.hex(). (Each sim is independent -- the server
resets agent state per sim -- so the first K rows suffice.)"""
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "fixtures"))
sys.path.insert(0, str(ROOT / "src"))

import exp_valueaware as E  # noqa: E402


def test_committed_champion_cache_matches_current_code():
    import pytest
    files = sorted((ROOT / "harness" / "baseline_cache").glob("champion_b*_N*.json"))
    if not files:
        # No committed cache -> nothing can be stale. The cache is a cloud-screen optimization
        # (skip re-running the frozen 'champion' baseline); it is regenerated + committed by the
        # next in-cloud screen after a strategy change. Guard re-activates once a cache exists.
        pytest.skip("no committed champion baseline cache yet (regenerated in-cloud on next screen)")
    field = E.build_field("champion")
    for f in files:
        m = re.match(r"champion_b(\d+)_N(\d+)\.json", f.name)
        block, n = int(m.group(1)), int(m.group(2))
        cached = json.loads(f.read_text())
        assert len(cached) == n, f"{f.name}: expected {n} rows, got {len(cached)}"
        for i, s in enumerate(range(block, block + min(8, n))):
            random.seed(s)
            u = E.run_simulation_replica(field, E.NS, E.T, enforce_budget=False)
            fresh = (u["ours"], u["d1"], u["d2"], u["d3"])
            cr = tuple(cached[i])
            assert all(a.hex() == b.hex() for a, b in zip(fresh, cr, strict=True)), (
                f"{f.name} sim {s}: cache is STALE vs the current champion ({fresh} != {cr}). "
                f"Recompute: delete harness/baseline_cache/ and re-run a screen, then commit.")
