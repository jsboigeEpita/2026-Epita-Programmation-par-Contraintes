# CP Explainer — Explicateur de solutions CP par LLM

Projet I2 — Pipeline qui analyse une solution CP-SAT, extrait les informations
structurelles (contraintes actives, marges, analyse de sensibilité) et génère
des explications en langage naturel via un LLM (Claude).

## Ce que fait le projet

- **Résout** 5 types de problèmes d'optimisation avec CP-SAT (ortools) :
  knapsack, diet, job shop, assignment, bin packing.
- **Analyse** la solution : identifie les contraintes actives (binding, slack=0),
  calcule les marges, réalise une analyse de sensibilité (re-résolution avec
  contraintes assouplies) et des contrefactuels (décisions alternatives forcées).
- **Explique** via un LLM (Claude / Mistral) en 3 types d'explication :
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
cp_explainer/
├── schemas.py      — Pydantic : SolverOutput, ExplanationOutput, ExplainerResult
├── solver.py       — Solveurs CP-SAT (5 types) + analyse de sensibilité + contrefactuels
├── llm_client.py   — Clients LLM (Anthropic Claude + Mistral fallback)
├── cache.py        — Cache disque SHA256 des appels LLM
├── prompts.py      — Templates de prompts pour les 3 types d'explication
├── explainer.py    — Appels LLM + explications template (sans LLM)
└── runner.py       — Orchestrateur du pipeline complet

problems/           — 5 instances JSON (knapsack, diet, job_shop, assignment, bin_packing)
scripts/
├── run_explainer.py  — CLI : expliquer un problème
├── run_benchmark.py  — Benchmark complet + rapport JSON
└── app.py            — Dashboard Streamlit
tests/
└── test_solvers.py   — Tests unitaires des solveurs CP-SAT
```

### Pipeline en 4 étapes

| # | Étape             | Outil      | Sortie                                       |
|---|-------------------|------------|----------------------------------------------|
| 1 | Résolution        | CP-SAT     | `SolverOutput` (variables, contraintes, slack) |
| 2 | Sensibilité       | CP-SAT     | Re-résolutions avec contraintes assouplies   |
| 3 | Explications LLM  | Claude     | 3 × `ExplanationOutput` (reasoning + texte)  |
| 4 | Explications tmpl | Template   | 3 textes template (sans LLM, pour comparaison) |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # remplir ANTHROPIC_API_KEY
```

Créer une clé Anthropic : https://console.anthropic.com

## Usage

### Expliquer un problème

```bash
python scripts/run_explainer.py problems/knapsack.json
python scripts/run_explainer.py problems/diet.json --save out/diet_result.json
python scripts/run_explainer.py problems/job_shop.json --no-cache
python scripts/run_explainer.py problems/assignment.json --provider mistral
```

Le script affiche :
- La solution CP-SAT (statut, objectif, variables)
- Les 3 explications LLM (texte + points clés)
- Les contraintes actives identifiées

### Benchmark complet

```bash
python scripts/run_benchmark.py
```

Produit `benchmark_report.json` avec, pour chaque problème :
- Statut de résolution, objectif, contraintes actives
- Métriques d'explication : couverture des contraintes actives, confiance LLM
- Temps d'exécution total

### Dashboard Streamlit

```bash
streamlit run scripts/app.py
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
