"""Value-aware Agent-1 search: can a near-truthful `b = c*v` beat EACH dummy (esp. dummy2)?

Follows the reviewed protocol:
  - metric = per-sim PAIRED margin  min_k (u_ours - u_dummy_k)  (beat the CLOSEST dummy);
    report its mean +- 95% CI (paired within-sim differences -> low variance).
  - pilot measures sd of the paired differences per dummy (NOT the marginal sigma) to size N.
  - DISJOINT seed blocks: pilot / screen / confirm / holdout (offsets below) so selection luck
    can't carry into confirmation.
  - fixed id-handling: set agent.id = label directly (never wrap get_id) -- avoids the relabel
    bug that corrupted earlier runs. Field built once + reused across sims (matches the grader).
  - candidates are deterministic (c*v uses no RNG) so CRN pairing stays structurally valid.

Usage: PYTHONPATH=src python harness/exp_valueaware.py <mode> <N>
  mode = pilot | screen | confirm | holdout    (default: screen 400)
"""
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "fixtures"))
sys.path.insert(0, str(ROOT / "src"))
import CONSTANTS  # noqa: E402
import id_dummy_1  # noqa: E402
import id_dummy_2  # noqa: E402
import id_dummy_3  # noqa: E402
import server as grader  # noqa: E402
from _progress import ticker  # noqa: E402
from dummy1_hunt import (  # noqa: E402
    ConstSuppressAgent1,
    DescentRaiseAgent1,
    DescentRaiseCondAgent1,
    DirectD1MarginAgent1,
    TunableDescentAgent1,
)
from margin_agent import BindingMarginAgent1, DescentAgent1, MarginAgent1  # noqa: E402
from replica_sim import run_simulation_replica  # noqa: E402
from robust_agent import RobustAgent1  # noqa: E402
from robust_raise_agent import RobustRaiseAgent1  # noqa: E402

from hw3.agent1 import BiddingAgent1 as Champion  # noqa: E402

BLOCK = {"pilot": 100_000, "screen": 0, "confirm": 200_000, "holdout": 400_000}  # disjoint offsets
NS, T = CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS


class ConstBid:
    """Near-truthful Agent 1: bid c * own value every round (no history). Deterministic."""

    def __init__(self, c):
        self.c, self.id, self.value = c, "ours", 0.0

    def start_simulation(self, na, ns, ctr, v, tb, T):
        self.value = float(v)

    def get_bid(self, budget):
        bid = self.c * self.value
        if bid != bid or bid in (float("inf"), float("-inf")):
            return 0.0
        return max(0.0, bid)  # server clamps to [0, budget]; Task 1 budget = inf

    def notify_round_results(self, rr):
        pass

    def get_id(self):
        return self.id


def candidate(name):
    if name == "champion":
        a = Champion(); a.id = "ours"; return a
    if name == "robust":
        a = RobustAgent1(); a.id = "ours"; return a
    if name == "rraise0":
        a = RobustRaiseAgent1(delta_frac=0.0); a.id = "ours"; return a
    if name == "rraise1":
        a = RobustRaiseAgent1(delta_frac=0.002); a.id = "ours"; return a
    if name.startswith("marginA"):
        a = MarginAgent1(w=float(name[7:]) / 100.0); a.id = "ours"; return a   # marginA060 -> w=0.6
    if name == "descent":
        a = DescentAgent1(); a.id = "ours"; return a
    if name.startswith("bindC"):
        a = BindingMarginAgent1(w=float(name[5:]) / 100.0); a.id = "ours"; return a
    # --- d1-hunt candidates (recover descent's dummy1 deficit without losing dummy2) ---
    if name.startswith("dplus"):   # extend the descent trigger: dplus010 -> tol_frac=0.010
        a = TunableDescentAgent1(tol_frac=float(name[5:]) / 1000.0); a.id = "ours"; return a
    if name == "dtight":           # exact-value exploit: sit as close under the constant top as possible
        a = TunableDescentAgent1(eps=1e-6); a.id = "ours"; return a
    if name.startswith("csupp"):   # constant-only suppression weight: csupp010 -> w=0.10
        a = ConstSuppressAgent1(w=float(name[5:]) / 100.0); a.id = "ours"; return a
    if name.startswith("directd1"):  # direct d1-utility suppression: directd1050 -> lam=0.50
        a = DirectD1MarginAgent1(lam=float(name[8:]) / 100.0); a.id = "ours"; return a
    if name == "hybrid":             # descent descend + d2-neutral cost-raise (idea 5)
        a = DescentRaiseAgent1(); a.id = "ours"; return a
    if name.startswith("cond"):      # hybrid + d2-protected conditional descend: cond050 -> tol_frac=0.05
        a = DescentRaiseCondAgent1(tol_frac=float(name[4:]) / 1000.0); a.id = "ours"; return a
    return ConstBid(float(name[1:]))  # "c1.05" -> 1.05


