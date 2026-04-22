import numpy as np
import heapq
from ortools.sat.python import cp_model
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from shapely.geometry import Point, LineString, Polygon

@dataclass
class DroneInstance:
    depot: Tuple[float, float, float]
    clients: List[Tuple[float, float, float]]
    demands: List[int]
    notam_zones: List[List[Tuple[float, float]]]
    num_drones: int
    battery_capacity: int
    max_load: int
    wind_coeff: float = 1.0
    unloading_time: int = 5
    grid_res: int = 30

class WaypointNavigator:
    """Gère le contournement intelligent : Direct si possible, sinon Waypoints."""
    def __init__(self, instance: DroneInstance):
        self.inst = instance
        self.zones = [Polygon(z) for z in instance.notam_zones]
        self.interest_points = [instance.depot] + instance.clients
        self.waypoints = self._generate_safe_waypoints()
        self.all_nodes = self.interest_points + self.waypoints
        # On construit le graphe d'adjacence pour la grille
        self.adj = self._build_adjacency_list()

    def _generate_safe_waypoints(self) -> List[Tuple]:
        pts = np.array(self.interest_points)
        x_min, y_min = np.min(pts[:,0]) - 20, np.min(pts[:,1]) - 20
        x_max, y_max = np.max(pts[:,0]) + 20, np.max(pts[:,1]) + 20
        safe_pts = []
        for x in np.linspace(x_min, x_max, self.inst.grid_res):
            for y in np.linspace(y_min, y_max, self.inst.grid_res):
                p = Point(x, y)
                if not any(p.within(zone) for zone in self.zones):
                    safe_pts.append((float(x), float(y), 10.0))
        return safe_pts

    def is_safe(self, p1: Tuple, p2: Tuple) -> bool:
        """Vérifie si la ligne directe (x,y) est libre de NOTAM."""
        line = LineString([(p1[0], p1[1]), (p2[0], p2[1])])
        return not any(line.intersects(zone) for zone in self.zones)

    def _build_adjacency_list(self) -> Dict:
        adj = {i: [] for i in range(len(self.all_nodes))}
        for i in range(len(self.all_nodes)):
            for j in range(i + 1, len(self.all_nodes)):
                p1, p2 = self.all_nodes[i], self.all_nodes[j]
                dist = np.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))
                # Connexions locales pour Dijkstra
                if dist < 35 and self.is_safe(p1, p2):
                    adj[i].append((j, dist))
                    adj[j].append((i, dist))
        return adj

    def get_shortest_path_data(self, start_idx: int, end_idx: int) -> Tuple[float, List[Tuple]]:
        """Logique : Direct d'abord, Dijkstra sinon."""
        p_start = self.all_nodes[start_idx]
        p_end = self.all_nodes[end_idx]

        # 1. TENTATIVE DIRECTE (Règle d'or)
        if self.is_safe(p_start, p_end):
            dist = np.sqrt(sum((a - b) ** 2 for a, b in zip(p_start, p_end)))
            return dist, [p_start, p_end]

        # 2. REPLI SUR DIJKSTRA VIA WAYPOINTS
        queue = [(0.0, start_idx, [p_start])]
        visited = {start_idx: 0.0}
        while queue:
            (d, curr, path) = heapq.heappop(queue)
            if curr == end_idx: return d, path
            
            for (nxt, weight) in self.adj[curr]:
                new_dist = d + weight
                if nxt not in visited or new_dist < visited[nxt]:
                    visited[nxt] = new_dist
                    heapq.heappush(queue, (new_dist, nxt, path + [self.all_nodes[nxt]]))
                    
        return 999999.0, []

