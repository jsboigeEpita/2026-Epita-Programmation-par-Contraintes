# H1 — Composition mélodique assistée par contraintes

> **Auteurs** : *Sam Krief et Nicolas Teisseire*

---

## Présentation rapide

Ce projet génère des **mélodies monodiques** (une seule voix) qui respectent les règles de base de la musique tonale, en utilisant le solveur **OR-Tools CP-SAT**.

L'idée centrale : une mélodie correcte est une suite de notes qui satisfait simultanément un ensemble de règles musicales (rester dans une gamme, éviter les sauts trop grands, finir sur la tonique, etc.). C'est très exactement un **problème de satisfaction de contraintes** au sens du cours, et on le résout comme tel.

À la sortie, on obtient des fichiers MIDI écoutables, dans 3 styles différents (`fluide`, `aventureux`, `minimaliste`), en plusieurs tonalités (Do majeur, Sol majeur, La mineur).

---

## Approche choisie

Il existe deux grandes façons de générer de la musique automatiquement :

1. **Modèles génératifs** (RNN, transformers) — apprennent un style à partir d'exemples, mais sans garantie sur le respect des règles.
2. **Programmation par contraintes** — encode explicitement les règles ; toute sortie produite est garantie correcte par construction.

On choisit la deuxième, qui est l'objet du cours. La créativité émerge ici non pas d'un modèle appris, mais de la **combinaison de contraintes strictes et de préférences pondérées**. On peut formuler ça simplement : on définit ce que veut dire "une mélodie correcte" via des contraintes, et on demande au solveur d'en trouver une qui maximise nos préférences stylistiques.

### Périmètre volontairement restreint

Pour rester dans le temps imparti, on s'est fixé un périmètre clair :

- **Une seule voix** (pas de polyphonie, pas de contrepoint à plusieurs voix)
- **Hauteurs uniquement** (toutes les notes durent une noire — pas de rythme variable)
- **Un seul solveur** : OR-Tools CP-SAT (le solveur du cours)
- **Trois tonalités** : Do majeur, Sol majeur, La mineur
- **Pas d'évaluation humaine formelle** — on vérifie objectivement le respect des règles et on laisse le jury écouter

Ce périmètre nous permet de **bien expliquer chaque ligne de code** plutôt que d'empiler des features superficielles. C'est aussi cohérent avec la promesse pédagogique du cours : montrer un CSP simple, son modèle, ses contraintes, son optimisation.

---

## Notions du cours mobilisées

| Notebook du cours | Ce qu'on en utilise |
|---|---|
| **CSP-1 — Fondamentaux** | Formalisation (X, D, C), réduction de domaine, `AddAllowedAssignments` |
| **CSP-5 — Optimization** | `Minimize`, fonction objectif, `AddAbsEquality`, `AddMaxEquality` |
| **CSP-7 — Soft Constraints** | Weighted CSP, variables de coût, somme pondérée |

On a volontairement laissé de côté Search-4 (recherche locale) : il serait pertinent pour des problèmes très grands, mais pour des mélodies de 16-24 notes, CP-SAT termine en moins de 10 secondes — la recherche locale n'apporterait rien ici.

---

## Architecture du code

```
h1-melody-csp/
│
├── README.md                          ← ce fichier
├── requirements.txt
├── H1-Melody-Generation.ipynb         ← notebook pédagogique principal
│
├── melody/                            ← le code, organisé en 3 modules
│   ├── __init__.py
│   ├── music_theory.py                ← constantes musicales et helpers MIDI
│   ├── solver.py                      ← le cœur CP-SAT (variables, contraintes, profils)
│   └── export.py                      ← export MIDI et piano-roll matplotlib
│
└── outputs/                           ← MIDI générés par le notebook
    └── demo_*.mid
```

**Volume** : environ 400 lignes de Python au total (commentaires inclus).
**Dépendances** : seulement `ortools`, `midiutil`, `matplotlib`. Pas de music21, pas de framework lourd.

### Organisation des modules

