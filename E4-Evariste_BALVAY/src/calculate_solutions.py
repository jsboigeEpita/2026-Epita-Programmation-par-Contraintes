from solver import solve, ProblemData
from random_shuffle import solve_rng
from milp_solver import solve_milp
from typing import List
import math
import pickle

def save_object(obj, filename):
    with open(filename, 'wb') as outp:
        pickle.dump(obj, outp, pickle.HIGHEST_PROTOCOL)

def create_operators_list_from_proportion(proportions: List[float], num_validators: int):
	"""Create the operators list based on the proportions of the biggest operators and the number of validators.

	Example
	-----
		create_operators_list_from_proportion([50, 25], 10) -> [0,0,0,0,0,1,1,1,2,3]
	"""
	if num_validators < 0:
		raise ValueError('The number of validators must be non-negative')
	if any(p < 0 for p in proportions):
		raise ValueError('Proportions must be non-negative')
	if sum(proportions) > 100:
		raise ValueError('The sum of the proportions is greater than 100%')

	if num_validators == 0:
		return []

	raw_counts = [(p / 100.0) * num_validators for p in proportions]
	base_counts = [int(count) for count in raw_counts]

	remainder = num_validators - sum(base_counts)
	if remainder > 0 and base_counts:
		fractional = [count - int(count) for count in raw_counts]
		order = sorted(range(len(fractional)), key=lambda i: (-fractional[i], i))
		for i in order[:remainder]:
			base_counts[i] += 1

	operators = []
	for i, count in enumerate(base_counts):
		operators.extend([i] * count)

	next_operator = len(base_counts)
	remaining = num_validators - len(operators)
	for i in range(remaining):
		operators.append(next_operator + i)

	return operators


# Simple example
# my_data = ProblemData(
#     num_validators=6,
# 	operators=[1,1,1,3,3,3],
# 	num_committees=2,
#     time_steps=1,
# 	min_size=2,
# 	max_size=4,
# 	target_size=3,
# 	max_per_operator=None,
#     active_by_time=None,
# )


# More realistic example
# num_validators = 10000
# num_committees = min(math.ceil(num_validators / 256), 64)
# operators = create_operators_list_from_proportion([24, 9, 9, 9, 6, 4], num_validators)

# my_data = ProblemData(
#     num_validators=num_validators,
# 	operators=operators,
# 	num_committees=num_committees,
#     time_steps=1,
# 	min_size=128,
# 	max_size=9999999,
# 	target_size=num_validators // num_committees,
# 	max_per_operator=None,
#     active_by_time=None,
# )

# Solve using random shuffle
# solution = solve_rng( #Solved 87s
#     data=my_data,
#     weights={
# 			"imbalance": 100,
# 			"anti_affinity": 10,
# 			"churn": 1,
# 			"size_deviation": 1,
# 		}
# )
# save_object(solution, 'solution_shuffle.pkl')

# Solve using CP-SAT Build: 49s   Solved: 319s
# solution = solve(
#     data=my_data,
#     weights={
# 			"imbalance": 100,
# 			"anti_affinity": 10,
# 			"churn": 1,
# 			"size_deviation": 1,
# 		},
# 	time_limit_s=99999999999.0
# )
# save_object(solution, 'solution_cp-sat.pkl')

# Solve using MILP Build: 45s   Solved: 704s
# solution = solve_milp(
#     data=my_data,
#     weights={
# 			"imbalance": 100,
# 			"anti_affinity": 10,
# 			"churn": 1,
# 			"size_deviation": 1,
# 		},
# 	time_limit_s=99999999999.0
# )
# save_object(solution, 'solution_milp.pkl')


# Multiples time frames
num_validators = 1000
num_committees = min(math.ceil(num_validators / 256), 64)
operators = create_operators_list_from_proportion([24, 9, 9, 9, 6, 4], num_validators)

my_data = ProblemData(
    num_validators=num_validators,
	operators=operators,
	num_committees=num_committees,
    time_steps=10,
	min_size=128,
	max_size=9999999,
	target_size=num_validators // num_committees,
	max_per_operator=None,
    active_by_time=None,
)

solution = solve(
    data=my_data,
    weights={
			"imbalance": 100,
			"anti_affinity": 10,
			"churn": 1,
			"size_deviation": 1,
		},
	time_limit_s=99999999.0
)
save_object(solution, 'solution_cp-sat2.pkl')