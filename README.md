# gsp-sim-bench

Reproducible benchmark + test harness for a repeated **Generalized Second-Price (GSP)** ad-auction
simulation. Compares bidding-agent strategies against three reference agents over a fixed, seeded
set of games. The submission agents are pure Python standard library — no runtime dependencies.

## Run the benchmarks locally

```bash
# Agent-1 variant sweep (Task 1, no budget) — aggression sweep vs the current agent:
PYTHONPATH=src python harness/benchmark_variants.py 5000

# Both tasks for the current agent (Task 1 + budget-constrained Task 2):
PYTHONPATH=src python harness/benchmark.py 5000
```

`N` (the argument) is the number of independent games averaged; each game runs `T=3000` rounds with
`4` agents and `4` slots. More `N` → tighter confidence intervals.

## CI

- **`benchmark`** workflow — runs both benchmarks in parallel and uploads the result tables as
  artifacts (trigger from the **Actions** tab, optional `N` input).
- **`ci`** workflow — lint (ruff), a report-only security scan (bandit), a stdlib-only bundle check
  with placeholder identifiers, and the full `pytest` suite.

## Dev setup

```bash
pip install -r requirements.txt   # pytest, ruff, bandit (dev tooling only)
PYTHONPATH=src pytest -q
```

## Layout

- `fixtures/` — the simulator (`server.py`), run constants, and the three reference agents.
- `src/hw3/` — the agents under test (placeholder identifiers only).
- `harness/` — benchmark drivers + strategy research modules.
- `tests/` — unit / latency / system / regression suites.
- `build/` — submission bundler (placeholder identifiers).
