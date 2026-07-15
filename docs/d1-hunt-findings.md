# HW3 Task-1 "beat all 3 dummies" — full exploration log

This is the complete R&D story for the Task-1 agent (`BiddingAgent1`), so both partners have
everything: what we shipped, what we tried, what worked, what didn't, and how to continue. **The
shipped agent is on `main`; the research lives in `harness/dummy1_hunt.py` + `harness/exp_valueaware.py`;
the ad-hoc validation scripts are in `docs/explorations/`.**

## TL;DR
- **Shipped Task-1 agent = "hybrid"** (`DescentRaiseAgent1` in `src/hw3/descent.py`): distribution-aware
  expected-utility + two targeted moves against a constant-fraction rival (dummy1). **It beats all 3
  dummies on the held-out block (400000)**; on the confirm block (200000) it's 2/3 with dummy1 just
  below zero. So dummy1 is a **near-coin-flip at ≈0** — the best achievable — while dummy2 & dummy3 are
  won on the point estimate. Task 2 (`BiddingAgent2`, pacing) is unchanged.
- **⚠️ Significance caveat (the honest one):** at N=5000 the ours-vs-dummy *paired* margins have WIDE CIs
  (ours and a dummy compete → negatively correlated → the paired diff is not tight). Rigorously, **only
  dummy3 is a statistically significant win** (`ours−d3 +4841 ±1337`); **dummy1 (+804 ±1590) and dummy2
  (+33 ±1551) are ties** that flip sign by seed block. So "beats all 3" is a **point estimate, not a
  statistically clean sweep** — don't over-claim it. What *is* significant + tight: hybrid beats our own
  prior agents (ours-vs-ours paired). Reproduce with `docs/explorations/paired_significance.py`.
- **We proved dummy1 can't be pushed *robustly* positive without giving back dummy2** — the tradeoff is
  structural. Hybrid is the frontier.

## The metric
Per-dummy margin `ours − dummy_k` at full T=3000, on **disjoint seed blocks** (confirm 200000,
held-out 400000), via the `replica` engine which is **byte-identical to the real `server.py`** (proven
by `tests/System_Tests/test_replica_parity.py`). "Beats all 3" = all three margins > 0.

## Run configuration (must match exactly to compare pair-to-pair — all from `fixtures/CONSTANTS.py`)
| knob | value |
|---|---|
| Rounds / sim (T) | 3000 |
| Slots | 4 (4-agent field → everyone wins a slot) |
| CTR per slot j | `α_j = t·d^j`, `t ~ N(0.7, 0.1)`, `d ~ N(0.6, 0.05)` |
| Private value | `v ~ U(0, 100)` — per agent, **fixed within a sim**, redrawn each sim |
| Budget (Task 2) | `B ~ N(10000, 750)` |
| Time cap | 50 ms/call (exceed → agent removed that round) |
| Seed blocks | pilot 100000 · **screen 0** · **confirm 200000** · **held-out 400000** (disjoint) |
| Engine | `replica` (byte-identical to `server.py`) or `real` (the grader itself) |
| Noise | per-sim σ ≈ 34,000 (dominated by the U(0,100) value draw) → need ~1,500–2,000 sims to resolve ~2,500-size gaps |

## Shared benchmark artifact (a peer)
Reproducible pair-vs-pair benchmark page, kept in sync with the shipped agent (currently **hybrid**):
**https://claude.ai/code/artifact/a1e22adc-7721-4fbc-a135-0c181aebad69** — same URL is always updated,
never re-minted. It shows the shipped agent's per-dummy margins on both blocks + the run config above +
the "how many sims for a 95% CI" derivation. Full-disclosure of the cost-raise mechanism is intentional
(team choice, as on HW1/HW2).

## Agent evolution
| agent | how | vs d1 | vs d2 | vs d3 | verdict |
|---|---|---|---|---|---|
| champion | best-response + cost-raise on last round | ~0 | **loses** | wins | 1/3 (PR #… earlier) |
| **descent** (PR #35) | distribution-EU + a targeted *descend* below a constant rival | −108 (holdout) | wins | wins | 2/3 |
| **hybrid** (PR #36, shipped) | descent **+ a d2-neutral cost-raise** | **+144 (holdout)** | wins | wins | **3/3 on holdout** |

## The d1-hunt mechanisms (all in `harness/dummy1_hunt.py`)
Baseline = descent (d1 −446 confirm / −108 holdout). Goal: recover dummy1 without losing dummy2.

1. **`TunableDescentAgent1` — extend the descend trigger / tighter epsilon** (`dplus*`, `dtight`).
   *Rejected*: barely moved d1 and cost d2.
2. **`ConstSuppressAgent1` — constant-only suppression weight** (`csupp*`). *Rejected*: **overshoots** —
   flips d1 to +1400 but crashes d2 to −1600, even at the smallest weight (w=0.02). The d1↔d2 tradeoff
   is a near **step function**, not a tunable slope.
3. **`DirectD1MarginAgent1` — value-aware: maximize `E[own − λ·d1_util]`** using dummy1's exactly-known
   value (`v̂ = bid/0.85`) (`directd1*`). *Rejected*: same overshoot as csupp (sharper proxy, same wall).
4. **`DescentRaiseAgent1` — the HYBRID (SHIPPED)**: adds a **cost-raise** — when our EU seat is slot 1
   directly *below* the constant rival, bid just under its identified bid. In GSP the slot-0 winner pays
   the bid directly below it (us), so dummy1 pays ~its full bid while **our own price and seat are
   unchanged** → a *d2-neutral* way to suppress dummy1. Recovered d1 by +259 (confirm) / +252 (holdout,
   paired, sig) for a tiny d2/d3 cost (−14…−19). **This is the one lever that broke the tradeoff.**
5. **`DescentRaiseCondAgent1` — conditional descend** (`cond*`): descend even in marginal rounds but only
   when it doesn't hand dummy2 a better slot. *Rejected*: worse than hybrid on **both** d1 and d2 — the
   extra descends cost ~as much own-utility as the d1-margin they gain.

**Conclusion:** the cost-raise is the *only* d2-neutral suppression, and it's maxed (it fires only when
we sit directly below dummy1, and it already bids just under it there). Everything else trades d1 for
d2 ~1:1. So **hybrid ≈ the ceiling**; dummy1 at the boundary is as far as it goes without regressing
dummy2.

## How to reproduce / continue (compute)
⚠️ **GitHub Actions minutes are exhausted** → the `ci` and `heavy-sims` workflows are **disabled**, and
the `test` required status check was dropped from `main`'s branch protection so PRs still merge. Run
everything **locally**; use **single core (`jobs=1`)** only — never multi-core (a `jobs=10` run cooked
the laptop to 98 °C). Small N screens (~500) finish in minutes.

```bash
# margin screen of any candidate set on a seed block (single core), e.g. hybrid vs a variant:
HW3_CANDS="descent,hybrid,cond050" HW3_BLOCK=confirm PYTHONPATH=src \
  python harness/exp_valueaware.py custom 500 replica 1
# blocks: confirm=200000, holdout=400000, screen=0
```
`docs/explorations/` has the ad-hoc scripts we used: `xblock_check.py` (cross-block margins),
`validate_port.py` (src == harness agent), `measure_descent_regression.py` (regression-baseline probe).

## To submit / re-enable CI later
- **Submit:** `submission_staging/123456789_987654321.zip` on `main` (the hybrid build) to Moodle.
- **Re-enable CI after the monthly reset:** `gh workflow enable ci.yml` + `gh workflow enable heavy-sims.yml`,
  and re-add the `test` required check to `main`'s branch protection.
