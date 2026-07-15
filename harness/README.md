# harness/ — evaluation & research tools

All run over the **real** `fixtures/server.py` (never a re-implementation), CRN-paired (fixed
seeds) for low variance. Run with `PYTHONPATH=src python harness/<file>.py [args]`.
**Fixed id-handling:** set `agent.id = label` directly — never wrap `get_id()` (that desyncs the
agent's self-id and corrupts it; see `docs/dummy2-search-findings.md`).

## Core — use these
| file | what it does |
|---|---|
| `benchmark.py [N]` | Reproducible fixed-seed avg-utility of our agent vs the 3 dummies (Task 1 & 2). The pair-comparison tool — exchange the "ours" numbers with another pair. |
| `tournament.py [N]` | CRN tournament, 4-agent + 13-agent (many-agent) regimes, mean ± 95% CI. |
| `diagnose.py [N]` | Per-agent slot-distribution / price / cost / utility per round — the "why" behind the numbers. |

## Quality gates (also run in CI via pytest, except where noted)
| file | what it does |
|---|---|
| `latency_probe.py` | Worst-case get_bid/notify time (src + bundled), 50 ms cap. |
| `mutation_test.py` | Mutation testing of `strategy.py` (must stay 7/7 killed). |
| `freeze_baseline.py` | Re-freeze `tests/Regression_Tests/baseline_utilities.json` after an accepted improvement (upward only). |

## Statistics
| file | what it does |
|---|---|
| `ci_sample_size.py [N]` | How many sims for a target 95%-CI width; N = (1.96σ/E)². |
| `exp_paired.py [N]` | Paired absolute-margin significance (ours − each dummy). |

## Research (strategy search — kept for the record / to resume)
| file | what it does |
|---|---|
| `exp_valueaware.py <mode> <N>` | **Current** search: value-aware `b=c·v` to beat all 3 dummies. pilot / screen / confirm / holdout on disjoint seed blocks. See `docs/dummy2-search-findings.md`. |
| `exp_treatment.py [N]` | Paired ON-vs-OFF treatment effect of the cost-raise (proxy agents). |
| `exp_smart.py [N]` | smart cost-raise vs self-referential raise vs off. |
| `exp_alpha.py`, `exp_raisecost.py` | Earlier cost-raise sweeps (superseded by the above; kept for history). |
| `compare.py <label>=<path.py>` | Head-to-head vs an external pair's `id_*.py` **if** we ever get their file (gitignored `external_agents/`). |

**Note:** absolute per-dummy margins are noisy (each agent draws an independent `U(0,100)` value →
paired-diff std ~53k). Confirm any candidate on a **disjoint** block at **N≈5000**, not a small
screen. Each 5000-sim field is ~15–40 min (server ThreadPool overhead dominates — a "simpler"
agent is not faster).