# the logically-best scenarios to screen: options A (w-sweep), B, C (w-sweep) vs the two baselines
CANDIDATES = ["champion", "robust",
              "marginA030", "marginA060", "marginA100",
              "descent",
              "bindC060", "bindC100"]


def build_field(cand_name):
    cand = candidate(cand_name)
    d1 = id_dummy_1.BiddingAgent1(); d1.id = "d1"
    d2 = id_dummy_2.BiddingAgent1(); d2.id = "d2"
    d3 = id_dummy_3.BiddingAgent1(); d3.id = "d3"
    field = [cand, d1, d2, d3]
    assert cand.get_id() == "ours", "self-id sanity: agent must report the id it is credited by"
    return field


def _sim_fn(engine):
    return grader.run_simulation if engine == "real" else run_simulation_replica


def _run_chunk(args):
    """Worker: one candidate over a seed chunk (own field instance). Returns [(seed, row)]."""
    cand_name, chunk, engine = args
    field = build_field(cand_name)
    sim = _sim_fn(engine)
    out = []
    for s in chunk:
        random.seed(s)
        u = sim(field, NS, T, enforce_budget=False)
        out.append((s, (u["ours"], u["d1"], u["d2"], u["d3"])))
    return out


_CACHE_DIR = ROOT / "harness" / "baseline_cache"   # TRACKED (committed) -> works on the cloud too
# Only 'champion' is cached: its code is src/hw3 (the shipped submission -> truly frozen), so its
# per-sim rows never go stale, and it's the paired baseline present in every screen (re-running it
# cost ~9-29 min per cloud run). replica==real byte-identical, so the cache is engine-independent
# (keyed by candidate + seed block + N). robust/margin*/etc. are NEVER cached -- their code evolves.
_FROZEN = {"champion"}


def _cache_path(cand_name, seeds):
    return _CACHE_DIR / f"{cand_name}_b{seeds[0]}_N{len(seeds)}.json"


def run_field(cand_name, seeds, engine="real", jobs=1):
    """Per-sim (u_ours,u_d1,u_d2,u_d3) for a candidate over seeds. engine='real' -> fixtures/server.py,
    'replica' -> the byte-validated fast Task-1 sim. jobs>1 fans the INDEPENDENT sims across processes
    -- CRN-safe (each sim reseeds + resets) and byte-identical to jobs=1 (asserted by test). Only for
    engine='replica'; jobs is ignored for 'real'. FROZEN candidates load/save a per-sim cache."""
    seeds = list(seeds)
    cache = _cache_path(cand_name, seeds) if cand_name in _FROZEN else None
    if cache is not None and cache.exists():
        print(f"  [{cand_name}] {len(seeds)}/{len(seeds)} (cached)", file=sys.stderr, flush=True)
        return [tuple(r) for r in json.loads(cache.read_text())]
    if jobs <= 1 or engine == "real":
        field = build_field(cand_name)
        sim = _sim_fn(engine)
        out = []
        tick = ticker(len(seeds), cand_name)
        for i, s in enumerate(seeds, 1):
            random.seed(s)
            u = sim(field, NS, T, enforce_budget=False)
            out.append((u["ours"], u["d1"], u["d2"], u["d3"]))
            tick(i)
    else:
        import multiprocessing as mp
        k = min(jobs, len(seeds))
        chunks = [seeds[i::k] for i in range(k)]   # round-robin -> balanced load per worker
        # mp workers can't stream per-% ticks -> announce the field so the log isn't silent for
        # ~minutes between the last field's 100% line and this one's.
        print(f"  [{cand_name}] running {len(seeds)} sims [jobs={k}] (mp: no per-% ticks) ...",
              file=sys.stderr, flush=True)
        with mp.Pool(k) as pool:
            parts = pool.map(_run_chunk, [(cand_name, ch, engine) for ch in chunks])
        by_seed = {s: row for part in parts for (s, row) in part}
        print(f"  [{cand_name}] {len(seeds)}/{len(seeds)} (100%) [jobs={k}]", file=sys.stderr, flush=True)
        out = [by_seed[s] for s in seeds]
    if cache is not None:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(out))
    return out


