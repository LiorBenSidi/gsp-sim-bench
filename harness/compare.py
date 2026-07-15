"""Head-to-head comparison: our agents vs one or more external student pairs (e.g. a peer pair), in the REAL GSP server, CRN-paired. Mirrors the competitive part (10 pts): several
student pairs in one auction, ranked by average utility over many sims.

Runs BOTH tasks: Task 1 = every pair's BiddingAgent1 (no budget); Task 2 = every pair's
BiddingAgent2 (budget). Optionally adds the 3 naive dummies to fill the field (--dummies).

PRIVACY: external files (id_<ids>.py with BiddingAgent1/BiddingAgent2) contain other students'
IDs and strategy -- they are loaded by PATH and MUST NEVER be committed to this repo. Keep them
outside the repo or in a gitignored dir. Output relabels each pair to a friendly nickname so no
real IDs are printed.

Usage:
  PYTHONPATH=src python harness/compare.py [num_sims] <label>=<path.py> [<label>=<path.py> ...]
  PYTHONPATH=src python harness/compare.py 200 peer_pair=/path/to/id_xxx_yyy.py --dummies

If an arg has no '=', it is auto-labelled rival1, rival2, ... A bare path still works.
"""
import importlib.util
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fixtures"))
sys.path.insert(0, str(ROOT / "src"))
import CONSTANTS  # noqa: E402
import server as grader  # noqa: E402

from hw3.agent1 import BiddingAgent1 as OurA1  # noqa: E402
from hw3.agent2 import BiddingAgent2 as OurA2  # noqa: E402


def _labelled(agent, uid):
    """Give the agent a stable, privacy-safe display id by setting its OWN .id -- so get_id() and
    the agent's internal self.id (used to recognise itself in the results) stay in sync. Wrapping
    get_id() alone desyncs them and cripples a self-identifying agent (it treats its own wins as a
    rival's). Works for any agent whose get_id returns self.id (ours, the dummies, standard
    student agents)."""
    agent.id = uid
    return agent


def _load_module(path, modname):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


def parse_args(argv):
    n, want_dummies, pairs = 200, False, []
    auto = 0
    for a in argv:
        if a == "--dummies":
            want_dummies = True
        elif a.isdigit():
            n = int(a)
        elif "=" in a:
            label, path = a.split("=", 1)
            pairs.append((label, path))
        else:
            auto += 1
            pairs.append((f"rival{auto}", a))
    return n, want_dummies, pairs


def build_field(pairs, want_dummies, which):
    """which = 1 or 2 -> use BiddingAgent1 or BiddingAgent2 from each source."""
    field = [_labelled((OurA1 if which == 1 else OurA2)(), "ours")]
    for i, (label, path) in enumerate(pairs):
        mod = _load_module(path, f"rival_{i}_{which}")
        cls = getattr(mod, f"BiddingAgent{which}")
        field.append(_labelled(cls(), label))
    if want_dummies:
        for d in (1, 2, 3):
            mod = _load_module(str(ROOT / "fixtures" / f"id_dummy_{d}.py"), f"dummy_{d}_{which}")
            cls = getattr(mod, f"BiddingAgent{which}")
            field.append(_labelled(cls(), f"dummy{d}"))
    return field


def run(field, enforce_budget, n):
    labels = [a.get_id() for a in field]
    per = {lab: [] for lab in labels}
    for s in range(n):
        random.seed(s)
        u = grader.run_simulation(field, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS,
                                  enforce_budget=enforce_budget)
        for lab in labels:
            per[lab].append(u.get(lab, 0.0))
    return {lab: (statistics.fmean(per[lab]),
                  1.96 * statistics.pstdev(per[lab]) / (n ** 0.5)) for lab in labels}


def report(title, field, enforce_budget, n):
    res = run(field, enforce_budget, n)
    print(f"\n== {title} ({len(field)} agents, {n} CRN sims) ==")
    print(f"  {'rank':<5}{'agent':<16}{'avg utility':>13}{'95% CI':>11}")
    for i, (lab, (m, ci)) in enumerate(sorted(res.items(), key=lambda kv: kv[1][0], reverse=True), 1):
        star = "  <- us" if lab == "ours" else ""
        print(f"  {i:<5}{lab:<16}{m:>13.1f}{ci:>11.1f}{star}")


def main():
    n, want_dummies, pairs = parse_args(sys.argv[1:])
    if not pairs:
        print("Provide at least one external agent file, e.g.:\n"
              "  PYTHONPATH=src python harness/compare.py 200 peer_pair=/path/id_xxx_yyy.py --dummies")
        return
    print(f"Comparing OURS vs {[lab for lab, _ in pairs]}"
          f"{' + dummies' if want_dummies else ''}, {n} CRN sims on the real server.")
    report("TASK 1 (no budget)", build_field(pairs, want_dummies, 1), False, n)
    report("TASK 2 (budget)", build_field(pairs, want_dummies, 2), True, n)


if __name__ == "__main__":
    main()
