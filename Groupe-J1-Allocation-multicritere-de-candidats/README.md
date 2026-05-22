# Allocation Multicritère de Candidats

Une application web sophistiquée pour l'allocation optimale de candidats à des postes, basée sur un système de scoring multicritère et une optimisation sous contraintes.

## Objectif

Ce projet résout le problème d'**allocation optimale de candidats à des postes de travail** en considérant :
- **14 critères d'évaluation** : localisation, expérience, compétences, motivations, culture, etc.
- **Contraintes multiples** : géographiques, contractuelles, linguistiques, diversité et équité
- **Optimisation globale** : maximisation du score total tout en respectant les capacités des postes

## Architecture

### Technologies principales

- **Python 3.14+**
- **FastAPI** : framework web moderne pour l'API REST
- **OR-Tools** : moteur d'optimisation de Google pour les problèmes de satisfaction de contraintes
- **Pydantic** : validation des données et modèles
- **JavaScript / HTML / CSS** : interface frontend

### Structure du projet

```
app/
├── main.py                  # Serveur FastAPI, endpoints de l'API
├── models.py               # Modèles de données (Pydantic)
├── scoring.py              # Moteur de scoring multicritère (1188 lignes)
├── assignment.py           # Solveur d'allocation avec OR-Tools
├── embedding_client.py      # Client pour embeddings textuels (fallback lexical)
├── storage.py              # Persistence JSON des données
├── data/
│   ├── candidates.json     # Profils des candidats
│   └── jobs.json           # Descriptions des postes
└── static/
    ├── index.html          # Interface web
    ├── app.js              # Logique frontend
    └── styles.css          # Styles CSS
```

## Installation et démarrage

### Prérequis

- Python 3.14+
- pip ou uv (gestionnaire de paquets moderne)

### Installation

```bash
# Installer les dépendances
pip install -r requirements.txt
# ou avec uv:
uv sync
```

### Démarrage du serveur