def _ci(xs):
    m = statistics.fmean(xs)
    return m, 1.96 * statistics.pstdev(xs) / (len(xs) ** 0.5)


def diffs(rows):
    """per-sim paired differences ours-d1, ours-d2, ours-d3, and the binding min."""
    d1 = [o - a for (o, a, _b, _c) in rows]
    d2 = [o - b for (o, _a, b, _c) in rows]
    d3 = [o - c for (o, _a, _b, c) in rows]
    dmin = [min(x, y, z) for x, y, z in zip(d1, d2, d3, strict=True)]
    return {"d1": d1, "d2": d2, "d3": d3, "min": dmin}


def pilot(n, engine="real", jobs=1):
    seeds = range(BLOCK["pilot"], BLOCK["pilot"] + n)
    rows = run_field("champion", seeds, engine, jobs)
    d = diffs(rows)
    print(f"PILOT (champion, block@{BLOCK['pilot']}, N={n}) -- paired diffs ours - dummy_k:\n")
    print(f"  {'vs':<6}{'mean':>10}{'sd(paired)':>12}{'95% CI':>20}")
    binding, binding_mean = None, 1e18
    for k in ("d1", "d2", "d3"):
        m, ci = _ci(d[k])
        sd = statistics.pstdev(d[k])
        print(f"  {k:<6}{m:>10.0f}{sd:>12.0f}   [{m-ci:>8.0f},{m+ci:>8.0f}]")
        if m < binding_mean:
            binding, binding_mean = k, m
    sd_bind = statistics.pstdev(d[binding])
    print(f"\n  binding (closest) dummy = {binding}, mean margin {binding_mean:.0f}, "
          f"sd(paired) {sd_bind:.0f}")
    for tgt in (1000, 500, 250):
        n_need = (1.96 * sd_bind / tgt) ** 2
        print(f"    N for a +/-{tgt} CI on the binding margin ~ {n_need:,.0f} sims")
    print("  (marginal sigma ~34,000 would demand ~4,400 for +/-1000 -- paired is far cheaper.)")


def evaluate(cand_name, seeds, engine="real", jobs=1):
    rows = run_field(cand_name, seeds, engine, jobs)
    d = diffs(rows)
    m_min, ci_min = _ci(d["min"])
    per = {k: statistics.fmean(d[k]) for k in ("d1", "d2", "d3")}
    beats_all = all(v > 0 for v in per.values())
    return m_min, ci_min, per, beats_all


def screen(n, block="screen", cands=None, engine="real", jobs=1, baseline="champion"):
    cands = cands or CANDIDATES
    seeds = list(range(BLOCK[block], BLOCK[block] + n))
    print(f"{block.upper()} (block@{BLOCK[block]}, N={n}, engine={engine}, jobs={jobs}). Per-dummy ABSOLUTE "
          f"margin (noisy) and CRN-PAIRED advantage vs {baseline} if present (tight). WIN = all 3 abs > 0.\n")
    # per-sim per-dummy margins for every candidate on the SAME seeds -> paired comparison
    perdummy = {}
    for name in cands:
        perdummy[name] = diffs(run_field(name, seeds, engine, jobs))
    base = perdummy.get(baseline)   # paired baseline only if it is in the list
    for name in cands:
        d = perdummy[name]
        absm = {k: statistics.fmean(d[k]) for k in ("d1", "d2", "d3")}
        all3 = all(v > 0 for v in absm.values())
        binding = min(absm.values())
        print(f"  {name:<10} beats-all-3={'YES' if all3 else 'no ':<3} min {binding:>+7.0f}  "
              f"abs: d1 {absm['d1']:>+6.0f}  d2 {absm['d2']:>+6.0f}  d3 {absm['d3']:>+6.0f}")
        if base is not None and name != baseline:
            parts = []
            for k in ("d1", "d2", "d3"):
                adv = [a - b for a, b in zip(d[k], base[k], strict=True)]
                am, aci = _ci(adv)
                star = "sig" if abs(am) > aci else "   "
                parts.append(f"{k} {am:>+6.0f}+-{aci:>4.0f}{star}")
            print(f"             vs {baseline} (paired): " + "   ".join(parts))


