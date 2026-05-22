from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ortools.sat.python import cp_model

import time


@dataclass(frozen=True)
class ProblemData:
	"""Input data for the CP-SAT committee assignment model."""
	num_validators: int
	operators: Sequence[int]
	num_committees: int
	time_steps: int
	min_size: int
	max_size: int
	target_size: Optional[int] = None
	max_per_operator: Optional[int] = None
	active_by_time: Optional[Sequence[Iterable[int]]] = None


@dataclass
class Solution:
	"""Solver output with assignments and derived metrics."""
	status: int
	objective: float
	assignment: Dict[int, Dict[int, int]]
	loads: Dict[int, int]
	committee_sizes: Dict[Tuple[int, int], int]
	metrics: Dict[str, int]
	problem_data: ProblemData

	def pretty(self, max_validators: int = 10, max_times: int = 3) -> str:
		"""Return a human-readable summary of the solution."""
		lines: List[str] = []
		lines.append(f"status={self.status} objective={self.objective}")
		lines.append(f"metrics={self.metrics}")
		lines.append(f"loads(sample)={dict(list(self.loads.items())[:max_validators])}")
		shown_times = sorted(self.assignment.keys())[:max_times]
		for t in shown_times:
			assignments = self.assignment.get(t, {})
			items = sorted(assignments.items())[:max_validators]
			lines.append(f"t={t} assignments(sample)={dict(items)}")
		if len(self.assignment) > max_times:
			lines.append("...more time steps omitted...")
		if len(self.loads) > max_validators:
			lines.append("...more validators omitted...")
		return "\n".join(lines)

	def __str__(self) -> str:
		"""Default string representation using pretty()."""
		return self.pretty()


def _build_model(data: ProblemData, weights: Dict[str, int]) -> Tuple[cp_model.CpModel, Dict[str, Dict]]:
	"""Create the CP-SAT model and return it with key variables."""
	model = cp_model.CpModel()

	validators = list(range(data.num_validators))
	committees = list(range(data.num_committees))
	times = list(range(data.time_steps))

	if len(data.operators) != data.num_validators:
		raise ValueError("operators length must match num_validators")

	active_by_time: List[Optional[set]] = []
	if data.active_by_time is None:
		active_by_time = [None for _ in times]
	else:
		if len(data.active_by_time) != data.time_steps:
			raise ValueError("active_by_time must match time_steps")
		active_by_time = [set(items) for items in data.active_by_time]

    # Creating the decision variables
	x: Dict[Tuple[int, int, int], cp_model.IntVar] = {}
	for v in validators:
		for c in committees:
			for t in times:
				x[(v, c, t)] = model.new_bool_var(f"x_v{v}_c{c}_t{t}")

	# Assignment constraints (one committee per validator per time when active).
	for v in validators:
		for t in times:
			if active_by_time[t] is not None and v not in active_by_time[t]:
				for c in committees:
					model.add(x[(v, c, t)] == 0)
			else:
				model.add(sum(x[(v, c, t)] for c in committees) == 1)

	# Committee size constraints and target-size deviation.
	committee_sizes: Dict[Tuple[int, int], cp_model.IntVar] = {}
	size_deviation: Dict[Tuple[int, int], cp_model.IntVar] = {}
	for c in committees:
		for t in times:
			size_var = model.new_int_var(0, data.num_validators, f"size_c{c}_t{t}")
			model.add(size_var == sum(x[(v, c, t)] for v in validators))
			model.add(size_var >= data.min_size)
			model.add(size_var <= data.max_size)
			committee_sizes[(c, t)] = size_var

			if data.target_size is not None:
				dev = model.new_int_var(0, data.num_validators, f"dev_c{c}_t{t}")
				model.add(dev >= size_var - data.target_size)
				model.add(dev >= data.target_size - size_var)
				size_deviation[(c, t)] = dev

	# Load balance: minimize max-min of validator loads.
	loads: Dict[int, cp_model.IntVar] = {}
	for v in validators:
		load = model.new_int_var(0, data.time_steps, f"load_v{v}")
		model.add(load == sum(x[(v, c, t)] for c in committees for t in times))
		loads[v] = load

	load_max = model.new_int_var(0, data.time_steps, "load_max")
	load_min = model.new_int_var(0, data.time_steps, "load_min")
	model.add_max_equality(load_max, [loads[v] for v in validators])
	model.add_min_equality(load_min, [loads[v] for v in validators])
	imbalance = model.new_int_var(0, data.time_steps, "imbalance")
	model.add(imbalance == load_max - load_min)

	# Operator anti-affinity: count per operator/committee/time and penalize excess.
	operators = sorted(set(data.operators))
	excess_terms: List[cp_model.IntVar] = []
	for o in operators:
		for c in committees:
			for t in times:
				op_validators = [v for v in validators if data.operators[v] == o]
				if not op_validators:
					continue
				n_op = model.new_int_var(0, len(op_validators), f"n_op{o}_c{c}_t{t}")
				model.add(n_op == sum(x[(v, c, t)] for v in op_validators))
				if data.max_per_operator is not None:
					model.add(n_op <= data.max_per_operator)
				excess = model.new_int_var(0, len(op_validators), f"excess_op{o}_c{c}_t{t}")
				model.add(excess >= n_op - 1)
				model.add(excess >= 0)
				excess_terms.append(excess)

	# Churn between time steps (0 if same committee, 1 if changed).
	churn_terms: List[cp_model.IntVar] = []
	if data.time_steps > 1:
		for v in validators:
			for t in times[1:]:
				if active_by_time[t] is not None:
					if v not in active_by_time[t] or v not in active_by_time[t - 1]:
						continue
				stayed = model.new_int_var(0, 1, f"stayed_v{v}_t{t}")
				same_bools = []
				for c in committees:
					same = model.new_bool_var(f"same_v{v}_c{c}_t{t}")
					model.add(same <= x[(v, c, t)])
					model.add(same <= x[(v, c, t - 1)])
					model.add(same >= x[(v, c, t)] + x[(v, c, t - 1)] - 1)
					same_bools.append(same)
				model.add(stayed == sum(same_bools))
				churn = model.new_int_var(0, 1, f"churn_v{v}_t{t}")
				model.add(churn + stayed == 1)
				churn_terms.append(churn)

	# Objective: weighted sum of imbalance, anti-affinity, churn, target-size deviation.
	objective_terms: List[cp_model.IntVar] = []

	if weights.get("imbalance", 0) > 0:
		objective_terms.append(imbalance * weights["imbalance"])

	if weights.get("anti_affinity", 0) > 0 and excess_terms:
		anti_affinity = model.new_int_var(0, len(excess_terms) * data.num_validators, "anti_affinity")
		model.add(anti_affinity == sum(excess_terms))
		objective_terms.append(anti_affinity * weights["anti_affinity"])
	else:
		anti_affinity = model.new_int_var(0, 0, "anti_affinity")

	if weights.get("churn", 0) > 0 and churn_terms:
		churn_sum = model.new_int_var(0, len(churn_terms), "churn_sum")
		model.add(churn_sum == sum(churn_terms))
		objective_terms.append(churn_sum * weights["churn"])
	else:
		churn_sum = model.new_int_var(0, 0, "churn_sum")

	if weights.get("size_deviation", 0) > 0 and size_deviation:
		dev_sum = model.new_int_var(0, len(size_deviation) * data.num_validators, "size_deviation_sum")
		model.add(dev_sum == sum(size_deviation.values()))
		objective_terms.append(dev_sum * weights["size_deviation"])
	else:
		dev_sum = model.new_int_var(0, 0, "size_deviation_sum")

	if objective_terms:
		model.minimize(sum(objective_terms))

	vars_out = {
		"x": x,
		"loads": loads,
		"committee_sizes": committee_sizes,
		"imbalance": imbalance,
		"anti_affinity": anti_affinity,
		"churn_sum": churn_sum,
		"size_deviation_sum": dev_sum,
	}

	return model, vars_out


