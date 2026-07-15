"""Thorough latency probe for the 50ms/call grader cap (get_bid AND notify_round_results).

Stresses the WORST case the smart cost-raise can hit: 3000 rounds where the slot winners keep
CHANGING id, so the agent's cross-round bid tracker (_bid_by_id) grows to its max (num_agents).
Measures BOTH the src modules AND the bundled submission file (the actual graded artifact).

Reports the worst single call (ms) per method per agent; must stay well under 50ms.

Usage: PYTHONPATH=src python harness/latency_probe.py
"""
import importlib.util
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

CTR = [0.7, 0.42, 0.252, 0.1512]
NUM_SLOTS = 4
T = 3000
CAP_MS = 50.0


def _histories(n_ids):
    """Round histories whose 4 winners rotate across n_ids distinct agents -> grows _bid_by_id
    to n_ids and keeps 'ours' sometimes in slot 0 (hidden) and sometimes below (observed)."""
    ids = [f"a{i}" for i in range(n_ids)]
    hists = []
    for r in range(T):
        base = r % n_ids
        rot = [ids[(base + k) % n_ids] for k in range(NUM_SLOTS)]
        # occasionally put "ours" on top or below to exercise both id-tracking branches
        if r % 3 == 0:
            rot[1] = "ours"
        elif r % 3 == 1:
            rot[0] = "ours"
        hists.append([(rot[0], 0, 30.0 + (r % 7)), (rot[1], 1, 12.0 + (r % 5)),
                      (rot[2], 2, 4.0 + (r % 3)), (rot[3], 3, 0.0)])
    return hists


def probe(agent, budget, hists):
    agent.start_simulation(13, NUM_SLOTS, CTR, 50.0, budget, T)
    try:
        agent.id = "ours"  # so it self-identifies in our synthetic history
    except Exception:
        pass
    worst_bid = worst_notify = 0.0
    for r in range(T):
        t = time.perf_counter(); agent.get_bid(budget); worst_bid = max(worst_bid, time.perf_counter() - t)
        t = time.perf_counter(); agent.notify_round_results(hists[r]); worst_notify = max(worst_notify, time.perf_counter() - t)
    return worst_bid * 1000, worst_notify * 1000


def load_bundle():
    out = ROOT / "submission_staging" / "id_latency_probe.py"
    out.parent.mkdir(exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "build" / "bundle.py"), "--id1", "111", "--id2",
                    "222", "--out", str(out)], check=True, cwd=str(ROOT),
                   env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""})
    spec = importlib.util.spec_from_file_location("bundled_probe", out)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    from hw3.agent1 import BiddingAgent1
    from hw3.agent2 import BiddingAgent2
    hists = _histories(13)  # many-agent worst case: 13 distinct ids rotating through the slots

    print(f"Latency probe -- {T} rounds, id-set grows to 13, cap = {CAP_MS:.0f} ms/call.\n")
    print(f"  {'agent (source)':<22}{'worst get_bid':>15}{'worst notify':>15}{'verdict':>10}")
    rows = [
        ("Agent1 (src)", BiddingAgent1(), float("inf")),
        ("Agent2 (src)", BiddingAgent2(), 10000.0),
    ]
    bundle = load_bundle()
    rows += [
        ("Agent1 (bundled)", bundle.BiddingAgent1(), float("inf")),
        ("Agent2 (bundled)", bundle.BiddingAgent2(), 10000.0),
    ]
    ok = True
    for label, agent, budget in rows:
        wb, wn = probe(agent, budget, hists)
        good = wb < CAP_MS and wn < CAP_MS
        ok = ok and good
        print(f"  {label:<22}{wb:>12.4f} ms{wn:>12.4f} ms{'  OK' if good else '  FAIL':>10}")
    margin = CAP_MS / max(1e-9, max(probe(BiddingAgent1(), float('inf'), hists)))
    print(f"\n  => {'ALL well under the 50ms cap' if ok else 'CAP BREACH'} "
          f"(~{margin:.0f}x headroom on Agent 1).")


if __name__ == "__main__":
    main()
