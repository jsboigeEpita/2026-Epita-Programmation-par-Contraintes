# CP Explainer — Explicateur de solutions CP par LLM

Projet I2 — Pipeline qui analyse une solution CP-SAT, extrait les informations
structurelles (contraintes actives, marges, analyse de sensibilité) et génère
des explications en langage naturel via un LLM (Mistral / Claude).

## Ce que fait le projet

- **Résout** 10 types de problèmes d'optimisation avec CP-SAT (ortools) :
  knapsack, diet, job shop, assignment, bin packing, nurse scheduling,
  graph coloring, n-queens, production planning, TSP.
- **Analyse** la solution : identifie les contraintes actives (binding, slack=0),
  calcule les marges, réalise une analyse de sensibilité (re-résolution avec
  contraintes assouplies) et des contrefactuels (décisions alternatives forcées).
- **Explique** via un LLM (Mistral / Claude) en 3 types d'explication :
  1. **Pourquoi cette solution est-elle optimale ?** — justifie l'optimalité.
  2. **Pourquoi ne peut-on pas faire mieux ?** — analyse les blocages et contrefactuels.
  3. **Comment améliorer la solution ?** — recommandations actionnables par assouplissement.
- **Compare** les explications LLM avec des explications template (sans LLM)
  pour évaluer l'apport du LLM en clarté et précision.
- **Met en cache** sur disque les appels LLM (SHA256 du prompt) pour rejouer les
  démonstrations sans ré-consommer des tokens.
- **Dashboard Streamlit** en 3 onglets : exploration interactive, benchmark, prompts.

## Architecture

```
src/
├── cp_explainer/
│   ├── core/           — schemas.py (Pydantic), solver.py (10 solveurs CP-SAT)
│   ├── llm/            — llm_client.py (Mistral + Claude), cache.py, prompts.py
│   └── pipeline/       — explainer.py (appels LLM + templates), runner.py (orchestrateur)
├── app/
│   └── app.py          — Dashboard Streamlit
├── cli/
│   ├── run_explainer.py  — CLI : expliquer un problème
│   └── run_benchmark.py  — Benchmark complet + rapport JSON
└── data/               — 10 instances JSON de problèmes

tests/
└── test_solvers.py     — 14 tests unitaires des solveurs CP-SAT

benchmark/              — benchmark_report.json (généré par run_benchmark.py)
slides/                 — support de présentation
resources/              — notebooks CSP de référence
```

### Pipeline en 4 étapes

| # | Étape             | Outil      | Sortie                                         |
|---|-------------------|------------|------------------------------------------------|
| 1 | Résolution        | CP-SAT     | `SolverOutput` (variables, contraintes, slack) |
| 2 | Sensibilité       | CP-SAT     | Re-résolutions avec contraintes assouplies     |
| 3 | Explications LLM  | Mistral    | 3 × `ExplanationOutput` (reasoning + texte)    |
| 4 | Explications tmpl | Template   | 3 textes template (sans LLM, pour comparaison) |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # remplir MISTRAL_API_KEY
```

La clé Mistral (provider par défaut) est disponible sur https://console.mistral.ai.
Claude peut être utilisé en ajoutant `ANTHROPIC_API_KEY` dans `.env`.

## Usage

### Expliquer un problème

```bash
python src/cli/run_explainer.py src/data/knapsack.json
python src/cli/run_explainer.py src/data/diet.json --save out/diet_result.json
python src/cli/run_explainer.py src/data/job_shop.json --no-cache
python src/cli/run_explainer.py src/data/assignment.json --provider mistral
```

Le script affiche :
- La solution CP-SAT (statut, objectif, variables)
- Les 3 explications LLM (texte + points clés)
- Les contraintes actives identifiées

### Benchmark complet

```bash
python src/cli/run_benchmark.py
```

Produit `benchmark/benchmark_report.json` avec, pour chaque problème :
- Statut de résolution, objectif, contraintes actives
- Métriques d'explication : couverture des contraintes actives, confiance LLM
- Temps d'exécution total

### Dashboard Streamlit

```bash
streamlit run src/app/app.py
```

Trois onglets :
- **Explorer une solution** : lance le pipeline complet sur un problème choisi,
  compare les explications LLM et template côte à côte, affiche les contrefactuels.
- **Benchmark** : explore `benchmark_report.json` avec métriques de qualité.
- **Prompts** : inspecte les prompts envoyés au LLM pour chaque type d'explication.

### Tests

```bash
python -m pytest tests/
```

## Méthodologie

### Extraction des informations structurelles

Pour chaque solution CP-SAT, le pipeline calcule :

- **Slack** (marge) de chaque contrainte : `slack = rhs - lhs`. `slack == 0` → contrainte **active (binding)**.
- **Analyse de sensibilité** : re-résolution avec chaque contrainte active assouplie de ε → mesure l'amélioration marginale de l'objectif.
- **Contrefactuels** : re-résolution avec une décision forcée (ex: "inclure l'objet 3") → mesure le coût de cette contrainte supplémentaire.

### Types d'explication

| Type             | Question posée                                  | Sources de données                          |
|------------------|-------------------------------------------------|---------------------------------------------|
| `why_optimal`    | Pourquoi cette solution est-elle optimale ?     | Contraintes actives, marges                 |
| `why_not`        | Pourquoi ne peut-on pas faire mieux ?           | Contrefactuels, contraintes actives         |
| `how_to_improve` | Quels assouplissements améliorent l'objectif ?  | Analyse de sensibilité, classement par gain |

### Évaluation des explications

Métriques automatiques (voir `run_benchmark.py`) :
- **Couverture** : fraction des contraintes actives citées dans l'explication.
- **Points clés** : nombre de faits identifiés dans `key_points`.
- **Confiance LLM** : `high / medium / low` auto-évaluée par le LLM.

Comparaison qualitative : explications LLM vs template affichées côte à côte
dans le dashboard Streamlit pour évaluation humaine.

## Taxonomie des explications

| Code | Situation                                                   |
|------|-------------------------------------------------------------|
| E1   | Contrainte active correctement identifiée et citée          |
| E2   | Contrefactuel quantifié (ex: "+5% de coût si on force X")  |
| E3   | Recommandation actionnée avec impact chiffré                |
| E4   | Contrainte implicite expliquée (ex: borne entière CP-SAT)   |
| E5   | Explication vague ou incorrecte (à améliorer)               |
