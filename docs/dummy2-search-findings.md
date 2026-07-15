# Beating all 3 dummies on Task 1 — search findings (paused 2026-07-10)

**Status:** PAUSED, not abandoned. The shipped agent is unchanged (`agent1.py` = best-response +
smart cost-raise). We will resume the search for a Task-1 strategy that beats **all three** dummies.

## The problem
Task 1's 40 pts requires our average utility to exceed **each** dummy. Over 5000 fixed-seed sims
the champion is **2nd of 4**: it beats dummy1 & dummy3 but **loses to dummy2** (the random
`U(0.4,1.0)·v` bidder). A rival pair (a peer) reportedly beats all three, so it is achievable.

## What this experiment BOUGHT us (progress, not a dead end)
A "failed" run that yields a structural finding moves us closer. Concrete, reusable gains:
1. **Value-aware bidding provably beats dummy2** (+1990 paired vs champion, significant) — the
   dummy2 half of the problem is *solved in isolation*. We know how to win d2.
2. **The champion's cost-raise is exactly what holds dummy1** — removing it (going `c·v`) loses d1
   by −1480 (paired, sig). So d1 and d2 each have a known, opposite lever.
3. **The target is a HYBRID**, and we now know its two required halves (keep the cost-raise for d1,
   add value-aware capture for d2). That's a concrete next design, not a blank page.
4. **A trustworthy measurement rig** (`exp_valueaware.py`) + the methodology lessons below — future
   attempts are cheap to run and won't be fooled by small-N mirages.

## Reference target — a peer's result (proof it IS achievable)
Rival pair a peer sent his own benchmark (his agent + the 3 course dummies, T=3000). **He beats
all 3 on both tasks:**
- Task 1: a peer **36,638** (1st) > dummy_2 34,815 > dummy_1 33,767 > dummy_3 28,691.
- Task 2: a peer **66,945** (1st) > dummy_3 45,570 > dummy_1 43,897 > dummy_2 31,113 (his agent
  leaves budget: mean $3,230, 69% of sims end with >$1,000 unspent — a Task-2 inefficiency, but
  still 1st).

⚠️ **Not directly comparable to our absolute numbers** — his dummies all score LOWER than ours
(dummy2 34,815 vs our 41,003, etc.) because the dummies' scores depend on the 4th agent (him vs
us); his agent suppresses them more. What it proves: **a strategy that beats all 3 exists.** Note
his Task-1 (36,638) is *lower absolute* than our champion (38,544) yet ranks 1st — i.e. the win is
about the dummy-suppression profile, not raw self-utility. That's the hybrid we're chasing.

## What we tried — value-aware / near-truthful `b = c·v`
Panel reframe (auction economist + strategy designer): our loss to dummy2 comes from our **own
conservatism**, not dummy2's strength — the champion takes the free bottom slot (CTR 0.15) **44%**
of rounds and slot-0 only 19%, ceding CTR-weighted value. In GSP your bid sets your RANK not your
price, so bidding near value is "free" and claims cheap high-CTR inventory. So we swept
`b = c·v`, c ∈ {0.90…1.15}, via `harness/exp_valueaware.py` (pilot → screen → confirm → holdout,
disjoint seed blocks, paired binding-dummy metric, fixed id-handling).

## Result — a real d1↔d2 tradeoff; no simple strategy beats all 3
**5000-sim holdout, disjoint block (seed 400000), per-dummy margin `mean(ours − dummy_k)`:**

| candidate | d1 | d2 | d3 | beats all 3 |
|---|---|---|---|---|
| champion (cost-raise) | +58 | **−1263** | +4622 | no (loses d2) |
| c0.90 | **−1422** | +727 | +4355 | no (loses d1) |
| c0.95 | −2113 | +10 | +3571 | no |
| c1.00 | −2793 | −736 | +2688 | no |

Paired vs champion (tight): c0.90 is **+1990 on d2 (sig)** but **−1480 on d1 (sig)**.

**The tradeoff is fundamental:** the champion's *cost-raise* suppresses dummy1 (→ beats d1) but it
is too conservative (→ loses d2). `c·v` captures value (→ beats d2) but drops the cost-raise
(→ dummy1 recovers, loses d1). Neither wins all three. This matches the economics adversary's
warning: "aggression self-degrades your sure win over dummy1."

## Methodology lessons (so we don't repeat mistakes)
- **The N=400 screen was a MIRAGE** — it showed `c·v` beating all 3 (block-0 was lucky). Only the
  **disjoint high-N (5000) holdout** revealed the d1 loss. Always confirm on a fresh block at N≈5000.