- `music_theory.py` — tout le **savoir musical** : gammes, pitch classes, conversion MIDI ↔ noms de notes. Aucune logique CP ici.
- `solver.py` — tout le **savoir CP** : construction du modèle, hard et soft constraints, fonction `solve()`. Aucune logique musicale "en dur" : tout passe par les helpers de `music_theory.py`.
- `export.py` — sortie : fichier MIDI et visualisation piano-roll.

Cette séparation est volontaire et défendable à la soutenance : on peut **changer de gamme sans toucher au solveur**, et **changer de solveur sans toucher à la théorie musicale**.

---

## Modélisation CSP — vue d'ensemble

### Variables

Pour une mélodie de $n$ notes :

$$X = \{p_0, p_1, \dots, p_{n-1}\}$$

Chaque $p_t$ est une variable entière représentant la hauteur MIDI de la $t$-ième note.

### Domaines

Plutôt que d'utiliser $D_t = [0, 127]$ (toutes les hauteurs MIDI) et de poser ensuite une contrainte "appartenance à la gamme", on **restreint directement le domaine** :

$$D_t = \{p \in [55, 79] \mid p \bmod 12 \in \text{gamme}\}$$

Soit environ 15 hauteurs au lieu de 128. C'est la première grosse réduction de l'espace de recherche, et elle se fait *gratuitement* via `NewIntVarFromDomain`.

### Hard constraints

| # | Contrainte | Encodage CP |
|---|---|---|
| C1 | Première note = tonique | `AddAllowedAssignments([p_0], tonic_values)` |
| C2 | Dernière note = tonique | `AddAllowedAssignments([p_{n-1}], tonic_values)` |
| C3 | Avant-dernière = V ou VII (cadence) | `AddAllowedAssignments([p_{n-2}], cadence_values)` |
| C4 | Sauts ≤ une quinte | `AddAbsEquality(|p_{t+1} - p_t|) <= 7` |
| C5 | Pas deux notes identiques consécutives | `|p_{t+1} - p_t| >= 1` |

C1 et C2 ancrent la mélodie sur sa tonique. C3 force une cadence finale (V→I ou VII→I), ce qui donne l'impression musicale d'une phrase qui se termine vraiment. C4 borne les sauts pour rester chantable. C5 évite les répétitions immédiates triviales.

### Soft constraints (Weighted CSP)

Pour chaque préférence, on crée des **variables de coût** que le solveur minimise.

| Préférence | Coût | Effet |
|---|---|---|
| `smoothness` | proportionnel à `max(0, |saut| - 2)` | favorise le mouvement conjoint |
| `range` | proportionnel à `max(0, 12 - ambitus)` | force à couvrir au moins une octave |
| `direction` | constant à chaque continuation de direction | encourage le changement de direction |
| `no_oscillation` | constant si `p_{t+2} == p_t` | évite les motifs A-B-A-B |

Tous ces coûts sont sommés, et l'objectif est :

$$\min \sum_i w_i \cdot \text{violation}_i$$

où les $w_i$ sont les poids spécifiques au profil stylistique choisi.

### Profils stylistiques

Un **profil** est juste un jeu de poids. On en a défini trois :

| Profil | smoothness | range | direction | no_oscillation |
|---|---|---|---|---|
| **fluide** | 5 | 1 | 1 | 3 |
| **aventureux** | 1 | 5 | 3 | 2 |
| **minimaliste** | 3 | 0 | 0 | 1 |

C'est le point de démonstration scientifique principal : **changer les poids change le style** de manière prévisible. Pour s'en convaincre, on calcule pour chaque profil l'ambitus moyen et la taille moyenne des sauts, et on retrouve ce qu'on attendait : `fluide` a des sauts plus petits que `aventureux`, etc.

---

## Diversification des solutions

Premier problème quand on relance le solveur avec les mêmes paramètres : on obtient souvent la même mélodie. C'est normal — il existe plusieurs mélodies optimales et le solveur retombe sur la première qu'il trouve.

Pour générer plusieurs mélodies réellement différentes, on utilise la fonction `solve_many()`. Elle ajoute à chaque appel une **contrainte d'exclusion** sur les solutions déjà produites :

