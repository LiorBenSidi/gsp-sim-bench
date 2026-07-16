"""Run ONE task of the real grader (server.py functions) at CONSTANTS.NUM_SIMULATIONS, unseeded,
honouring CONSTANTS.ENFORCE_TIME_CAP -- so enforced N=10,000 can run per-task (each task its own
CI job, to fit the 6h runner limit). Prints the same per-dummy 95% threshold check server.py does.

Run from a dir containing server.py, CONSTANTS.py, id_dummy_1/2/3.py, and the agent bundle id_*.py.
Usage: python grade_one.py <task 1|2>
"""
import sys

import CONSTANTS
import server

task = int(sys.argv[1]) if len(sys.argv) > 1 else 1
cls = "BiddingAgent1" if task == 1 else "BiddingAgent2"
enforce_budget = (task == 2)

agents = server.load_agents(cls)
print(f"== Real grader (server.py fns), Task {task}: NUM_SIMULATIONS={CONSTANTS.NUM_SIMULATIONS}, "
      f"ENFORCE_TIME_CAP={CONSTANTS.ENFORCE_TIME_CAP}, unseeded ==", flush=True)

sums = {}
for sim in range(CONSTANTS.NUM_SIMULATIONS):
    u = server.run_simulation(agents, CONSTANTS.NUM_SLOTS, CONSTANTS.T_ROUNDS,
                              enforce_budget=enforce_budget)
    for a, v in u.items():
        sums[a] = sums.get(a, 0.0) + v
    if (sim + 1) % 500 == 0:
        print(f"  {sim + 1}/{CONSTANTS.NUM_SIMULATIONS}", file=sys.stderr, flush=True)

avg = {a: s / CONSTANTS.NUM_SIMULATIONS for a, s in sums.items()}
for a_id, u in sorted(avg.items(), key=lambda kv: kv[1], reverse=True):
    print(f"Agent {a_id:28} | Average Utility: {u:12.2f}")
server.print_threshold_check(f"Task {task}", avg)
