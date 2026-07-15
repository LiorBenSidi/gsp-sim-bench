"""Answer 'is the win significant?' correctly: the ABSOLUTE per-agent CI (~±1000) is dominated by the
shared U(0,100) value draw. Because every agent faces the SAME seeds (CRN), the PAIRED margin
(ours - dummy_k) per sim cancels that variance and has a far tighter CI. Reports, on seeds 0..4999
(N=5000, T=3000, replica == server.py), each paired margin's mean + 95% CI + whether it excludes 0.
Single core."""
import random
import statistics
import sys
from pathlib import Path

ROOT = Path("/Users/liorben/dev/ec-hw3-gsp-bidding-bot")
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "fixtures"))
sys.path.insert(0, str(ROOT / "src"))

import CONSTANTS
import id_dummy_1, id_dummy_2, id_dummy_3
from replica_sim import run_simulation_replica as sim
from hw3.agent1 import BiddingAgent1   # shipped hybrid

NS, T, N = CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS, 5000

a = BiddingAgent1(); a.id = "ours"
d1 = id_dummy_1.BiddingAgent1(); d1.id = "d1"
d2 = id_dummy_2.BiddingAgent1(); d2.id = "d2"
d3 = id_dummy_3.BiddingAgent1(); d3.id = "d3"
f = [a, d1, d2, d3]

pair = {"d1": [], "d2": [], "d3": []}
absu = {"ours": [], "d1": [], "d2": [], "d3": []}
for s in range(N):
    random.seed(s)
    u = sim(f, NS, T, enforce_budget=False)
    for k in absu:
        absu[k].append(u[k])
    for k in pair:
        pair[k].append(u["ours"] - u[k])
    if (s + 1) % 1000 == 0:
        print(f"  {s + 1}/{N}", file=sys.stderr, flush=True)


def ci(xs):
    return statistics.fmean(xs), 1.96 * statistics.pstdev(xs) / (len(xs) ** 0.5)


print(f"seeds 0..{N - 1}, N={N}, T={T}\n")
print("ABSOLUTE per-agent CI (wide -- dominated by the shared value draw):")
for k in ("ours", "d1", "d2", "d3"):
    m, c = ci(absu[k]); print(f"  {k:5s} {m:10.1f} +- {c:7.1f}")
print("\nPAIRED margin ours - dummy_k (CRN -- the correct, tight test):")
for k in ("d1", "d2", "d3"):
    m, c = ci(pair[k])
    sig = "SIGNIFICANT (CI excludes 0)" if abs(m) > c else "not significant (CI includes 0)"
    print(f"  ours - {k}: {m:+9.1f} +- {c:6.1f}   -> {'WIN' if m > 0 else 'LOSS'}, {sig}")
