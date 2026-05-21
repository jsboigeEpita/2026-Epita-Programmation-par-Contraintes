from ortools.sat.python import cp_model
from melody.music_theory import scale_pitches, tonic_pitch_classes, dominant_or_leading_tone_pcs

def build_model(n_notes: int=16, scale_name: str='C_major', max_interval: int=7):
    model = cp_model.CpModel()
    domain = scale_pitches(scale_name)
    pitch = [model.NewIntVarFromDomain(cp_model.Domain.FromValues(domain), f'pitch_{t}') for t in range(n_notes)]
    tonic_pcs = tonic_pitch_classes(scale_name)
    _force_pitch_class(model, pitch[0], tonic_pcs)
    _force_pitch_class(model, pitch[-1], tonic_pcs)
    cadence_pcs = dominant_or_leading_tone_pcs(scale_name)
    _force_pitch_class(model, pitch[-2], cadence_pcs)
    for t in range(n_notes - 1):
        diff = model.NewIntVar(-24, 24, f'diff_{t}')
        model.Add(diff == pitch[t + 1] - pitch[t])
        abs_diff = model.NewIntVar(0, 24, f'abs_diff_{t}')
        model.AddAbsEquality(abs_diff, diff)
        model.Add(abs_diff <= max_interval)
        model.Add(abs_diff >= 1)
        model.Add(abs_diff != 6)
    return (model, pitch)

def _force_pitch_class(model, pitch_var, allowed_pcs: list[int]) -> None:
    allowed_values = []
    for p in range(0, 128):
        if p % 12 in allowed_pcs:
            allowed_values.append((p,))
    model.AddAllowedAssignments([pitch_var], allowed_values)

def add_soft_smoothness(model, pitch, weight: int) -> list:
    costs = []
    for t in range(len(pitch) - 1):
        diff = model.NewIntVar(-24, 24, f'smooth_diff_{t}')
        model.Add(diff == pitch[t + 1] - pitch[t])
        abs_diff = model.NewIntVar(0, 24, f'smooth_abs_{t}')
        model.AddAbsEquality(abs_diff, diff)
        excess = model.NewIntVar(0, 24, f'smooth_excess_{t}')
        model.AddMaxEquality(excess, [abs_diff - 2, model.NewConstant(0)])
        cost = model.NewIntVar(0, 24 * weight, f'smooth_cost_{t}')
        model.Add(cost == excess * weight)
        costs.append(cost)
    return costs

def add_soft_range(model, pitch, weight: int, min_range: int=12) -> list:
    max_pitch = model.NewIntVar(0, 127, 'max_pitch')
    min_pitch = model.NewIntVar(0, 127, 'min_pitch')
    model.AddMaxEquality(max_pitch, pitch)
    model.AddMinEquality(min_pitch, pitch)
    actual_range = model.NewIntVar(0, 127, 'range')
    model.Add(actual_range == max_pitch - min_pitch)
    deficit = model.NewIntVar(0, 127, 'range_deficit')
    model.AddMaxEquality(deficit, [min_range - actual_range, model.NewConstant(0)])
    cost = model.NewIntVar(0, 127 * weight, 'range_cost')
    model.Add(cost == deficit * weight)
    return [cost]

def add_soft_no_oscillation(model, pitch, weight: int) -> list:
    costs = []
    for t in range(len(pitch) - 2):
        is_same = model.NewBoolVar(f'osc_{t}')
        model.Add(pitch[t + 2] == pitch[t]).OnlyEnforceIf(is_same)
        model.Add(pitch[t + 2] != pitch[t]).OnlyEnforceIf(is_same.Not())
        cost = model.NewIntVar(0, weight, f'osc_cost_{t}')
        model.Add(cost == weight * is_same)
        costs.append(cost)
    return costs

def add_soft_direction_changes(model, pitch, weight: int) -> list:
    costs = []
    for t in range(1, len(pitch) - 1):
        a = model.NewIntVar(-24, 24, f'dir_a_{t}')
        b = model.NewIntVar(-24, 24, f'dir_b_{t}')
        model.Add(a == pitch[t] - pitch[t - 1])
        model.Add(b == pitch[t + 1] - pitch[t])
        up_a = model.NewBoolVar(f'up_a_{t}')
        up_b = model.NewBoolVar(f'up_b_{t}')
        model.Add(a > 0).OnlyEnforceIf(up_a)
        model.Add(a <= 0).OnlyEnforceIf(up_a.Not())
        model.Add(b > 0).OnlyEnforceIf(up_b)
        model.Add(b <= 0).OnlyEnforceIf(up_b.Not())
        same_direction = model.NewBoolVar(f'same_dir_{t}')
        model.Add(up_a == up_b).OnlyEnforceIf(same_direction)
        model.Add(up_a != up_b).OnlyEnforceIf(same_direction.Not())
        cost = model.NewIntVar(0, weight, f'dir_cost_{t}')
        model.Add(cost == weight * same_direction)
        costs.append(cost)
    return costs