```python
# Pour chaque mélodie déjà générée, on impose :
#   au moins une de ses notes doit différer
for prev in blocklist:
    model.AddBoolOr([pitch[t] != prev[t] for t in range(n)])
```

Cette technique est dans l'esprit du cours (cf. CSP-5 sur la dominance breaking et l'énumération de solutions) et donne immédiatement de la diversité.

---

## Comment lancer le projet

### Installation

```bash
git clone <url-du-repo>
cd h1-melody-csp
python -m venv .venv
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

### Utilisation rapide depuis Python

```python
from melody import solve, to_midi, to_text

# Générer une mélodie de 16 notes en Do majeur, style fluide
melody = solve(n_notes=16, scale_name='C_major', profile='fluide')

# L'afficher en notation musicale lisible
print(to_text(melody))     # ex : C4 D4 E4 F4 G4 A4 B4 C5 ...

# L'exporter en MIDI
to_midi(melody, 'ma_melodie.mid', tempo=110)
```

### Notebook pédagogique

Tout est expliqué pas à pas dans `H1-Melody-Generation.ipynb` :

```bash
jupyter notebook H1-Melody-Generation.ipynb
```

Le notebook contient :
1. Présentation du problème en CSP, calcul de la taille de l'espace
2. Théorie musicale (le strict minimum)
3. Le premier modèle, hard constraints seules
4. Ajout des soft constraints et profils
5. Démos visuelles (piano-rolls) et export MIDI

### Écouter les MIDI générés

- **VLC** ou **MuseScore** (gratuit) sur l'ordinateur
- En ligne : https://onlinesequencer.net/import (drag-and-drop du `.mid`)

---

## Évaluation : vérification automatique des règles

Comme on n'est pas musiciens professionnels, on ne se prononce pas sur "la beauté" des mélodies. À la place, on vérifie **objectivement** que chaque mélodie générée respecte les 6 règles définies (5 hard constraints + une vérification d'unicité).

Le notebook contient une fonction `check_melody()` qui passe la mélodie au crible et affiche `[OK]` ou `[ECHEC]` pour chaque règle. Sur toutes nos générations, toutes les hard constraints sont validées — c'est garanti par le solveur, mais c'est rassurant à montrer en démo.

Côté soft constraints, on observe statistiquement (taille moyenne des sauts, ambitus) que les profils produisent bien les effets attendus.

L'évaluation "à l'oreille" est faite par le jury pendant la soutenance.

---

## Limitations assumées

- **Pas de polyphonie** : on ne traite qu'une voix. Ajouter une basse demanderait de nouvelles contraintes de consonance entre voix, ce qui sort de notre périmètre.
- **Rythme fixe** : toutes les notes durent une noire. Ajouter le rythme demanderait des variables `duration[t]` et des contraintes métriques (somme des durées = nombre de mesures).
- **Tonalité fixe** : pas de modulation en cours de mélodie. Ajouter ça reviendrait à modéliser une variable `key[t]` qui change le domaine de chaque note dynamiquement — possible mais complexe.

Ces limitations sont des perspectives d'extension naturelles, pas des défauts du modèle. Elles montrent que notre approche est **modulaire** : on peut ajouter chacune de ces dimensions sans casser ce qui existe.

---

## Références

### Notebooks du cours
- CSP-1 — Fondamentaux des CSP
- CSP-5 — Optimisation combinatoire en CP
- CSP-7 — Soft Constraints

### Outils
- OR-Tools CP-SAT — https://developers.google.com/optimization/cp/cp_solver
- midiutil — https://github.com/MarkCWirt/MIDIUtil

### Articles
- Anders, T. (2009). *Composing Music by Composing Rules: Computer-Assisted Composition Using Constraint Programming*. PhD Thesis, Queen Mary University of London.
- Truchet, C., & Codognet, P. (2004). *Musical Constraint Satisfaction Problems Applied to Harmony*. Constraints, 9(1), 23–44.

---

*Projet réalisé dans le cadre du cours de Programmation par Contraintes, EPITA SCIA, promo 2026.*