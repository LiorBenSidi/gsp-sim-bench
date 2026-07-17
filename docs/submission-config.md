# HW3 submission configuration — the exact run parameters

Single source of truth for **every** number in this repo (benchmarks, the a peer artifact, the
regression baseline, the replica screens). All of them are driven by the grader constants below, so
any two runs that name the same block/N/engine are directly comparable.

## Definitive grader result

The vendored agent (`submission_staging/id_207490913_318931672.py`, sha256 `1d2f969c…`) run through
the official `server.py` + `CONSTANTS.py` + 3 dummies (all sha256-pinned), unseeded, **N=10,000**.
**Both tasks PASS all three per-dummy threshold checks:**

| | ours | vs dummy_1 | vs dummy_2 | vs dummy_3 | verdict |
|---|---|---|---|---|---|
| **Task 1** | 39,594.69 | OK (102.9%) | OK (103.2%) | OK (115.5%) | **PASSED** |
| **Task 2** | 67,036.17 | OK (122.7%) | OK (210.1%) | OK (161.7%) | **PASSED** |

Pass criterion = **≥95% of each dummy** (`PASS_TOLERANCE=0.05`) — the relief exists because the
grader run is unseeded, so it absorbs draw variance (SE ≈ ±340 at N=10,000). Ranking (1st/1st here)
bears only on the competitive part. Zero latency warnings across ~60M `get_bid` calls. Grader run:
Actions `29583647700`.

## Grader constants (`fixtures/CONSTANTS.py` — mirrors the official `CONSTANTS.py`)

| constant | value | meaning |
|---|---|---|
| `T_ROUNDS` | **3000** | rounds per simulation (one GSP auction per round) |
| `NUM_SLOTS` | **4** | ad slots per round |
| `NUM_SIMULATIONS` | 30 (default) | games averaged — **the grader uses "very high" N**, so treat our N as a sample, not the grader's |
| `P_CTR_t` | (0.7, 0.1) | slot-0 CTR base `t ~ N(0.7, 0.1)` |
| `P_CTR_d` | (0.6, 0.05) | per-slot decay `d ~ N(0.6, 0.05)`; slot-j CTR `= t·d^j` |
| `UNI_VALUE` | (0, 100) | per-agent per-click value `v ~ U(0,100)`, fixed within a sim, private |
| `BUDGET_NORM` | (10000, 750) | Task-2 budget `B ~ N(10000, 750)` |
| `TIME_CAP` | **0.05 s** | per-`get_bid` wall-clock cap; exceeding it disqualifies the agent (bid 0, utility ÷ full T) |

## Field and the two tasks

- **Field:** our agent + the 3 provided naive dummies → `num_agents == num_slots == 4`.
- **Task 1** (`BiddingAgent1`): `enforce_budget=False` — no budget constraint.
- **Task 2** (`BiddingAgent2`): `enforce_budget=True` — budget `B ~ N(10000,750)`.
- **Grading (HW3.pdf p.3 + 2026-07-16 relief):** per agent, 40 pts for reaching **≥ 95% of each of
  the 3 dummies** on average utility (`PASS_TOLERANCE=0.05` — the relief exists because the grader run
  is unseeded; you do *not* have to strictly beat a dummy) + 10 pts competitive vs the class.

## What's shipped

| agent | class | engine |
|---|---|---|
| `BiddingAgent1` (Task 1) | `StochRaiseStrong07Agent1` (`FLOOR=0.7`) | distribution-EU best response + d1 descend + d1 cost-raise + **censoring-safe d2 (stochastic) cost-raise** |
| `BiddingAgent2` (Task 2) | unchanged | distribution-EU best response + self-correcting budget pacing |

Both are stdlib-only, O(1) memory/round, well under the 50 ms cap (latency test green).

## Measurement engines — when each is valid

| engine | file | what it is | valid for |
|---|---|---|---|
| **Real server** | `fixtures/server.py` via `harness/benchmark.py` | the actual grader simulator (threaded, budgets, latency DQ) | **both tasks**; the submission-faithful number; feeds the a peer artifact |
| **Replica** | `harness/replica_sim.py` via `docs/explorations/validate_all_candidates.py` | a fast re-implementation of the server's **Task-1** dynamics — same CTR/value model, same RNG draw order (byte-parity test `test_replica_parity.py`) | **Task 1 only** (`enforce_budget=False`); ~100× faster, used to screen candidates. Asserts `enforce_budget is False`. |

The replica does **not** model the budget draw (Task 2) or the timeout/disqualify path.

## Seed blocks — which run used which

Runs are only comparable within the **same** seed block (the dummies are field-dependent — competitors'
utilities shift when our agent bids differently, so cross-block absolute numbers don't line up).

| block (offset) | role | used by |
|---|---|---|
| **0 .. N−1** | the shared, reproducible benchmark block | `harness/benchmark.py`, the **a peer artifact**, the regression baseline (short-T) |
| **200000 ..** | a disjoint confirm block | ad-hoc confirms |
| **400000 ..** | the reserved **holdout** (never used to build the agent) | `stoch_strong07` holdout confirmation (`VC_OFF=400000`) |
| **600000 ..** | a scratch screen block | candidate screen (`VC_OFF=600000`) |

## Reproduce any number

```bash
# Real-server, submission config (a peer-comparable), both tasks, seeds 0..N-1, T=3000:
PYTHONPATH=src python harness/benchmark.py <N>          # default N=300

# Fast Task-1 candidate screen / holdout confirm (replica), paired vs the shipped hybrid:
VC_N=<N> VC_T=3000 VC_OFF=<block> VC_ONLY=<candidate> \
  PYTHONPATH=src python docs/explorations/validate_all_candidates.py

# Regression baseline (20 seeds, T=500 short proxy, own-utility guard):
PYTHONPATH=src python harness/freeze_baseline.py

# Rebuild the committed submission bundle after any src/hw3 change:
PYTHONPATH=src python build/make_submission.py --id1 123456789 --id2 987654321
```

## Compute discipline (this machine)

Runs are **single-core only** (`jobs=1`) — the M4 overheated (85–98 °C) under multi-core sim loads.
GitHub Actions minutes are exhausted → both workflows disabled, so **all gates run locally**
(pytest / ruff / latency / mutation) before any merge. Keep sim N modest and watch temperature.
