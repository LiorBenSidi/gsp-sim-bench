"""Live progress heartbeat for the heavy harnesses.

Prints a `k/N (X%)` line to STDERR (flushed) at ~5% boundaries and at completion, so a long run
streams visible progress in the GitHub Actions log and in a local terminal (best under `python -u`,
which the heavy-sims workflow uses). stderr is deliberate: it keeps the stdout results tables clean
for pair-exchange / parsing, and never changes any computed number (fixed-seed CRN is untouched).
"""
import sys


def ticker(total, label="sims", every_frac=0.05):
    """Return `tick(done)`: call it with the 1-based count of finished sims; it emits a progress
    line at ~every_frac boundaries and on the final sim. A no-op-ish tiny helper -- pure I/O."""
    total = int(total)
    step = max(1, int(total * every_frac))

    def tick(done):
        if done == total or done % step == 0:
            pct = 100.0 * done / total if total else 100.0
            print(f"  [{label}] {done}/{total} ({pct:.0f}%)", file=sys.stderr, flush=True)

    return tick
