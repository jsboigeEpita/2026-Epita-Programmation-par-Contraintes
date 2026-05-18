from solver import Solution
from typing import List, Dict
import pickle

SOLUTION_FILE = "solution_shuffle.pkl"
SOLUTION_FILE = "solution_cp-sat.pkl"

with open(SOLUTION_FILE, "rb") as input_file:
    solution = pickle.load(input_file)

def calculate_max_affinity(solution: Solution):
	num_committees = solution.problem_data.num_committees
	operators = solution.problem_data.operators

	for t in solution.assignment.keys():
		operators_per_committee: List[Dict[int, int]] = [{} for _ in range(num_committees)]
		for v, c in solution.assignment[t].items():
			operators_per_committee[c].setdefault(operators[v], 0)
			operators_per_committee[c][operators[v]] += 1
		
		for c in range(num_committees):
			max_affinity = max(operators_per_committee[c].values()) / sum(operators_per_committee[c].values())
			print(f"{round(100 * max_affinity, 2)}%")
	# print(operators_per_committee)

calculate_max_affinity(solution)


	