```bash
# Via Python direct
python app/main.py

# Via uvicorn
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

L'application est alors accessible à : **http://localhost:8000**

## Système de Scoring

### 14 Critères d'évaluation

| Critère | Poids | Description |
|---------|-------|-------------|
| **Compétences obligatoires** | 20% | Couverture des skills requis (65% exact match + 35% sémantique) |
| **Expérience** | 12% | Années d'expérience vs minimum demandé |
| **Alignement du poste** | 12% | Correspondance rôle actuel / rôle visé avec missions |
| **Localisation** | 10% | Compatibilité géographique et mobilité |
| **Compétences souhaitées** | 10% | Couverture des skills bonus (60% niveaux + 40% sémantique) |
| **Motivation** | 10% | Alignement motivations personnelles / opportunités |
| **Éducation** | 8% | Niveau de diplôme requis |
| **Contrat** | 8% | Type de contrat préféré vs offert |
| **Salaire** | 8% | Fourchette salariale compatible |
| **Diversité & Équité** | 7% | Objectifs de diversité et inclusion |
| **Langues** | 6% | Couverture des langues requises |
| **Culture et valeurs** | 5% | Alignement valeurs personnelles / culture entreprise |
| **Disponibilité** | 5% | Dates de début compatibles |
| **Potentiel d'apprentissage** | 5% | Alignement objectifs de progression |

### Calcul du score

1. **Score de base** : somme pondérée des critères (0-100)
2. **Pénalités applicables** :
   - Localisation bloquante : ×0.65
   - Disponibilité trop éloignée : ×0.85
   - Couverture linguistique insuffisante : ×0.9
   - Compétences obligatoires insuffisantes : ×0.8
   - Type de contrat peu compatible : ×0.9

3. **Score final** = Score de base × produit des pénalités

### Approches d'évaluation

**Structured** : Basée sur des règles et données structurées (localisation, expérience, contrat, etc.)

**Hybrid/Embedding** : Utilise les embeddings textuels (modèle par défaut) avec fallback lexical en cas d'indisponibilité

**Lexical Fallback** : Similarité basée sur tokens partagés quand embedding n'est pas disponible

## Modèles de données

### Profil Candidat

```json
{
  "full_name": "string",
  "email": "string",
  "current_title": "string",
  "years_experience": 0-60,
  "location": {
    "city": "string",
    "country": "string",
    "remote_preference": "on_site | hybrid | remote",
    "mobility_km": 0-10000
  },
  "skills": [
    {
      "name": "string",
      "level": 1-5,
      "category": "technical | functional | language | tool | other"
    }
  ],
  "education": {
    "degree": "string",
    "field_of_study": "string",
    "certifications": ["string"]
  },
  "preferences": {
    "target_roles": ["string"],
    "target_sectors": ["string"],
    "contract_types": ["cdi | cdd | internship | freelance | apprenticeship"],
    "salary_min": 0-∞,
    "values": ["string"]
  },
  "motivation": {
    "free_text": "string (10-4000 caractères)",
    "drivers": ["string"],
    "mission_preferences": ["string"]
  },
  "potential": {
    "learning_goals": ["string"],
    "transferable_experiences": "string",
    "growth_domains": ["string"]
  },
  "availability": {
    "start_date": "YYYY-MM-DD",
    "schedule": "full_time | part_time | either",
    "constraints": "string"
  },
  "diversity": {
    "gender": "female | male | non_binary | other | undisclosed",
    "self_declared_tags": ["first_generation | reconversion | rqth | international | caregiver | rural_background"],
    "equity_notes": "string"
  }
}
```

### Profil Poste

```json
{
  "title": "string",
  "team": "string",
  "location": {
    "city": "string",
    "country": "string",
    "work_mode": "on_site | hybrid | remote"
  },
  "requirements": {
    "minimum_degree": "string",
    "minimum_years_experience": 0-60,
    "mandatory_skills": ["string"],
    "languages": ["string"]
  },
  "desired_skills": [
    {
      "name": "string",
      "level": 1-5,
      "category": "technical | functional | language | tool | other"
    }
  ],
  "missions": "string (10-5000 caractères)",
  "environment": {
    "team_style": "string",
    "pace": "string",
    "culture_keywords": ["string"]
  },
  "conditions": {
    "salary_min": 0-∞,
    "salary_max": 0-∞,
    "contract_type": "cdi | cdd | internship | freelance | apprenticeship | other",
    "start_date": "YYYY-MM-DD",
    "capacity": 1-1000
  },
  "target_profile": {
    "expected_traits": ["string"],
    "growth_potential": "string",
    "learning_expectations": ["string"],
    "diversity_constraints": [
      {
        "dimension": "gender | tag",
        "value": "string",
        "minimum_count": 0-1000,
        "maximum_count": 0-1000,
        "target_count": 0-1000,
        "priority": "required | preferred",
        "rationale": "string"
      }
    ]
  }
}
```

## API REST

### Endpoints principaux

#### Gestion des candidats

```http
GET /api/candidates                    # Lister tous les candidats
POST /api/candidates                   # Créer un candidat
```

#### Gestion des postes

```http
GET /api/jobs                          # Lister tous les postes
POST /api/jobs                         # Créer un poste
```

#### Compatibilité

```http
POST /api/compatibility
Content-Type: application/json

{
  "candidate_ids": ["string"],         # IDs à évaluer (vide = tous)
  "job_ids": ["string"],               # IDs à évaluer (vide = tous)
  "top_k_per_candidate": 5,            # Top K postes par candidat
  "criterion_weights": {               # Poids personnalisés (optionnel)
    "location": 0.1,
    ...
  }
}
```

**Réponse** : Liste des scores de compatibilité avec détails critère par critère

#### Allocation optimale

```http
POST /api/assignment
Content-Type: application/json

