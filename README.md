# gsp-sim-bench

Reproducible benchmark harness for a repeated **Generalized Second-Price (GSP)** ad-auction
simulation. Compares bidding-agent strategies against three reference agents over a fixed, seeded
set of games. Pure Python standard library — no dependencies.

## Run locally

```bash
# Agent-1 variant sweep (Task 1, no budget) — aggression sweep vs the current agent:
PYTHONPATH=src python harness/benchmark_variants.py 5000

# Both tasks for the current agent (Task 1 + budget-constrained Task 2):
PYTHONPATH=src python harness/benchmark.py 5000
```

`N` (the argument) is the number of independent games averaged; each game runs `T=3000` rounds with
`4` agents and `4` slots. More `N` → tighter confidence intervals.

## Run in CI

The `benchmark` GitHub Actions workflow runs both benchmarks in parallel and uploads the result
tables as artifacts. Trigger it from the **Actions** tab (`Run workflow`), optionally setting `N`.

## Layout

- `fixtures/` — the simulator (`server.py`), run constants, and the three reference agents.
- `src/hw3/` — the agents under test (placeholder identifiers only).
- `harness/` — the benchmark drivers.
