# C3 — Drone Delivery Routing (CP-SAT)

VRP pour drones avec contraintes d'autonomie, capacité et zones de vol interdites, résolu avec Google OR-Tools CP-SAT.

## Lancer

```bash
cd C3-drone-delivery
pip install -r requirements.txt
cd backend
uvicorn main:app --reload
```

Ouvrir `http://localhost:8000`

## Utilisation

1. **Placer le dépôt** (mode Dépôt, clic sur la carte)
2. **Ajouter des clients** (mode Client, régler poids/volume/priorité)
3. **Dessiner des zones interdites** (mode Zone, double-clic pour finir)
4. **Configurer les drones** (nb, autonomie, capacité)
5. **Résoudre** → les routes s'affichent par couleur sur la carte

Ou utiliser **Générer instance** pour un exemple aléatoire.

## API

- `POST /solve` — résoudre un problème
- `GET /generate` — générer une instance aléatoire