def solve(data: ProblemData, weights: Optional[Dict[str, int]] = None, time_limit_s: float = 10.0) -> Solution:
	"""Solve the CP-SAT model and return a Solution object."""
	if weights is None:
		weights = {
			"imbalance": 100,
			"anti_affinity": 10,
			"churn": 1,
			"size_deviation": 1,
		}

	before_time = time.time()
	model, vars_out = _build_model(data, weights)

	print(f"Model fully built in {time.time() - before_time}")
	solver = cp_model.CpSolver()
	solver.parameters.max_time_in_seconds = time_limit_s

	before_time = time.time()
	status = solver.solve(model)
	print(f"Model fully sovled in {time.time() - before_time}")

	assignment: Dict[int, Dict[int, int]] = {t: {} for t in range(data.time_steps)}
	loads: Dict[int, int] = {}
	committee_sizes: Dict[Tuple[int, int], int] = {}

	if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
		for v in range(data.num_validators):
			loads[v] = int(solver.value(vars_out["loads"][v]))

		for (c, t), size_var in vars_out["committee_sizes"].items():
			committee_sizes[(c, t)] = int(solver.value(size_var))

		for v in range(data.num_validators):
			for t in range(data.time_steps):
				for c in range(data.num_committees):
					if solver.value(vars_out["x"][(v, c, t)]) == 1:
						assignment[t][v] = c
						break

	metrics = {
		"imbalance": int(solver.value(vars_out["imbalance"])) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 0,
		"anti_affinity": int(solver.value(vars_out["anti_affinity"])) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 0,
		"churn": int(solver.value(vars_out["churn_sum"])) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 0,
		"size_deviation": int(solver.value(vars_out["size_deviation_sum"])) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 0,
	}

	return Solution(
		status=status,
		objective=float(solver.objective_value) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 0.0,
		assignment=assignment,
		loads=loads,
		committee_sizes=committee_sizes,
		metrics=metrics,
		problem_data=data
	)


def solve_static(
	num_validators: int,
	operators: Sequence[int],
	num_committees: int,
	min_size: int,
	max_size: int,
	target_size: Optional[int] = None,
	max_per_operator: Optional[int] = None,
	weights: Optional[Dict[str, int]] = None,
	time_limit_s: float = 10.0,
) -> Solution:
	"""Solve a single time-step instance (time_steps=1)."""
	data = ProblemData(
		num_validators=num_validators,
		operators=operators,
		num_committees=num_committees,
		time_steps=1,
		min_size=min_size,
		max_size=max_size,
		target_size=target_size,
		max_per_operator=max_per_operator,
		active_by_time=None,
	)
	return solve(data, weights=weights, time_limit_s=time_limit_s)