def add_soft_strong_beat_consonance(model, pitch, weight: int, scale_name: str='C_major') -> list:
    from melody.music_theory import SCALES
    pcs = SCALES[scale_name]['pcs']
    triad_pcs = [pcs[0], pcs[2], pcs[4]]
    triad_pitches = [p for p in range(0, 128) if p % 12 in triad_pcs]
    costs = []
    for t in range(0, len(pitch), 2):
        is_on_triad = model.NewBoolVar(f'triad_{t}')
        model.AddAllowedAssignments([pitch[t]], [(p,) for p in triad_pitches]).OnlyEnforceIf(is_on_triad)
        cost = model.NewIntVar(0, weight, f'triad_cost_{t}')
        model.Add(cost == weight * (1 - is_on_triad))
        costs.append(cost)
    return costs

def add_soft_arch_contour(model, pitch, weight: int) -> list:
    n = len(pitch)
    target_lo = n // 3
    target_hi = 2 * n // 3
    max_val = model.NewIntVar(0, 127, 'arch_max')
    model.AddMaxEquality(max_val, pitch)
    is_peak = []
    for t in range(n):
        b = model.NewBoolVar(f'peak_{t}')
        model.Add(pitch[t] == max_val).OnlyEnforceIf(b)
        model.Add(pitch[t] != max_val).OnlyEnforceIf(b.Not())
        is_peak.append(b)
    in_zone_bools = is_peak[target_lo:target_hi + 1]
    if not in_zone_bools:
        return []
    peak_in_zone = model.NewBoolVar('peak_in_zone')
    model.AddBoolOr(in_zone_bools).OnlyEnforceIf(peak_in_zone)
    for b in in_zone_bools:
        model.AddImplication(peak_in_zone.Not(), b.Not())
    cost = model.NewIntVar(0, weight, 'arch_cost')
    model.Add(cost == weight * (1 - peak_in_zone))
    return [cost]
PROFILES = {'fluide': {'smoothness': 5, 'range': 1, 'direction': 1, 'no_oscillation': 3, 'strong_beat': 4, 'arch': 3}, 'aventureux': {'smoothness': 1, 'range': 5, 'direction': 3, 'no_oscillation': 2, 'strong_beat': 1, 'arch': 1}, 'minimaliste': {'smoothness': 3, 'range': 0, 'direction': 0, 'no_oscillation': 1, 'strong_beat': 2, 'arch': 0}}

def solve(n_notes: int=16, scale_name: str='C_major', profile: str='fluide', time_limit: float=10.0, random_seed: int=0) -> list[int] | None:
    model, pitch = build_model(n_notes=n_notes, scale_name=scale_name)
    weights = PROFILES[profile]
    all_costs = []
    if weights['smoothness'] > 0:
        all_costs += add_soft_smoothness(model, pitch, weights['smoothness'])
    if weights['range'] > 0:
        all_costs += add_soft_range(model, pitch, weights['range'])
    if weights['direction'] > 0:
        all_costs += add_soft_direction_changes(model, pitch, weights['direction'])
    if weights['no_oscillation'] > 0:
        all_costs += add_soft_no_oscillation(model, pitch, weights['no_oscillation'])
    if weights.get('strong_beat', 0) > 0:
        all_costs += add_soft_strong_beat_consonance(model, pitch, weights['strong_beat'], scale_name=scale_name)
    if weights.get('arch', 0) > 0:
        all_costs += add_soft_arch_contour(model, pitch, weights['arch'])
    if all_costs:
        model.Minimize(sum(all_costs))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.random_seed = random_seed
    solver.parameters.randomize_search = True
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return [solver.Value(p) for p in pitch]

def solve_many(n: int, **kwargs) -> list[list[int]]:
    melodies = []
    for seed in range(n):
        m = _solve_with_blocklist(blocklist=melodies, random_seed=seed, **kwargs)
        if m is None:
            break
        melodies.append(m)
    return melodies

def _solve_with_blocklist(blocklist: list[list[int]], **kwargs) -> list[int] | None:
    n_notes = kwargs.get('n_notes', 16)
    scale_name = kwargs.get('scale_name', 'C_major')
    profile = kwargs.get('profile', 'fluide')
    time_limit = kwargs.get('time_limit', 10.0)
    random_seed = kwargs.get('random_seed', 0)
    model, pitch = build_model(n_notes=n_notes, scale_name=scale_name)
    weights = PROFILES[profile]
    all_costs = []
    if weights['smoothness'] > 0:
        all_costs += add_soft_smoothness(model, pitch, weights['smoothness'])
    if weights['range'] > 0:
        all_costs += add_soft_range(model, pitch, weights['range'])
    if weights['direction'] > 0:
        all_costs += add_soft_direction_changes(model, pitch, weights['direction'])
    if weights['no_oscillation'] > 0:
        all_costs += add_soft_no_oscillation(model, pitch, weights['no_oscillation'])
    if weights.get('strong_beat', 0) > 0:
        all_costs += add_soft_strong_beat_consonance(model, pitch, weights['strong_beat'], scale_name=scale_name)
    if weights.get('arch', 0) > 0:
        all_costs += add_soft_arch_contour(model, pitch, weights['arch'])
    for prev_melody in blocklist:
        diff_bools = []
        for t in range(n_notes):
            b = model.NewBoolVar(f'diff_{len(blocklist)}_{t}')
            model.Add(pitch[t] != prev_melody[t]).OnlyEnforceIf(b)
            model.Add(pitch[t] == prev_melody[t]).OnlyEnforceIf(b.Not())
            diff_bools.append(b)
        model.AddBoolOr(diff_bools)
    if all_costs:
        model.Minimize(sum(all_costs))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.random_seed = random_seed
    solver.parameters.randomize_search = True
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return [solver.Value(p) for p in pitch]

