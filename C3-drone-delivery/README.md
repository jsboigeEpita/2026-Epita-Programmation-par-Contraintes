# C3 — Drone Delivery Routing (CP-SAT)

**Groupe :** brieuc.crosson, nathan.champagne, adrien.capitaine

Optimisation de tournées de drones de livraison (VRP) avec contraintes d'autonomie, de capacité et de zones de vol interdites (NOTAM), résolu avec Google OR-Tools CP-SAT.

## Problème

Il s'agit d'une variante du **Vehicle Routing Problem (VRP)** appliquée à des flottes de drones :

- Depuis un dépôt central, plusieurs drones doivent livrer des colis à un ensemble de clients
- Chaque client doit être visité exactement une fois
- Chaque drone est soumis à des contraintes de **batterie** (autonomie), de **poids** et de **volume**
- Des **zones NOTAM** (zones de vol interdit) doivent être contournées
- L'objectif est de **minimiser la distance totale** parcourue par l'ensemble des drones

## Modélisation CP-SAT

Le solveur utilise **Google OR-Tools CP-SAT** avec les contraintes suivantes :

| Contrainte | Description |
|---|---|
| Couverture | Chaque client est visité exactement une fois |
| Conservation de flux | Pour chaque drone et chaque nœud, le nombre d'arcs entrants égale le nombre d'arcs sortants (style MTZ) |
| Autonomie | La batterie consommée sur chaque arc est déduite du solde courant ; le retour au dépôt doit rester faisable |
| Capacité poids | La somme des poids livrés ne dépasse pas `max_load` du drone |
| Capacité volume | La somme des volumes livrés ne dépasse pas `max_volume` du drone |

**Objectif :** minimiser la distance totale parcourue (tous les clients sont toujours servis)

### Contournement des zones NOTAM (WaypointNavigator)

Pour calculer les distances réelles entre nœuds, on ne peut pas utiliser la distance euclidienne directe si une zone NOTAM est sur le chemin. L'algorithme procède en deux temps :

1. **Chemin direct** : si le segment entre deux points n'intersecte aucun polygone NOTAM (via Shapely), on prend la distance euclidienne.
2. **Dijkstra sur grille de waypoints** : sinon, une grille de points sûrs est générée autour de la scène (hors des zones), et Dijkstra trouve le chemin le plus court en évitant les obstacles.

La matrice de distances résultante est passée au solveur CP-SAT. Les chemins complets sont conservés pour l'affichage animé sur la carte.

## Lancer

### Sans Docker

```bash
cd C3-drone-delivery
pip install -r requirements.txt
cd backend
uvicorn main:app --reload
```

Ouvrir `http://localhost:8000`

### Avec Docker

```bash
cd C3-drone-delivery
docker compose up --build
```

## Utilisation de l'interface

1. **Mode Dépôt** — clic sur la carte pour placer le dépôt
2. **Mode Client** — clic pour ajouter un client, régler poids / volume dans la sidebar
3. **Mode Zone** — cliquer les sommets du polygone NOTAM, double-clic pour fermer
4. **Configurer les drones** — nombre, autonomie (km), capacité poids/volume
5. **Résoudre** — le solveur tourne (30s max par défaut), les routes s'affichent par couleur sur la carte avec animation

## API

| Endpoint | Description |
|---|---|
| `POST /solve` | Résoudre un problème (corps : `MissionRequest`) |

## Stack technique

- **Backend** : Python 3.11+, FastAPI, Google OR-Tools CP-SAT, Shapely
- **Frontend** : HTML/JS, Leaflet (carte interactive), Leaflet-Draw (zones NOTAM)
- **Deploy** : Docker Compose