{
  "candidate_ids": [],                 # IDs à affecter (vide = tous)
  "job_ids": [],                       # IDs à affecter (vide = tous)
  "criterion_weights": {},             # Poids personnalisés
  "minimum_score": 35,                 # Score minimum pour éligibilité
  "enforce_location": true,            # Enforcer géolocalisation
  "enforce_required_skills": true,     # Enforcer compétences obligatoires
  "enforce_contract": true,            # Enforcer type de contrat
  "enforce_languages": true,           # Enforcer langues
  "enforce_availability": false,       # Enforcer disponibilité
  "enforce_diversity_requirements": true,
  "max_solver_time_seconds": 10.0      # Timeout du solveur
}
```

**Réponse** : 
- Affectations optimales sélectionnées
- Candidats non affectés avec raison
- Charge de travail par poste
- Score total et statut du solveur

#### Santé de l'app

```http
GET /api/health                        # {"status": "ok"}
```

## Configuration

### Poids des critères (par défaut)

Les poids par défaut sont définis dans `scoring.py` et peuvent être surpassés via les paramètres API :

```python
DEFAULT_CRITERION_WEIGHTS = {
    "location": 0.1,
    "availability": 0.05,
    "contract": 0.08,
    "salary": 0.08,
    "education": 0.08,
    "experience": 0.12,
    "languages": 0.06,
    "required_skills": 0.2,
    "desired_skills": 0.1,
    "diversity_equity": 0.07,
    "role_alignment": 0.12,
    "motivation": 0.1,
    "culture": 0.05,
    "learning_potential": 0.05,
}
```

### Paramètres du solveur

- `minimum_score` : Score minimum pour qu'une paire candidat-poste soit éligible (défaut : 35/100)
- `max_solver_time_seconds` : Timeout de résolution (défaut : 10s, max : 120s)
- Enforcement flags : Permettent de désactiver certaines contraintes

## Détails techniques

### Scoring textuel

Pour les critères basés sur du texte libre (motivation, alignement de rôle, culture, potentiel d'apprentissage) :

1. **Embedding sémantique** : Si un client d'embedding est disponible, similitude cosinus calculée
2. **Fallback lexical** : Sans embedding, utilise la similarité lexicale et le fuzzy token overlap
3. **Combinaison** : Formules hybrides combinant exact match et similarité sémantique

### Optimisation sous contraintes

Utilise **OR-Tools SAT Solver** pour maximiser :

```
maximize: (nombre d'affectations × 10000) + 
          (somme des scores de compatibilité × 100) + 
          (bonus diversité)
```

Sous les contraintes :
- Chaque candidat affecté à **au maximum 1 poste**
- Chaque poste peut accueillir **jusqu'à sa capacité** de candidats
- Contraintes de diversité **requises** et **préférées** sur les postes
- Filtres d'éligibilité basés sur les critères sélectionnés

## Exemples d'utilisation

### Créer un candidat

```bash
curl -X POST http://localhost:8000/api/candidates \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Alice Dupont",
    "current_title": "Ingénieur Backend",
    "years_experience": 5,
    "email": "alice@example.com",
    "location": {
      "city": "Paris",
      "country": "France",
      "remote_preference": "hybrid",
      "mobility_km": 30
    },
    "skills": [
      {"name": "Python", "level": 4, "category": "technical"},
      {"name": "FastAPI", "level": 3, "category": "technical"},
      {"name": "Français", "level": 5, "category": "language"}
    ],
    "education": {
      "degree": "Master Informatique"
    },
    "preferences": {
      "target_roles": ["Staff Engineer", "Tech Lead"],
      "contract_types": ["cdi"],
      "salary_min": 50000
    },
    "motivation": {
      "free_text": "Je recherche des défis techniques stimulants dans une équipe dynamique."
    }
  }'
```

### Créer un poste

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Ingénieur Backend Senior",
    "team": "Platform Team",
    "location": {
      "city": "Paris",
      "country": "France",
      "work_mode": "hybrid"
    },
    "requirements": {
      "minimum_years_experience": 3,
      "mandatory_skills": ["Python", "FastAPI"],
      "languages": ["Français", "Anglais"]
    },
    "desired_skills": [
      {"name": "Kubernetes", "level": 3, "category": "technical"},
      {"name": "PostgreSQL", "level": 4, "category": "technical"}
    ],
    "missions": "Concevoir et maintenir l\u0027infrastructure backend...",
    "conditions": {
      "contract_type": "cdi",
      "salary_min": 45000,
      "salary_max": 65000,
      "capacity": 2,
      "start_date": "2026-06-01"
    }
  }'
```

### Calculer la compatibilité

```bash
curl -X POST http://localhost:8000/api/compatibility \
  -H "Content-Type: application/json" \
  -d '{
    "top_k_per_candidate": 3
  }'
```

### Réaliser une allocation optimale

```bash
curl -X POST http://localhost:8000/api/assignment \
  -H "Content-Type: application/json" \
  -d '{
    "minimum_score": 50,
    "enforce_diversity_requirements": true,
    "max_solver_time_seconds": 15
  }'
```

## Auteur

- Mark Delaloi
- Alexandre Bodin
- Dylan De Araujo

