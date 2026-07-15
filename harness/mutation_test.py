"""Mutation testing: apply one-line mutations to src/hw3/strategy.py and confirm each is KILLED
by the test suite (pytest exits non-zero). A SURVIVED mutant is a real coverage gap. The original
file is always restored. Usage: PYTHONPATH=src python harness/mutation_test.py"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STRAT = ROOT / "src" / "hw3" / "strategy.py"

MUTATIONS = [
    ("rivals[k] + _EPS", "rivals[k] - _EPS", "bid below the displaced rival (wrong slot)"),
    ("if price > value:", "if price < value:", "accept a negative-utility slot"),
    ("(value - price) * ctr_list[k]", "(value + price) * ctr_list[k]", "wrong utility sign"),
    ("min(max(0.0, bid), budget)", "max(0.0, bid)", "drop the budget cap"),
    ("bid = 0.0", "bid = value", "over-bid the free floor"),
    ("winner_by_slot[k] != my_id", "winner_by_slot[k] == my_id", "include self as a rival"),
    ("price = rivals[k] if k < len(rivals) else 0.0", "price = 0.0", "ignore the slot price"),
]


def run_suite():
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x"], cwd=str(ROOT),
                       env=env, capture_output=True, text=True)
    return r.returncode


def main():
    orig = STRAT.read_text()
    assert run_suite() == 0, "baseline suite must be green before mutation testing"
    results = []
    try:
        for old, new, desc in MUTATIONS:
            if old not in orig:
                results.append(("SKIP", desc)); continue
            STRAT.write_text(orig.replace(old, new, 1))
            results.append(("KILLED" if run_suite() != 0 else "SURVIVED", desc))
    finally:
        STRAT.write_text(orig)  # always restore
    killed = sum(1 for r, _ in results if r == "KILLED")
    total = sum(1 for r, _ in results if r != "SKIP")
    for res, desc in results:
        print(f"  {res:<9} {desc}")
    print(f"\n{killed}/{total} mutants killed.")
    assert killed == total, "SURVIVING mutant(s) -> coverage gap"


if __name__ == "__main__":
    main()
