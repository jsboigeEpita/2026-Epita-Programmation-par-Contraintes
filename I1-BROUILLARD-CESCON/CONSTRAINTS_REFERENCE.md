# Référence exhaustive des contraintes, bonus et pénalités

Document de référence pour le rapport. Chaque contrainte est listée avec :
sa **nature** (hard / soft), sa **formule CP-SAT**, son **poids** (le cas
échéant), et sa **localisation** dans le code.

> Convention : ce qui passe par `model.add(...)` est **hard** (inviolable).
> Ce qui passe par `soft_bonuses` / `soft_penalties` est **soft** (pondéré
> dans l'objectif `maximize(Σ bonus − Σ penalty)`).

---

## 1. Variables de décision

| Nom | Type | Domaine | Sens |
|---|---|---|---|
| `selected[a]` | `BoolVar` | {0, 1} | activité `a` retenue dans le voyage |
| `assign[a, d]` | `BoolVar` | {0, 1} | `a` planifiée le jour `d` |
| `start[a, d]` | `IntVar` | [0, SLOTS_PER_DAY − dur] | créneau de début (1 slot = 30 min depuis 7h) |
| `intervals[a, d]` | `OptionalFixedSizeIntervalVar` | — | enveloppe scheduling, activée par `assign` |

Variables annexes (créées dynamiquement) :
- `both_assigned[a1, a2, d]` (BoolVar) : les deux activités co-assignées le jour `d`
- `order_var[a1, a2, d]` (BoolVar) : a1 avant a2 (ou inverse)
- `is_lunch[a, d]`, `is_dinner[a, d]` (BoolVar) : créneau de repas
- `shortfall[d]`, `overflow[d]` (IntVar) : écart au rythme cible
- `min_shortfall[d]` (IntVar) : écart au minimum d'activités
- `underspend` (IntVar) : sous-dépense du budget activités

---

## 2. Contraintes HARD (inviolables)

### 2.1 Cohérence selection ↔ assignment
*Localisation : `_create_variables` (solver.py)*

| Contrainte | Formule CP-SAT |
|---|---|
| Au plus 1 jour assigné par activité | `model.add_at_most_one([assign[a, d] for d])` |
| selected ⇒ au moins un jour | `model.add_bool_or(day_vars + [selected[a].negated()])` |
| Un jour assigné ⇒ selected | `model.add_implication(assign[a, d], selected[a])` |
| Sans aucun jour possible | `model.add(selected[a] == 0)` |

### 2.2 Budget (type 1)
*Localisation : `_add_budget_constraints` (solver.py)*

| Contrainte | Formule | Note |
|---|---|---|
| Coût activités borné | `Σ selected[a] · cost[a] · num_travelers ≤ activity_budget` | `activity_budget = max(0, total_budget − hotel_total − food_total)` |
| Hôtel | `hotel_total = hotel_per_night × num_days` | par chambre, **pas** × travelers |
| Repas | `food_total = daily_food_budget × num_days × num_travelers` | par personne |
| Cap food/jour | `Σ assign[a, d] · cost[a] · num_travelers ≤ daily_food_budget × num_travelers` ∀ d, ∀ a gastro |

### 2.3 Temporel / scheduling (type 2)
*Localisation : `_add_temporal_constraints`*

| Contrainte | Formule |
|---|---|
| Fenêtre effective | `eff_start = max(opening_slot[a], win_start)` ; `eff_end = min(closing_slot[a], win_end)` |
| Si activité ne tient pas | `model.add(assign[a, d] == 0)` |
| Sinon, début ≥ eff_start | `start[a, d] ≥ eff_start` only_enforce_if `assign[a, d]` |
| Sinon, fin ≤ eff_end | `start[a, d] + duration ≤ eff_end` only_enforce_if `assign[a, d]` |
| Marge de début utilisateur | `−30 min` de tolérance avant `day_start_hour` |
| Fin utilisateur | **stricte** (pas de tolérance) |

### 2.4 Logiques (type 3)
*Localisation : `_add_logical_constraints`*

| Contrainte | Formule |
|---|---|
| `must_visit` | `model.add(selected[a] == 1)` |
| `must_visit_on_day = d` | `model.add(assign[a, d] == 1)` + `selected[a] = 1` + `assign[a, d'] = 0` ∀ d' ≠ d |
| `must_avoid` | `model.add(selected[a] == 0)` |
| Incompatibilités `(a1, a2)` | `model.add(assign[a1, d] + assign[a2, d] ≤ 1)` ∀ d |
| Prérequis (B requiert A) | `model.add(selected[A] ≥ selected[B])` + ordre temporel ∀ jours |
| Fermetures hebdo | `model.add(assign[a, d] == 0)` si day-of-week(d) ∈ `closed_days[a]` |

### 2.5 Capacité / ressources (type 4)
*Localisation : `_add_capacity_constraints`*

| Contrainte | Formule |
|---|---|
| Pas de chevauchement par jour | `model.add_no_overlap(intervals[a, d] ∀ a)` |
| Espacement par trajet (sens a1→a2) | `start[a1, d] + dur1 + travel_slots ≤ start[a2, d]` only_enforce_if `[both_assigned, order_var]` |
| Espacement par trajet (sens a2→a1) | `start[a2, d] + dur2 + travel_slots ≤ start[a1, d]` only_enforce_if `[both_assigned, ¬order_var]` |
| `travel_slots = max(1, travel_min // 30)` |
| `both_assigned = min(assign[a1, d], assign[a2, d])` |

### 2.6 Cardinalité (type 6)
*Localisation : `_add_cardinality_constraints`*

| Contrainte | Formule | Note |
|---|---|---|
| Plafond journalier | `day_count[d] ≤ dynamic_max` | `dynamic_max = min(max_activities_per_day, available_hours // min_duration)` |
| Plancher absolu | `day_count[d] ≥ 1` | jamais de journée vide |
| Plafond par catégorie | `Σ selected[a] (cat) ≤ max_per_category[cat]` |
| Plancher par catégorie | `Σ selected[a] (cat) ≥ min_per_category[cat]` |

### 2.7 Heures de repas (type 7 — fenêtres disjonctives)
*Localisation : `_add_meal_time_constraints`. S'applique aux restaurants
détectés par `_is_restaurant` (gastro + durée 1-3h + filtre par mots-clés).*

| Contrainte | Formule |
|---|---|
| Service unique | `is_lunch + is_dinner == 1` only_enforce_if `assign[a, d]` |
| Déjeuner | `12h ≤ start[a, d] ≤ 14h` only_enforce_if `[assign, is_lunch]` |
| Dîner | `19h30 ≤ start[a, d] ≤ 21h30` only_enforce_if `[assign, is_dinner]` |

Slots équivalents : déjeuner ∈ [10, 14] ; dîner ∈ [25, 29].

### 2.8 Stabilité multi-tours — pinning hard
*Localisation : `_add_pin_constraints`. Actif uniquement si `touched_days`
est défini et qu'un plan précédent existe.*

Pour chaque jour `d` **non touché** par la requête :

| Contrainte | Formule |
|---|---|
| Activité du plan précédent forcée | `model.add(assign[a, d] == 1)` |
| Créneau de début forcé | `model.add(start[a, d] == previous_slot)` |
| Aucune autre activité ce jour | `model.add(assign[a', d] == 0)` ∀ a' non dans le plan |

---

## 3. Bonus SOFT (ajoutés à l'objectif)

### 3.1 Priorité d'activité
*Localisation : `_add_soft_preferences`*

Pour chaque activité `a` :
```
score[a] = priority_score[a]                 # 1 à 10 (LLM)
         + 3 si category ∈ preferred (mode flexible)
         + 5 si category ∈ preferred (mode strict)
         − 5 si category ∈ avoided
```
Bonus = `selected[a] × score[a]`.

Plage typique : **5 à 13 points** par activité sélectionnée.

### 3.2 Bonus matin
Si `morning_preference` (catégorie) est défini, pour chaque activité de
cette catégorie démarrant **avant slot 10 (= 12h)** :

| Bonus | Valeur |
|---|---|
| Activité matinale assignée | **+2** |

### 3.3 Stabilité multi-tours (bonus soft)
*Localisation : `_add_stability_bonus`. Pour chaque (activité, jour) du
plan précédent qui est maintenu.*

| Contexte | Poids |
|---|---|
| `touched_days = None` (modification globale du contexte) | **+20** par (act, day) maintenu |
| `touched_days = {…}` (modification localisée, pinning ailleurs) | **+8** par (act, day) maintenu |

---

## 4. Pénalités SOFT (soustraites à l'objectif)

### 4.1 Sous-dépense du budget activités
*Localisation : `_add_budget_constraints`. Désactivée en pace=relaxed et si
`activity_budget ≤ 100 €`.*

| Pénalité | Formule |
|---|---|
| `target_spend = 70 % × activity_budget` |
| `underspend = max(0, target_spend − activity_cost)` |
| `penalty_var = underspend // 20` |
| Ajouté aux `soft_penalties` | **1 point par 20 € sous le seuil** |

### 4.2 Rythme — shortfall (sous-rythme)
*Localisation : `_add_soft_preferences`*

Pour chaque jour `d` :
- `shortfall[d] = max(0, target − day_count[d])`

| Pace | Target/jour | Poids `shortfall × W` |
|---|---|---|
| `relaxed` | 3 | **× 15** |
| `moderate` | 4 | **× 20** |
| `intense` | 5 | **× 25** |

Exemple : une journée vide en `intense` → 5 × 25 = **125 points de pénalité**.

### 4.3 Rythme — overflow (sur-rythme)
| Pace | Poids `overflow × W` |
|---|---|
| `relaxed` | **× 10** |
| `moderate` | × 4 |
| `intense` | × 1 |

C'est l'asymétrie qui distingue réellement les paces : `relaxed` est lourdement
puni s'il dépasse 3/jour ; `intense` quasi-pas s'il dépasse 5.

### 4.4 Plancher d'activités/jour (soft target)
*Localisation : `_add_cardinality_constraints`. Si `min_activities_per_day > 1` :*

| Pénalité | Formule | Poids |
|---|---|---|
| `min_shortfall[d] = max(0, min_activities_per_day − day_count[d])` | | |
| ajouté aux `soft_penalties` | `min_shortfall × 20` | **× 20** par jour |

Note : le hard floor reste à 1 (pas de jour vide). Au-delà, c'est une cible soft.

### 4.5 Pénalité de trajet (regroupement géographique)
*Localisation : `_add_travel_penalty`. Pour chaque paire `(a1, a2)`
co-assignées le jour `d` :*

```
weight = max(0, (travel_min − 15) // 10)
penalty += both_assigned[a1, a2, d] × weight
```

| `travel_min` | Pénalité |
|---|---|
| ≤ 15 min | **0** (intra-quartier, gratuit) |
| 25 min | 1 |
| 35 min | 2 |
| 60 min | 4 |
| 100 min | 8 |

---

## 5. Calibration globale — ordres de grandeur

| Famille | Plage typique |
|---|---|
| Bonus de priorité activité | **5 à 13** par activité |
| Bonus matin | +2 |
| Bonus stabilité (pas de pin) | +20 par (act, day) maintenu |
| Bonus stabilité (pin partiel) | +8 |
| Pénalité shortfall pace | 15-125 par journée (selon pace × écart) |
| Pénalité overflow pace | 1-10 par activité de trop |
| Pénalité min_activities_per_day | 0-60 par jour |
| Pénalité trajet | 0-8 par paire co-assignée |
| Pénalité sous-dépense budget | 0-50 typique (cap à `activity_budget // 20`) |

**Objectif final** :
```
maximize(Σ bonus − Σ penalty)
```

---

## 6. Paramètres par défaut hors solveur

| Paramètre | Valeur | Source | Effet |
|---|---|---|---|
| `num_travelers` | 1 | `DEFAULT_CONSTRAINTS` | × food, × cost activités |
| `daily_food_budget` | 60 € | `DEFAULT_CONSTRAINTS` | borne hard food/jour |
| `hotel_per_night` | `None` puis calculé | `_resolve_hotel_budget` | **40 % × total_budget / num_days** ; plancher 50 € |
| `day_start_hour` | 9 | `DEFAULT_CONSTRAINTS` | fenêtre journalière, marge −30 min |
| `day_end_hour` | 19 | `DEFAULT_CONSTRAINTS` | fenêtre journalière, **stricte** |
| `preferred_pace` | `"moderate"` | `DEFAULT_CONSTRAINTS` | target 4/jour |
| `max_activities_per_day` | 6 | `DEFAULT_CONSTRAINTS` | borne hard `dynamic_max` |
| `min_activities_per_day` | 2 | `DEFAULT_CONSTRAINTS` | soft target × 20 |
| `morning_preference` | `"culture"` | `TravelConstraints` | bonus +2 si avant 12h |

### Sélection d'hôtel (post-solve)
| Règle | Choix |
|---|---|
| Hôtel le plus cher ≤ `hotel_per_night` | choisi |
| Aucun ≤ cap | le moins cher disponible |

### Pré-vérification budget
```
hotel_cost = real_hotel_price × num_days       # prix de l'hôtel pré-sélectionné
food_cost  = daily_food_budget × num_days × num_travelers
si hotel_cost + food_cost > total_budget       → INFEASIBLE_BUDGET
```

---

## 7. Annexe — exemple chiffré (pour la diapo)

Configuration : **5 jours · 2 personnes · 5000 € · pace = moderate · culture préférée**

```
Budget alloué :
  hotel_per_night auto = 5000 × 0.4 / 5 = 400 €/nuit
  Hôtel choisi par solveur  = 280 €/nuit (premium ≤ 400)
  hotel_total                = 280 × 5  = 1400 €
  food_total                 = 60 × 5 × 2 = 600 €
  activity_budget            = 5000 − 1400 − 600 = 3000 €

Objectif (résultat typique avec 18 activités sélectionnées) :
  + 18 × ~10 (priority + bonus culture)        = +180
  + 4 × 2 (bonus matin sur 4 activités culture) = +8
  − 5 × 0 (pace moderate, target atteint)       = 0
  − ~12 (trajets moyens 25 min × 6 paires)      = −12
  = +176

Sortie :
  - 18 activités planifiées
  - hôtel premium dans le budget
  - 70 % du budget activités consommé
  - 100 % satisfaction des préférences "culture"
```