class DroneRoutingSolver:
    def __init__(self, instance: DroneInstance):
        self.inst = instance
        self.navigator = WaypointNavigator(instance)
        self.num_interest = len(instance.clients) + 1
        self.full_paths = {}
        self.dist_matrix = self._compute_matrix()
        
    def _compute_matrix(self) -> np.ndarray:
        n = self.num_interest
        matrix = np.zeros((n, n), dtype=int)
        for i in range(n):
            for j in range(i + 1, n):
                dist, path = self.navigator.get_shortest_path_data(i, j)
                matrix[i][j] = matrix[j][i] = int(dist * self.inst.wind_coeff * 100)
                self.full_paths[(i, j)] = path
                self.full_paths[(j, i)] = path[::-1]
        return matrix

    def solve(self, time_limit=30.0):
        model = cp_model.CpModel()
        n_n, n_k = self.num_interest, self.inst.num_drones
        arcs = {(i, j, k): model.NewBoolVar(f'a_{i}_{j}_{k}') for i in range(n_n) for j in range(n_n) for k in range(n_k) if i != j}
        battery = {(i, k): model.NewIntVar(0, self.inst.battery_capacity * 100, f'b_{i}_{k}') for i in range(1, n_n) for k in range(n_k)}
        load = {(i, k): model.NewIntVar(0, self.inst.max_load, f'l_{i}_{k}') for i in range(1, n_n) for k in range(n_k)}
        
        for i in range(1, n_n):
            model.Add(sum(arcs[i, j, k] for j in range(n_n) for k in range(n_k) if i != j) == 1)
        for k in range(n_k):
            for j in range(n_n):
                model.Add(sum(arcs[i, j, k] for i in range(n_n) if i != j) == sum(arcs[j, l, k] for l in range(n_n) if j != l))
            model.Add(sum(arcs[0, j, k] for j in range(1, n_n)) <= 1)
            for i in range(n_n):
                for j in range(n_n):
                    if i == j: continue
                    if i == 0 and j > 0:
                        model.Add(battery[j, k] == self.inst.battery_capacity * 100 - self.dist_matrix[0, j]).OnlyEnforceIf(arcs[0, j, k])
                        model.Add(load[j, k] == self.inst.demands[j-1]).OnlyEnforceIf(arcs[0, j, k])
                    elif i > 0 and j > 0:
                        model.Add(battery[j, k] == battery[i, k] - self.dist_matrix[i, j]).OnlyEnforceIf(arcs[i, j, k])
                        model.Add(load[j, k] == load[i, k] + self.inst.demands[j-1]).OnlyEnforceIf(arcs[i, j, k])
                    elif i > 0 and j == 0:
                        model.Add(battery[i, k] >= self.dist_matrix[i, 0]).OnlyEnforceIf(arcs[i, 0, k])

        model.Minimize(sum(arcs[i, j, k] * self.dist_matrix[i, j] for i, j, k in arcs))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        status = solver.Solve(model)
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            routes = []
            for k in range(n_k):
                drone_path, curr = [], 0
                while True:
                    nxt = -1
                    for j in range(n_n):
                        if curr != j and solver.Value(arcs[curr, j, k]): nxt = j; break
                    if nxt == -1: break
                    seg = self.full_paths[(curr, nxt)]
                    if not drone_path: drone_path.extend(seg)
                    else: drone_path.extend(seg[1:])
                    curr = nxt
                    if curr == 0: break
                if drone_path: routes.append({'drone_id': k, 'geometry': drone_path})
            return routes
        return None

if __name__ == "__main__":
    print("--- DÉMARRAGE DU TEST (TRAJET DIRECT VS CONTOURNEMENT) ---")
    # Mur avec passage central
    wall1 = [(45, 0), (45, 40), (55, 40), (55, 0)]
    wall2 = [(45, 60), (45, 100), (55, 100), (55, 60)]
    
    data = DroneInstance(
        depot=(20, 50, 0), 
        clients=[
            (10, 50, 10),  # Ouest (Accessible en direct)
            (90, 50, 10),  # Est (Bloqué, doit contourner par le milieu y=50)
            (20, 20, 10),  # Ouest (Accessible en direct)
            (80, 80, 10)   # Est (Bloqué, doit contourner)
        ],
        demands=[5, 5, 5, 5],
        notam_zones=[wall1, wall2],
        num_drones=2,
        battery_capacity=3000,
        max_load=15
    )
    
    res = DroneRoutingSolver(data).solve()
    if res:
        for r in res:
            print(f"\nDrone {r['drone_id']} :")
            for i, p in enumerate(r['geometry']):
                print(f"  Étape {i}: ({p[0]:.1f}, {p[1]:.1f})")