def solve_with_fixed_notes(fixed_notes: list[int | None], scale_name: str='C_major', profile: str='fluide', time_limit: float=10.0, random_seed: int=0) -> list[int] | None:
    n_notes = len(fixed_notes)
    model, pitch = build_model(n_notes=n_notes, scale_name=scale_name)
    for t, fixed_value in enumerate(fixed_notes):
        if fixed_value is not None:
            model.Add(pitch[t] == fixed_value)
    weights = PROFILES[profile]
    all_costs = []
    if weights['smoothness'] > 0:
        all_costs += add_soft_smoothness(model, pitch, weights['smoothness'])
    if weights['range'] > 0:
        all_costs += add_soft_range(model, pitch, weights['range'])
    if weights['direction'] > 0:
        all_costs += add_soft_direction_changes(model, pitch, weights['direction'])
    if weights['no_oscillation'] > 0:
        all_costs += add_soft_no_oscillation(model, pitch, weights['no_oscillation'])
    if weights.get('strong_beat', 0) > 0:
        all_costs += add_soft_strong_beat_consonance(model, pitch, weights['strong_beat'], scale_name=scale_name)
    if weights.get('arch', 0) > 0:
        all_costs += add_soft_arch_contour(model, pitch, weights['arch'])
    if all_costs:
        model.Minimize(sum(all_costs))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.random_seed = random_seed
    solver.parameters.randomize_search = True
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return [solver.Value(p) for p in pitch]

def generate_variations(theme: list[int], n_variations: int=4, keep_positions: list[int] | None=None, **kwargs) -> list[list[int]]:
    n = len(theme)
    if keep_positions is None:
        keep_positions = [0, n - 1, n - 2] + list(range(0, n, 4))
        keep_positions = sorted(set(keep_positions))
    fixed_notes = [theme[t] if t in keep_positions else None for t in range(n)]
    variations = []
    blocklist = [theme]
    for seed in range(200):
        if len(variations) >= n_variations:
            break
        var = _variation_with_blocklist(fixed_notes=fixed_notes, blocklist=blocklist, random_seed=seed, **kwargs)
        if var is not None and var not in variations and (var != theme):
            variations.append(var)
            blocklist.append(var)
    return variations

def _variation_with_blocklist(fixed_notes: list[int | None], blocklist: list[list[int]], scale_name: str='C_major', profile: str='fluide', time_limit: float=5.0, random_seed: int=0) -> list[int] | None:
    n_notes = len(fixed_notes)
    model, pitch = build_model(n_notes=n_notes, scale_name=scale_name)
    for t, fixed_value in enumerate(fixed_notes):
        if fixed_value is not None:
            model.Add(pitch[t] == fixed_value)
    weights = PROFILES[profile]
    all_costs = []
    if weights['smoothness'] > 0:
        all_costs += add_soft_smoothness(model, pitch, weights['smoothness'])
    if weights['range'] > 0:
        all_costs += add_soft_range(model, pitch, weights['range'])
    if weights['direction'] > 0:
        all_costs += add_soft_direction_changes(model, pitch, weights['direction'])
    if weights['no_oscillation'] > 0:
        all_costs += add_soft_no_oscillation(model, pitch, weights['no_oscillation'])
    if weights.get('strong_beat', 0) > 0:
        all_costs += add_soft_strong_beat_consonance(model, pitch, weights['strong_beat'], scale_name=scale_name)
    if weights.get('arch', 0) > 0:
        all_costs += add_soft_arch_contour(model, pitch, weights['arch'])
    for prev in blocklist:
        diff_bools = []
        for t in range(n_notes):
            b = model.NewBoolVar(f'var_diff_{len(blocklist)}_{t}')
            model.Add(pitch[t] != prev[t]).OnlyEnforceIf(b)
            model.Add(pitch[t] == prev[t]).OnlyEnforceIf(b.Not())
            diff_bools.append(b)
        model.AddBoolOr(diff_bools)
    if all_costs:
        model.Minimize(sum(all_costs))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.random_seed = random_seed
    solver.parameters.randomize_search = True
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return [solver.Value(p) for p in pitch]