# Diet Planner

Un solveur de menus hebdomadaires basé sur la programmation par contraintes (CP-SAT, OR-Tools).
On lui donne un budget, un nombre de jours et de repas, il sort une planification optimisée
qui respecte les apports nutritionnels recommandés (kcal, protéines, lipides, glucides,
fibres, sel, calcium, fer).

## Le problème

C'est une variante du Diet Problem : trouver les quantités d'aliments qui couvrent les
besoins nutritionnels au moindre coût. On l'a étendu à la planification hebdomadaire
avec des contraintes en plus :

* au moins un féculent, un légume et un dessert par repas
* maximum un produit carné (viande ou poisson) par repas
* pas plus de 5 aliments par repas
* variété sur la semaine (pas le même aliment deux jours de suite)
* option végétarien
* aliments exclus à la demande
* budget global

La table nutritionnelle vient de Ciqual 2025 (Anses), 1975 aliments après filtrage.

## Stack

* Python + OR-Tools (CP-SAT) pour le solveur
* Pandas pour le preprocessing de la table Ciqual
* FastAPI pour l'API
* HTML + Tailwind (via CDN) + JS vanilla pour le front

## Lancer le projet

Il faut le fichier `Table Ciqual 2025_FR_2025_11_03.xlsx` à la racine du projet.
Disponible librement sur [data.gouv.fr](https://entrepot.recherche.data.gouv.fr/dataset.xhtml?persistentId=doi:10.57745/RDMHWY).

```bash
python3 -m venv .venv
.venv/bin/pip install fastapi 'uvicorn[standard]' ortools pandas openpyxl
.venv/bin/uvicorn api:app --reload
```

Puis [http://127.0.0.1:8000](http://127.0.0.1:8000).

Au premier lancement, l'API parse l'Excel et génère un cache `ciqual_clean.csv`
pour accélérer les démarrages suivants.

## Structure

```
api.py              # backend FastAPI
diet.py             # solveur CP-SAT et générateur hebdo
preprocessing.py    # nettoyage et enrichissement de la table Ciqual
train.ipynb         # notebook d'exploration et de modélisation
static/
  index.html        # interface
  app.js            # logique front
```

## Endpoints

| Méthode | URL              | Description                                |
|---------|------------------|--------------------------------------------|
| GET     | `/`              | Interface web                              |
| GET     | `/api/foods`     | Liste des aliments dispo                   |
| GET     | `/api/nutrients` | Cibles nutritionnelles                     |
| POST    | `/api/menu`      | Génère un menu                             |

Body de `POST /api/menu` :

```json
{
  "days": 7,
  "meals_per_day": 2,
  "budget_eur": 30,
  "vegetarian": false,
  "excluded_foods": [],
  "seed": 42
}
```

## Limites connues

Les prix des aliments sont des estimations à partir de mots-clés et de groupes,
pas des vrais prix de marché. Pour un usage sérieux il faudrait brancher une
vraie source de prix (Open Food Facts, scrapping supermarché, etc.).

Si le budget est trop serré le solveur peut renvoyer `infeasible` sur certains
repas. Dans ce cas on relâche la contrainte budget pour ce repas (fallback)
avant de baisser les bras.

## Auteurs

Projet réalisé dans le cadre du cours Programmation par Contraintes (Epita, 2026).

* Kim Tayant-Serrat
* Damien Duthou
