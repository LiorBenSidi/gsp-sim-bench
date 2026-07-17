"""Run ONE task for N unseeded fast-mode sims using ALL CPU CORES (multiprocessing), emit JSON
{task, n, sums, avg} on stdout.

The sims are embarrassingly parallel, so instead of running N sims sequentially (server.py wraps
each call in a per-call threadpool -> slow), we fan the N sims across os.cpu_count() worker
PROCESSES. Each worker runs a disjoint chunk with FRESH agents and a UNIQUE RNG seed, so the chunks
are independent samples whose per-agent sums add up to the single big-N mean. `seed_base` offsets a
shard's seeds so shards never overlap; summing all shards' sums / total_n = the N-total mean.

Run from a dir with server.py, CONSTANTS.py, id_dummy_1/2/3.py, and the agent bundle id_*.py.
Usage: python grade_shard.py <task 1|2> <n_sims> [seed_base]
"""
import json
import multiprocessing as mp
import os
import sys


def _run_chunk(args):
    import random

    import CONSTANTS
    import server
    task, n_chunk, seed = args
    random.seed(seed)  # unique per worker -> independent sample stream (required: forked workers
    #                    would otherwise share the parent RNG state and produce identical sims)
    cls = "BiddingAgent1" if task == 1 else "BiddingAgent2"
    enforce_budget = (task == 2)
    agents = server.load_agents(cls)  # fresh agent instances in this worker
    sums = {}
    for _ in range(n_chunk):
        u = server.run_simulation(agents, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS,
                                  enforce_budget=enforce_budget)
        for a, v in u.items():
            sums[a] = sums.get(a, 0.0) + v
    return sums


def main():
    task = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 25000
    seed_base = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    workers = os.cpu_count() or 2
    base, rem = divmod(n, workers)
    chunks = [base + (1 if i < rem else 0) for i in range(workers)]
    jobs = [(task, chunks[i], seed_base + 1 + i) for i in range(workers) if chunks[i] > 0]
    print(f"task={task} n={n} workers={workers} chunks={chunks} seed_base={seed_base}",
          file=sys.stderr, flush=True)
    with mp.Pool(len(jobs)) as pool:
        results = pool.map(_run_chunk, jobs)
    total = {}
    for s in results:
        for a, v in s.items():
            total[a] = total.get(a, 0.0) + v
    avg = {a: v / n for a, v in total.items()}
    print(json.dumps({"task": task, "n": n, "workers": workers, "sums": total, "avg": avg}))


if __name__ == "__main__":
    main()
