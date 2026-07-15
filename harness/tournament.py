"""Local CRN tournament harness over the REAL fixtures/server.py (the authoritative grader).

Never re-implements the auction. Seeds the global RNG per simulation (Common Random Numbers)
so candidate strategies are compared paired -> far lower variance than server.py's 30-sim
default. Reports mean utility +- 95% CI, and supports a many-agent (#agents > #slots) regime.

Usage:  PYTHONPATH=src python harness/tournament.py [num_sims]
"""
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fixtures"))  # so `import CONSTANTS` inside server.py resolves
sys.path.insert(0, str(ROOT / "src"))

import CONSTANTS  # noqa: E402
import id_dummy_1  # noqa: E402
import id_dummy_2  # noqa: E402
import id_dummy_3  # noqa: E402
import server as grader  # noqa: E402
from _progress import ticker  # noqa: E402

from hw3.agent1 import BiddingAgent1  # noqa: E402
from hw3.agent2 import BiddingAgent2  # noqa: E402


def _labelled(cls, uid):
    """Give the agent a unique display id by setting its OWN .id attribute -- so get_id() AND the
    agent's internal self.id (used to recognise itself in the results, e.g. to exclude itself as a
    rival) stay in sync. Wrapping get_id() alone desyncs them and cripples a self-identifying
    agent (it treats its own wins as a rival's). Lets us also clone rivals into a bigger field."""
    a = cls()
    a.id = uid
    return a


def run(factories, num_slots, T, num_sims, enforce_budget, seed_base=0, progress="sims"):
    """factories: list of (label, class). Instances created ONCE and reused across sims
    (matching the real grader); RNG seeded per sim (CRN). Returns {label: [util per sim]}."""
    agents = [_labelled(cls, label) for label, cls in factories]
    labels = [label for label, _ in factories]
    results = {lab: [] for lab in labels}
    tick = ticker(num_sims, progress)
    for s in range(num_sims):
        random.seed(seed_base + s)
        utils = grader.run_simulation(agents, num_slots, T, enforce_budget=enforce_budget)
        for lab in labels:
            results[lab].append(utils.get(lab, 0.0))
        tick(s + 1)
    return results


def summarize(results):
    rows = []
    for lab, xs in results.items():
        m = statistics.fmean(xs)
        sd = statistics.pstdev(xs) if len(xs) > 1 else 0.0
        ci = 1.96 * sd / (len(xs) ** 0.5) if xs else 0.0
        rows.append((lab, m, ci))
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows


def _report(title, factories, enforce_budget, num_sims):
    res = run(factories, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS, num_sims, enforce_budget, progress=title)
    print(f"\n== {title} ({num_sims} sims, CRN) ==")
    for lab, m, ci in summarize(res):
        star = "  <- candidate" if lab.startswith("ours") else ""
        print(f"  {lab:<16} mean {m:11.1f}  +/- {ci:8.1f}{star}")


def _clones(factories, k):
    return [(f"{lab}#{c}", cls) for lab, cls in factories for c in range(k)]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    d1 = [("dummy1", id_dummy_1.BiddingAgent1), ("dummy2", id_dummy_2.BiddingAgent1),
          ("dummy3", id_dummy_3.BiddingAgent1)]
    d2 = [("dummy1", id_dummy_1.BiddingAgent2), ("dummy2", id_dummy_2.BiddingAgent2),
          ("dummy3", id_dummy_3.BiddingAgent2)]
    # Default regime: candidate + 3 dummies (num_agents == num_slots == 4).
    _report("TASK 1 default (4 agents)", [("ours", BiddingAgent1)] + d1, False, n)
    _report("TASK 2 default (4 agents)", [("ours", BiddingAgent2)] + d2, True, n)
    # Competitive regime: many agents vs 4 slots (real scarcity). 1 + 3*4 = 13 agents.
    _report("TASK 1 many-agent (13 agents)", [("ours", BiddingAgent1)] + _clones(d1, 4), False, n)
    _report("TASK 2 many-agent (13 agents)", [("ours", BiddingAgent2)] + _clones(d2, 4), True, n)


if __name__ == "__main__":
    main()