- **The paired-difference std is ~53,000, NOT tighter than the marginal σ≈34,000** — because our
  value and each dummy's value are *independent* draws, so `u_ours − u_dummy` sums two variances.
  ⇒ the *absolute* "beats each dummy" margin needs ~5,000–10,000 sims to pin. (The *candidate-vs-
  champion* paired diff IS tight — good for ranking candidates, not for the absolute claim.)
- **Wall-clock:** every 5000-sim field ≈ 15–40 min because `server.py` wraps every get_bid/notify
  in a per-call `ThreadPoolExecutor` (~120M thread ops/field). The agent's own logic is a rounding
  error — `c·v` is NOT meaningfully faster than the champion. Run FEWER candidates/sims, not
  "cheaper" agents. Reuse the champion's cached 5000-sim numbers instead of re-running it.

## Where to resume — the hybrid (candidate B/C)
The only path that can beat all three is a **hybrid**: keep the champion's cost-raise (hold d1)
AND make its slot-selection **less conservative** (lift d2), e.g. a value-model best-response that
(a) identifies each rival's fixed per-sim value — `v1 = bid/0.85` exact, `v̂2 = max observed dummy2
bid`, dummy3 deterministic — and best-responds to the *distribution* (not the stale last bid), and
(b) still cost-raises the slot-0 leader when in slot 1. See `agent1.py` (already tracks `_bid_by_id`)
and `harness/exp_valueaware.py` (add the hybrid as a candidate). Keep the **no-regression ratchet**:
ship only if it beats all 3 on a disjoint 5000-sim holdout AND doesn't regress Task 2 / the 13-agent
regime / latency / tests; otherwise keep the champion.

## Adversarial audit (2026-07-11) — three-expert triangulation of "do we use all per-round info?"
Three independent read-only expert agents (GSP auction-theory, structural value-estimation,
information-completeness red-team) audited the shipped champion. They converged on the **same** root
cause with file:line receipts. **Shipped agent UNCHANGED — analysis only, for the resume path.**

### Consolidated findings (ranked)
| # | Unused / underused signal | Sev | Why it matters |
|---|---|---|---|
| 1 | Best-respond to ONE stale round, not dummy2's **distribution** | CRIT | Values fixed for 3000 rounds ⇒ the utility-max policy vs dummy1+dummy2 is a single **stationary** bid, not per-round noise-chasing. This **is** the dummy2 loss. Formal name: **Cournot / 1-memory fictitious play**, which fails vs a mixing opponent. |
| 2 | Per-rival bid `max/mean/count` collapsed to last-bid (A1, `agent1.py:49`) / never formed (A2) | CRIT | The sufficient statistic that identifies `v_i`; enables #1. |
| 3 | **Censoring bias**: dummy2's HIGH draws win slot 0 → unobserved → we **underestimate `v₂`** exactly where it beats us | HIGH | Needs a censoring-aware estimator (treat slot-0 rounds as right-censored at `price[0]`); impossible without accumulation. |
| 4 | Self-referential slot-0 estimate when we hold slot 1 (A2 **fully unpatched**) | HIGH | Feedback loop amplifying the dummy2 leak (`strategy.py:29,90`). |
| 5 | `num_agents` passed but dropped (`strategy.py:105`) | HIGH | Parks the `agents≤slots` regime split. |
| 6 | `raise_top` can overtake/overpay vs a **stochastic** top (A1 fires it unconditionally at slot 1) | MED | Safe vs constant dummy1, risky vs varying dummy2/3. |
| 7 | dummy3 is price-adaptive → **shapeable** (repeated-game price suppression) | MED | Could suppress its future bids; ignored. |
| 8 | Own win/price/utility never tracked | MED | Can't self-calibrate / detect reconstruction error. |

**Non-findings (correct — do NOT touch):** exact CTR curve, value-cap (util ≥ 0), per-sim reset,
exact slot-k≥1 identification, Agent 2 pacing (*why Task 2 dominates*), latency/robustness. Agent 1
ignoring budget/T is **correct** (Task 1 has infinite budget), not a gap.

### Theory map (real articles)
- **Cournot best-response / fictitious play** (Brown 1951; Robinson 1951) — names our actual algorithm; its known failure vs a mixing opponent = the dummy2 loss.
- **Edelman–Ostrovsky–Schwarz (2007, AER)** + **Varian (2007, IJIO)** — GSP LEF/SNE equilibria & bid↔value inequalities; background, but LEF is *equilibrium* play and we want to *exploit* bots.
- **Guerre–Perrigo–Vuong (2000, Econometrica)** + **Athey–Nekipelov (2010)** — structural bid→value inversion; A–N models precisely the dummy2 (per-round noise) setup. Currently ignored.
- **Not applicable:** MAB/UCB/Thompson (this is identification, not a bandit; Thompson out of scope per TA); VCG / laddered auctions (we're a *bidder* in plain GSP, no quality scores).

### Candidate C — the untested resume candidate (distinct from the tried constant `c·v`)
The paused search tested only **candidate A** (constant shade `b=c·v`) → d1↔d2 tradeoff. The experts
point to **candidate C**, **never tested**:
1. **Accumulate** per-rival sufficient stats across rounds (`count, sum, max` of each rival's reconstructed bid, using the exact slot-k≥1 identification the price vector already hands us).
2. **Estimate `v̂_i` with a slot-0 censoring correction** — dummy1: `b/0.85` exact; dummy2: `max(b)` or `mean(b)/0.7`, corrected upward for censored high draws; dummy3: `spike/0.8` when the `0.8·v` cap binds.
3. **Best-respond to dummy2's implied distribution with a STATIONARY bid** — pick `b` maximizing `E[(value − price(b))·CTR(slot(b))]` over `P(dummy2 < b)` (uniform on `[0.4·v₂, v₂]`), once, robustly — not per-round.
4. **Keep the cost-raise only for the constant top (dummy1)** where it's provably free; do NOT fire `raise_top` against a stochastic top.

**Honest ceiling (do not over-expect):** this is **diagnostic, not a magic bullet**. When `v₂` is
genuinely high, dummy2 *deserves* slot 0 and contesting is unprofitable — the estimate won't overturn
that; it sizes the minimum bid to capture only the **profitable** out-ranking cases. Expected gain is
real but bounded. Worth exactly **one** rigorous attempt under the no-regression ratchet (beat all 3
on a disjoint 5000-sim holdout AND regress nothing: Task 2 / 13-agent / latency / tests), else keep
the champion.

## Candidate C′ (Fable 5 refinement, 2026-07-11) — the plan to actually run
A one-time Fable-5 pass on Candidate C. It caught a **fatal flaw** and sharpened the rest. **Still
parked / analysis-only; champion UNCHANGED.** Key math was independently re-derived and checks out
(`b*` algebra; the `v̂₂` moment equation; `server.py:121` short-circuits the budget draw when
`enforce_budget=False`, so Task-1 RNG order is deterministic).

### The fatal flaw in C: wrong objective
C maximized **own** EU `E[(v−price)·CTR]` — that is just the failed constant shade `c·v` with a
better estimator, so it re-loses d1 (the entire d1 win is *suppression*, not own utility). **Fix —
margin objective:**
`J(b) = E[u_ours(b)] − Σ_k w_k · E[u_k(b)]`, weights swept coarse `w_d1=w_d2=w0 ∈ {0, 0.5, 1}`,
`w_d3=0` (d3 is +4622 slack). `w0=0` is the pure-EU control arm (should reproduce C's d1 loss).

### Policy, not a single bid
Only d2 is i.i.d.; d3's bid moves every round (deterministic in observed prices). So the *policy* is
stationary, the **bid is recomputed each round** (microseconds; the server's ThreadPool dominates
wall-clock anyway).

### Estimators (O(1) per-rival sufficient stats: n_u,S_u,min_u,max_u,n_c,S_c,max_c)
- **d1 (constant):** bid observed exactly from any non-top round; `v̂₁ = b1/0.85`.
- **d2 (U(0.4,1)·v):** censoring is **one-sided/benign** — low draws never win slot 0, so
  `U₂ = min(min_u/0.4, 100) ↓ v₂` from above; hard lower bound `L₂ = max(max_u, max_c)`. Point:
  **`v̂₂ = (S_u + S_c/2) / (0.7·n_u + 0.2·n_c)`**, clipped to `[L₂, U₂]` (Buckley–James imputation;
  reduces to `mean/0.7` with no censoring).
- **d3 (reactive):** don't estimate — **predict** `b3_{t+1}=1.1·median(positive prices_t)` if `< v₃`
  else `0.8·v₃`; `v₃` pinned exactly from round 0 (`b3/0.75`) or any capped round (`b3/0.8`).
- **Slot-0 self-reference bug (audit #4) disappears:** treat the observed `price[0]` as a censoring
  bound (`b_top ≥ our bid`), never a point estimate.

### Exact per-round objective + optimizer
One random variable B₂ ⇒ the sorted cut-points `{0.4v̂₂, b1, b3, b, v̂₂}` split its support into ≤4
intervals where every agent's slot/price is fixed and each utility is **linear in B₂** → integrate in
closed form for `E[u_ours], E[u_d1], E[u_d2], E[u_d3]`. `J(b)` is piecewise-quadratic in `b`;
optimize over its ≤~15 breakpoints/vertices (or a 200-pt grid). Carry the champion's safety
invariants (never bid > v, NaN/inf guards, per-sim reset, ε tie-margins).

### The profitability frontier (the ceiling, made exact + safe)
Contesting d2 for slot 0 pays iff `b < b* := (1−d₁)·v + d₁·m` (m = best deterministic bid below us;
d₁ = CTR₁/CTR₀) — the **EOS/Varian local-envelope bid**. Three properties:
1. Captures **all** profitable out-rankings, **none** of the unprofitable (GSP 2nd-price ⇒ every
   capture pays); "d2 deserves the top" is exactly `B₂ > b*`. Capture prob `= clip((b*−0.4v̂₂)/(0.6v̂₂),0,1)`.
2. **`b*` is independent of `v̂₂`** ⇒ estimation error cannot break individual rationality; v̂₂ only
   sizes expected gains + the margin/suppression terms. (The robustness C lacked.)
3. d2-contest and the d1 cost-raise act on **disjoint round configs** (top stochastic vs deterministic),
   so contesting d2 can't erode the d1 win; the only coupling (d1 tops, raise target > b*) is resolved
   numerically by J per round — exactly what a constant `c` could never express.
- **Cost-raise subsumed into J**, and it never fires against a *stochastic* top on a stale estimate
  (audit #6). Suppression vignette: in the all-censored regime (`0.4v₂ >` everyone), bid up to
  `min(v, 0.95·0.4·v̂₂_LB)` — never overtakes, lifts d2's cost from m to ≈0.4v₂ at CTR 0.7 (the
  a peer-style "suppress everyone" margin swing pure-EU leaves on the table).
- **Ratchet fences:** behavioral typing (not id-string trust); rounds 0–~10 / UNKNOWN rival / 13-agent
  (`num_agents > num_slots`, audit #5) → champion path verbatim; **Agent 2 untouched** (implement C′
  additively; Task-2 code path bit-identical). d3 *shaping* is a C2 extension, out of scope (d3 slack).

### Measurement overhaul (the biggest hidden leverage)
The 5000-sim absolute-margin CI is **±1470** (per-sim sd ≈53k), so the champion's **+58 d1 and −1263
d2 are within noise** — the current holdout can't certify "beats all 3". Fixes:
- **Threadless replica sim** (import `run_gsp_auction`, call agents in server order) ≈ **100× faster**;
  **gate: byte-identical utilities on 30 seeds vs the real server before trusting a single number.**
- **Control variates** on the seed-reconstructable draws `(v_ours,v1,v2,v3,T_ctr,d_ctr)` (known means)
  → CI shrink ×2–3.
- **50k fast-sim verdict** (~1 hr) = the real "beats all 3" certificate against a high-NUM_SIMULATIONS grader.

### Staged experiment (disjoint blocks per exp_valueaware.py; kill-switch at ~hour 8)
- **Stage 0 — oracle kill test (cheapest falsifier, before any estimator):** J-policy with the *true*
  `v_i` injected; fast-sim N=400, arms `w0∈{0,0.5,1}`. **Kill if** no arm shows paired-vs-champion d2
  ≥ **+1500** with d1 change ≥ **−200** → policy has no headroom, stop, keep champion.
- **Stage 1** — estimator unit tests (no sim): v̂₂ within 3% by 300 rounds across censoring rates; d3
  predictor exact; typing confusion = 0.
- **Stage 2** — full C′ screen, fast-sim N=400, CRN-paired vs cached champion. Gates: d2 ≥ +1500,
  d1 ≥ −100 (not sig-neg), d3 ≥ −3000.
- **Stage 3** — confirm, fast-sim N=2000, control-variate-adjusted margins all > 0.
- **Stage 4 — holdout + ratchet (real server):** N=5000 @ block 400000, single frozen arm. Accept iff
  (1) all 3 CV-adjusted margins > 0, binding-margin CI-LB > −250; (2) paired d2 ≥ +1300 sig, d1 ≥ 0
  point (CI-LB > −300), d3 not worse than −3000; (3) **50k fast-sim: all 3 margins CI-LB > 0**;
  (4) ratchet — Agent 2 bit-identical + Task 2 unchanged, 13-agent no-regression, latency p99 under cap,
  public_tests + mutation + full suite green. Any fail → keep champion.
- **Earliest falsifiers:** fast-sim byte-match fails (fix rig) → Stage-0 oracle can't clear (policy has
  no headroom; a peer's edge is elsewhere, e.g. d3 shaping) → `w0=0` beats `w0>0` on d1 (suppression
  theory of the d1 win is wrong — valuable either way).

Budget ≈ 2–3 working days, kill-switch at ~hour 8.

## Robustness layer — a partner's review, reconciled (2026-07-11)
a partner reviewed Agent 1 **robustness-first** (beat the 3 dummies AND unseen competitive agents; *don't
overfit to dummy formulas*). His prompt and C′ have a real tension, resolved by the **grading
structure**, not compromise:
- **40 pts = beat the 3 KNOWN dummies** (public code) → C′'s exact exploit (`v̂_i`, exact integration,
  `b*`) is legitimate and stays. Modeling public code is not overfitting.
- **10 pts = competitive vs UNKNOWN student agents** → a partner's robustness layer applies.
- **Bridge = behavioral typing** (already in C′): typed rival → exploit (C′); UNKNOWN/volatile →
  robust path (a partner). Complementary, gated by type.

### Fold in (additive — upgrades C′, no regression)
1. **Flesh out C′'s UNKNOWN fallback** (today just "→ champion path"). For untyped rivals use an
   opponent-agnostic policy: per-opponent online stats `{last, rolling mean, variance, max, count,
   recency, stability}`; predict next bid from recent+historical (not last round); **uncertainty-aware
   margin** scaled by variance/stability (wide for volatile, ~ε for stable) instead of fixed
   `threshold+ε`; **candidate-set EU** (`0`, fractions of `v`, `v`, predicted-threshold+margin) over
   several plausible rankings; **risk-adjusted score `E[u] − λ·uncertainty`**. Earns the competitive
   10 pts; strict upgrade over "fall back to champion".
2. **Opponent-family robustness bench** (NEW ratchet dimension). Add synthetic opponents to the
   harness; require no-regression across ALL: truthful, fixed-shade, random-shade, adaptive-recent-
   price, strategy-switcher, other best-responders. Report mean, 95% CI, **worst-case**, and by-family.
   The 3 real dummies are regression tests, not the whole spec.
3. **Comparison matrix** (a partner's required output) → experiment arms: current champion / robust-opponent-
   aware / raise_top-OFF / conservative-raise_top.

### a partner INDEPENDENTLY CONFIRMS (already in C′ — validation, no change)
- "best-responds to last round as if it repeats" → C′ already uses distribution-aware BR over
  accumulated stats.
- "top bid = arbitrary `slot0·1.1+1`" → C′ already treats it as a censoring **interval / lower bound**,
  not a point (self-ref bug gone).
- "conservative raise_top only when top directly observed & overtake prob negligible" → **exactly**
  C′'s rule (raise only vs a deterministic/directly-observed top; never vs a stochastic top on a stale
  estimate).

### Minor arms (cheap A/B, low priority)
- Cold open: `0.9·v` vs truthful `v` vs a short bounded exploration.
- Bottom slot: `0` vs a tiny positive bid (tie-order dependence — real but low-impact in the 4-agent
  40-pt regime; matters more when `#agents > #slots`).

### DO NOT adopt (would regress C′) — regression guard
- **Don't drop the exact dummy exploit** for the typed 40-pt regime. "Don't overfit to dummy formulas"
  applies to the UNKNOWN path only; against the known dummies the exact models ARE the 40-pt driver.
- **Don't replace C′'s exact per-round integration with sampled/candidate-set EU for the KNOWN field** —
  exact is strictly better; candidate-set EU is only for the untyped, multi-stochastic-rival case.
- **Keep `b*`** (provable IR-safety, `v̂₂`-independent) as the typed-path profitability gate; the
  risk-adjusted score is the UNKNOWN-path analogue, not a replacement.
- Keep the measurement overhaul (replica sim, control variates, oracle kill-test) — unaffected.

### Agent 2 (per a partner): don't redesign
Only verify per-sim reset, budget/time limits, and no unsafe inheritance from the shared logic —
matches C′ (Agent 2 untouched).