# confirm list = champion (paired baseline) + margin candidates. Weights CORRECTED down: rival-spend
# is ~3x the own-utility scale, so w=0.6/1.0 (the first screen) over-suppress and tank own utility ->
# d1 gets WORSE. This sweep uses w in {0.10, 0.20} (a gentle nudge) + descent (weight-free). robust/
# rraise0 dropped (already measured). Narrow to [champion, <winner>] before a real holdout.
SHORTLIST = ["champion", "marginA010", "marginA020", "descent", "bindC010"]


MARGINS = ["marginA030", "marginA060", "marginA100", "descent", "bindC060", "bindC100"]  # new agents only

# d1-hunt: recover descent's dummy1 deficit (~-446 @ high N) without losing its dummy2 win. Baseline
# = descent (the shipped Task-1 policy). dplus = extend the trigger (tol sweep); dtight = exact-value
# tighter descent; csupp = constant-only suppression weight. Screened on the confirm block (200000),
# then the winner re-run on the holdout block (400000).
D1HUNT = ["descent", "dplus010", "dplus020", "dplus050", "dplus100", "dtight", "csupp010", "csupp020"]

# Round 2 (lean): the direct d1-utility maximizer (idea 4) -- sharpest, value-aware. Kept small so
# the screen is fast; run only if round 1 (D1HUNT) doesn't yield a clean 3/3.
D1HUNT2 = ["descent", "directd1025", "directd1050", "directd1100"]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "screen"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    engine = sys.argv[3] if len(sys.argv) > 3 else "real"   # Action passes no 3rd arg -> real server
    jobs = int(sys.argv[4]) if len(sys.argv) > 4 else 1     # replica-only multiprocessing fan-out
    if mode == "pilot":
        pilot(n, engine, jobs)
    elif mode == "margins":                                 # new agents only (don't re-run baselines)
        screen(n, "confirm", cands=MARGINS, engine=engine, jobs=jobs)
    elif mode == "d1hunt":                                  # d1-hunt screen on the confirm block
        screen(n, "confirm", cands=D1HUNT, engine=engine, jobs=jobs, baseline="descent")
    elif mode == "d1hunt2":                                 # round 2: direct d1-utility maximizer
        screen(n, "confirm", cands=D1HUNT2, engine=engine, jobs=jobs, baseline="descent")
    elif mode == "d1holdout":                               # d1-hunt winner on the disjoint holdout
        screen(n, "holdout", cands=D1HUNT, engine=engine, jobs=jobs, baseline="descent")
    elif mode == "custom":
        # Arbitrary candidate list + block via env (HW3_CANDS="descent,directd1005,...", HW3_BLOCK).
        # Lets each weight run as its OWN concurrent cloud Action -> ~1-field wall-clock instead of
        # a long sequential screen. Absolute margins are CRN-comparable across runs (same block/N/seeds).
        import os
        cands = [c.strip() for c in os.environ.get("HW3_CANDS", "descent").split(",") if c.strip()]
        block = os.environ.get("HW3_BLOCK", "confirm")
        screen(n, block, cands=cands, engine=engine, jobs=jobs, baseline="descent")
    elif mode in ("confirm", "holdout"):
        screen(n, mode, cands=SHORTLIST, engine=engine, jobs=jobs)
    else:
        screen(n, "screen", engine=engine, jobs=jobs)


if __name__ == "__main__":
    main()
