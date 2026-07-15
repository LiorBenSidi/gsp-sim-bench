"""Absolute-utility benchmark of the SHIPPED hybrid Task-1 agent, matching the original champion
artifact config exactly: seeds 0..4999 (block 0), N=5000, T=3000, 4-agent field (ours + 3 dummies),
replica engine (byte-identical to server.py). Reports each agent's mean Average-Utility + 95% CI --
the exact quantity the grader ranks on -- so both pairs can compare on identical seeds. Single core."""
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
from hw3.agent1 import BiddingAgent1   # the shipped hybrid

NS, T, N = CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS, 5000


def field():
    a = BiddingAgent1(); a.id = "ours"
    d1 = id_dummy_1.BiddingAgent1(); d1.id = "d1"
    d2 = id_dummy_2.BiddingAgent1(); d2.id = "d2"
    d3 = id_dummy_3.BiddingAgent1(); d3.id = "d3"
    return [a, d1, d2, d3]


f = field()
cols = {"ours": [], "d1": [], "d2": [], "d3": []}
for s in range(N):
    random.seed(s)
    u = sim(f, NS, T, enforce_budget=False)
    for k in cols:
        cols[k].append(u[k])
    if (s + 1) % 500 == 0:
        print(f"  {s + 1}/{N}", file=sys.stderr, flush=True)


def ci(xs):
    return statistics.fmean(xs), 1.96 * statistics.pstdev(xs) / (len(xs) ** 0.5)


print(f"HYBRID Task-1 absolute Average Utility — seeds 0..{N - 1}, N={N}, T={T} (replica == server.py)\n")
rows = sorted(cols.items(), key=lambda kv: statistics.fmean(kv[1]), reverse=True)
for rank, (name, xs) in enumerate(rows, 1):
    m, c = ci(xs)
    tag = " <- OURS" if name == "ours" else ""
    print(f"  {rank}. {name:6s} {m:10.1f}  ± {c:7.1f}{tag}")
