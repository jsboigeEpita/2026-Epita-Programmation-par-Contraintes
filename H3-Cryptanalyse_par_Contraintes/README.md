# H3 - Cryptanalyse par Contraintes

> Utiliser la programmation par contraintes (CP-SAT) pour casser des chiffrements classiques : substitution monoalphabétique, Vigenère, transposition columnar et Hill cipher.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture du projet](#2-architecture-du-projet)
3. [Contraintes linguistiques implémentées](#3-contraintes-linguistiques-implémentées)
4. [Chiffrement par substitution — H3-1](#4-chiffrement-par-substitution--h3-1)
5. [Chiffrement de Vigenère — H3-2](#5-chiffrement-de-vigenère--h3-2)
6. [Chiffrement par transposition — H3-3](#6-chiffrement-par-transposition--h3-3)
7. [Hill Cipher — H3-4](#7-hill-cipher--h3-4)
8. [Évaluation comparée — H3-5](#8-évaluation-comparée--h3-5)
9. [Installation et utilisation](#9-installation-et-utilisation)
10. [Avancement](#10-avancement)

---

## 1. Vue d'ensemble

### Problématique

La cryptanalyse classique repose sur l'**analyse statistique** (fréquences de lettres, bigrammes). L'approche par **programmation par contraintes** encode les propriétés du chiffrement et du langage naturel directement comme des contraintes CSP, permettant une recherche systématique et combinable dans l'espace des clés possibles.

**Avantages de l'approche CP :**
- Combine simultanément plusieurs sources d'information (fréquences, bigrammes, trigrammes, mots connus)
- Chaque connaissance supplémentaire devient une contrainte qui réduit l'espace de recherche
- Garantit l'optimalité de la solution trouvée (preuve formelle)
- Se généralise naturellement à des chiffrements plus complexes

### Ce que le projet n'est pas

Ce projet n'est pas de la cryptanalyse par machine learning ni de la force brute aveugle. La force vient de l'**encodage symbolique des contraintes** : chaque règle du langage et du chiffrement devient une contrainte CSP.

### Résultats obtenus

| Chiffrement | Espace clé | Approche | Précision / Succès | Temps |
|-------------|-----------|----------|--------------------|-------|
| Substitution | 26! ≈ 4×10²⁶ | Analyse de fréquence | ~31% (400 L) | < 1 ms |
| Substitution | 26! ≈ 4×10²⁶ | Hill climbing (trigrammes) | ~85% (400 L) / 40% succès (800 L) | < 2 s |
| Substitution | 26! ≈ 4×10²⁶ | CP-SAT + mot connu | ~92% (400 L) | < 5 s |
| Vigenère | 26^L | IC → CP-SAT | 100% (L=4,5,6) | 4–6 s |
| Transposition | L! | CP-SAT bigrammes | 100% (L=6) | < 0.1 s |
| Hill 2×2 | 26^4 | CP-SAT (texte clair connu) | 100% | < 1 s |
| Hill 2×2 | 26^4 | CP-SAT seul | ~0% (timeout) | ≈ 20 s |

---

## 2. Architecture du projet

```
H3-Cryptanalyse_par_Contraintes/
│
├── README.md
├── requirements.txt
│
├── notebooks/                              ← notebooks Jupyter à exécuter dans l'ordre
│   ├── H3-1-Substitution.ipynb            [✓] Substitution mono — 3 approches + benchmark
│   ├── H3-2-Vigenere.ipynb                [✓] Vigenère — IC + Kasiski + CP-SAT
│   ├── H3-3-Transposition.ipynb           [✓] Transposition — CP-SAT + benchmark
│   ├── H3-4-Hill.ipynb                    [✓] Hill cipher — connu + seul + benchmark
│   └── H3-5-Evaluation.ipynb              [✓] Benchmark comparatif global
│
├── core/
│   ├── ciphers/
│   │   ├── substitution.py                [✓] encrypt / decrypt / key_accuracy
│   │   ├── vigenere.py                    [✓] encrypt / decrypt / str_to_key / key_to_str
│   │   ├── transposition.py               [✓] encrypt / decrypt / generate_random_key / key_accuracy
│   │   └── hill.py                        [✓] encrypt / decrypt / known_plaintext_attack / _matrix_inv_mod26
│   ├── solvers/
│   │   ├── cp_substitution.py             [✓] CP-SAT : AllDifferent + coûts bigrammes + unigrammes
│   │   ├── cp_vigenere.py                 [✓] CP-SAT : agrégation par paire de positions-clé (L² contraintes)
│   │   ├── hill_climbing.py               [✓] Hill climbing bigrammes/trigrammes + restarts
│   │   ├── cp_transposition.py            [✓] CP-SAT : AllDifferent + table agrégée within-row (L-1 contraintes)
│   │   └── cp_hill.py                     [✓] CP-SAT : connu (mod 26 linéaire) + seul (bigrammes)
│   ├── linguistics/
│   │   └── frequency_analysis.py          [✓] IC, Kasiski, bigrammes, trigrammes, freq attack
│   └── evaluation/
│       └── benchmark.py                   [✓] run_trials, print_table, compare_approaches
│
├── data/
│   ├── french_reference.txt               [✓] 8 314 lettres de référence
│   ├── french_bigrams_standard.json       [✓] 676 bigrammes avec log-probabilités
│   └── french_trigrams_standard.json      [✓] 17 576 trigrammes avec log-probabilités
│
└── examples/                              ← graphiques générés par les notebooks
    ├── freq_distributions.png
    ├── benchmark_substitution.png
    ├── vigenere_ic.png
    ├── vigenere_key_length.png
    ├── transpo_freq.png
    ├── transpo_perm_scores.png
    ├── benchmark_transposition.png
    ├── hill_freq.png
    ├── benchmark_hill.png
    ├── evaluation_comparative.png
    └── evaluation_temps.png
```

---

## 3. Contraintes linguistiques implémentées

### 3.1 Indice de coïncidence (IC)

```python
IC = Σ f(l)×(f(l)−1) / (n×(n−1))
```

| Langue | IC typique |
|--------|-----------|
| Français | ~0.065 |
| Anglais | ~0.061 |
| Texte chiffré Vigenère | ~0.038–0.055 |
| Texte uniforme (aléatoire) | ~0.038 |

L'IC est **conservé par une substitution monoalphabétique** (clé fixe) et par la **transposition** — signal clé pour distinguer les types de chiffrement.

### 3.2 Score de bigrammes (fonction objectif CP-SAT)

```python
score = Σ log P(texte_clair[i:i+2])   pour tout i
```

Encodé dans CP-SAT via `AddElement` sur une table de coûts entière :

```python
cost_table[a*26+b] = round(-log_prob('AB') × 1000)
# Faible = bigramme fréquent en français (ES, EN, LE...)
# Élevé  = bigramme rare/impossible (ZX, WK...)

model.add_element(bigram_idx, cost_table, cost_var)
model.minimize(sum(cost_vars))
```

### 3.3 Score de trigrammes

Utilisé par le hill climbing pour une meilleure discrimination (les bigrammes seuls peuvent ne pas distinguer des substitutions proches).

### 3.4 Coûts unigrammes (guide de recherche CP-SAT)

Pour la substitution, on ajoute un coût proportionnel à la distance entre le rang de fréquence de la lettre chiffrée et celui de la lettre claire proposée :

```python
cost_unigram[c] = UNIGRAM_SCALE × |rang_freq(c) − rang_freq_fr(key[c])|
```

26 contraintes `AddElement` supplémentaires qui guident le solveur vers des correspondances cohérentes avec les fréquences.

---

## 4. Chiffrement par substitution — H3-1

### Principe

Chaque lettre du texte clair est remplacée par une lettre fixe. La clé est une **permutation de l'alphabet** (bijection 26→26).

```
Plain  : A B C ... E ... L  A  J  U  S  T  I  C  E ...
Cipher : X Q W ... R ... Y  X  O  Z  K  P  N  C  R ...
```

**Espace** : 26! ≈ 4×10²⁶ — infaisable en force brute.

### Modèle CP-SAT

```
Variables   : key[i] ∈ [0..25] pour i ∈ [0..25]
              key[i] = j  ↔  lettre chiffrée i déchiffrée en lettre j
Contrainte  : AllDifferent(key)
Objectif    : minimize Σ count(c1,c2) × cost_table[key[c1]×26 + key[c2]]
            + Σ UNIGRAM_SCALE × |rang(c) − rang_fr(key[c])|
```

### Trois approches comparées (benchmark, 5 essais, seed=42)

| Approche | Précision (400 L) | Succès complet (800 L) | Temps |
|----------|-------------------|------------------------|-------|
| Analyse de fréquence | ~31% | 0% | < 1 ms |
| Hill climbing (trigrammes) | ~85% | 40% | 0.5–2 s |
| CP-SAT pur | ~14% (timeout) | 0% | ≈ 15 s |
| CP-SAT + mot connu | ~92% | — | < 5 s |

### Force du CP-SAT : les contraintes additionnelles

Quand on connaît un mot du texte clair (ex : "JUSTICE"), on fixe directement les 7 lettres correspondantes :

```python
for p, c in zip("JUSTICE", cipher_of_JUSTICE):
    model.add(key[ord(c)-65] == ord(p)-65)
```

L'espace passe de 26! à 19! — CP-SAT trouve la solution en quelques secondes.

---

## 5. Chiffrement de Vigenère — H3-2

### Principe

La clé est un mot de longueur L. Chaque lettre est décalée par la valeur correspondante de la clé (cycliquement).

```
Clé     :  F   R   A   N   C   E   F   R   A ...
Décalage:  5  17   0  13   2   4   5  17   0 ...
Clair   :  L   A   J   U   S   T   I   C   E ...
Chiffré :  Q   R   J   H   U   X   N   T   E ...
```

`chiffré[i] = (clair[i] + clé[i mod L]) mod 26`

### Pipeline d'attaque

```
1. IC + Kasiski → longueurs candidates {L1, L2, ...}
2. CP-SAT(L1)  → clé candidate + réduction de période
3. Si échec    → CP-SAT(L2), etc.
```

### Modèle CP-SAT (innovation : agrégation par paires)

```
Variables : key[j] ∈ [0..25] pour j ∈ [0..L-1]

Pour chaque paire de positions-clé (j1, j2) :
  agg_cost[a*26+b] = Σ cost_bigram[((ci−a+26)%26)×26 + ((ci1−b+26)%26)]
                     somme sur toutes les positions (i, i+1) où (i%L, (i+1)%L) = (j1, j2)

→ L² contraintes AddElement au total (36 pour L=6)
```

### Résultats (benchmark, 5 essais par longueur, n=200/400/800 L)

| Clé | L | Détection IC | Succès CP-SAT | Temps moyen |
|-----|---|-------------|---------------|-------------|
| CLEF | 4 | ✓ | 100% | ~4 s |
| PARIS | 5 | ✓ | 100% | ~5 s |
| FRANCE | 6 | ✓ | 100% | ~4 s |

---

## 6. Chiffrement par transposition — H3-3

### Principe

Les lettres ne sont **pas substituées** mais **réarrangées** selon une permutation de colonnes.

```
Clair   : BONJOURPARIS  (12 lettres, L=4)
Matrice :  B O N J
           O U R P
           A R I S
Clé     : [3, 1, 0, 2]  (lire les colonnes dans cet ordre)
Chiffré : JPS | OUR | BOA | NRI  → JPSOURBOANRI
```

**Propriété clé** : la transposition **préserve les fréquences** (IC conservé) mais brise les bigrammes → signal pour CP-SAT.

### Modèle CP-SAT

```
Variables   : pos[c] ∈ [0..L-1] pour c ∈ [0..L-1]
              pos[c] = j  ↔  colonne originale c placée en segment j
Contrainte  : AllDifferent(pos)
Objectif    : minimiser coûts bigrammes within-row

Table agrégée : agg_table[p*L + q] = Σ_row bigram_cost(cipher[p*n_rows+row], cipher[q*n_rows+row])
→ L-1 contraintes AddElement seulement (une par paire de colonnes consécutives)
```

### Résultats (benchmark, 5 essais, L=6, seed=42)

| n (lettres) | Précision | Succès (100%) | Temps |
|-------------|-----------|---------------|-------|
| 120 | 100% | 100% | ~0.08 s |
| 240 | 100% | 100% | ~0.09 s |
| 360 | 100% | 100% | ~0.09 s |
| 480 | 100% | 100% | ~0.08 s |

CP-SAT résout la transposition (L=6, L!=720) en moins de 100 ms — résultats parfaits.

---

## 7. Hill Cipher — H3-4

### Principe

Chiffrement **linéaire par blocs** — multiplication matricielle mod 26 sur des blocs de 2 lettres.

```
K = [[6, 24], [1, 13]]   (clé : matrice 2×2 inversible mod 26)
[c1, c2]ᵀ = K × [p1, p2]ᵀ  mod 26
```

**Condition d'inversibilité** : `gcd(det(K) mod 26, 26) = 1`

**Espace** : 26⁴ = 456 976 matrices, dont ~157 248 inversibles.

### Deux approches CP-SAT

**Attaque à texte clair connu** — 2 paires (clair, chiffré) suffisent :
```
K = C × P⁻¹ (mod 26)    →  solution unique, temps < 1 ms (algèbre)
```
CP-SAT encode les équations linéaires mod 26 directement → 100% de succès.

**Attaque texte chiffré seul** :
```
Variables   : kd[i][j] ∈ [0..25]  (matrice de déchiffrement K_inv)
Contrainte  : gcd(det(K_inv), 26) = 1
Objectif    : minimiser Σ bigram_cost(p0[b], p1[b]) + bigram_cost(p1[b], p0[b+1])
```
Modèle purement linéaire (c0, c1 = constantes). Mais le paysage bigramme est trop plat → CP-SAT atteint le timeout.

### Résultats

| Approche | Données | Temps | Succès |
|----------|---------|-------|--------|
| Algèbre directe | 2 paires | < 1 ms | 100% |
| CP-SAT connu (2 paires) | 2 paires | < 1 s | 100% |
| CP-SAT seul | ≥ 50 L | ≈ 20 s (timeout) | ~0% |

---

## 8. Évaluation comparée — H3-5

### Métriques

| Métrique | Description |
|----------|-------------|
| `mean_accuracy` | % de valeurs de clé correctement trouvées (moyenne) |
| `success_rate` | % d'essais avec clé exacte (accuracy ≥ 99%) |
| `mean_time_s` | Temps moyen de résolution (secondes) |

### Protocole

- **5 essais** par longueur, clés aléatoires, `seed=42`
- Timeout CP-SAT fixé à **20 s**
- Corpus français source commun

### Synthèse comparative

| Chiffrement | Approche | Espace clé | Temps | Résultat |
|-------------|----------|-----------|-------|----------|
| Substitution | Analyse de fréquence | 26! | < 1 ms | ~31% précision |
| Substitution | Hill climbing | 26! | 0.5–2 s | ~85% / 40% succès (800 L) |
| Substitution | CP-SAT pur | 26! | ≈ 20 s (timeout) | ~14% |
| Substitution | CP-SAT + mot connu | 19! (ex.) | < 5 s | ~99% |
| Vigenère | IC + CP-SAT | 26^L | ~4 s | 100% (L≤6) |
| Transposition | CP-SAT bigrammes | L=6! | ~0.09 s | ~100% |
| Hill 2×2 | CP-SAT connu | 26^4 / algèbre | < 1 s | 100% |
| Hill 2×2 | CP-SAT seul | 26^4 | ≈ 20 s (timeout) | ~0% |

### Conclusions clés

1. **CP-SAT brille avec des contraintes additionnelles** : mots connus, texte clair partiel, longueur de clé connue
2. **Sans contraintes fortes**, le hill climbing surpasse CP-SAT pour la substitution (QAP NP-difficile)
3. **La longueur du texte est critique** : < 200 lettres difficile même avec hill climbing
4. **Hiérarchie d'attaque** : Transposition ≈ Vigenère > Substitution + connaissance > Substitution seule > Hill seul

---

## 9. Installation et utilisation

### Dépendances

```bash
pip install -r requirements.txt
# → ortools, numpy, matplotlib, jupyter
```

### Lancement des notebooks

```bash
cd H3-Cryptanalyse_par_Contraintes
jupyter notebook notebooks/
```

### Utilisation directe des modules

```python
from core.ciphers.substitution import generate_random_key, encrypt
from core.linguistics.frequency_analysis import bigram_log_probs, trigram_log_probs, letter_frequencies
from core.solvers.hill_climbing import hill_climbing_attack
from core.solvers.cp_substitution import solve_substitution
from core.ciphers.vigenere import encrypt as v_encrypt
from core.solvers.cp_vigenere import solve_vigenere
from core.ciphers.transposition import generate_random_key as trans_gen_key, encrypt as trans_enc
from core.solvers.cp_transposition import solve_transposition

# Substitution
with open('data/french_reference.txt') as f:
    corpus = f.read()
blp = bigram_log_probs(corpus)
tlp = trigram_log_probs(corpus)
lf  = letter_frequencies(corpus)

key = generate_random_key()
cipher = encrypt("BONJOUR MONDE", key)
result = hill_climbing_attack(cipher, blp, lf, ngram_size=3)

# Vigenère
from core.linguistics.frequency_analysis import detect_key_length_ic
cipher_v = v_encrypt("BONJOUR MONDE", [5, 17, 0, 13, 2, 4])  # FRANCE
L = detect_key_length_ic(cipher_v)[0][0]
res = solve_vigenere(cipher_v, L, blp)
print(res['key_str'])  # → FRANCE

# Transposition
key_t = trans_gen_key(6)
cipher_t = trans_enc("BONJOUR MONDE", key_t)
res_t = solve_transposition(cipher_t, 6, blp)
print(res_t['key'])
```

### Ordre des notebooks

| Notebook | Contenu | Durée estimée |
|----------|---------|---------------|
| `H3-1-Substitution.ipynb` | Substitution mono, 3 approches, benchmark | ~6 min |
| `H3-2-Vigenere.ipynb` | IC, Kasiski, CP-SAT, pipeline complet | ~5 min |
| `H3-3-Transposition.ipynb` | Transposition, permutation CP-SAT | ~3 min |
| `H3-4-Hill.ipynb` | Hill cipher, algèbre mod 26 | ~5 min |
| `H3-5-Evaluation.ipynb` | Benchmark comparatif global | ~15 min |

---

## 10. Avancement

### Terminé ✓

- [x] **H3-1 — Substitution monoalphabétique**
  - [x] `core/ciphers/substitution.py` — encrypt, decrypt, key_accuracy
  - [x] `core/solvers/cp_substitution.py` — AllDifferent + coûts bigrammes + coûts unigrammes
  - [x] `core/solvers/hill_climbing.py` — bigrammes/trigrammes, restarts aléatoires
  - [x] `notebooks/H3-1-Substitution.ipynb` — 3 approches + CP-SAT avec mots connus + benchmark

- [x] **H3-2 — Vigenère**
  - [x] `core/ciphers/vigenere.py` — encrypt, decrypt, réduction de période
  - [x] `core/linguistics/frequency_analysis.py` — IC, Kasiski, detect_key_length_ic
  - [x] `core/solvers/cp_vigenere.py` — agrégation par paires, L² contraintes, 100% sur L=4,5,6
  - [x] `notebooks/H3-2-Vigenere.ipynb` — IC, Kasiski, CP-SAT, benchmark multi-clés

- [x] **H3-3 — Transposition columnar**
  - [x] `core/ciphers/transposition.py` — encrypt, decrypt, generate_random_key, key_accuracy
  - [x] `core/solvers/cp_transposition.py` — AllDifferent + table agrégée within-row, L-1 contraintes
  - [x] `notebooks/H3-3-Transposition.ipynb` — IC conservé, CP-SAT, benchmark L=4..8

- [x] **H3-4 — Hill cipher**
  - [x] `core/ciphers/hill.py` — encrypt, decrypt, known_plaintext_attack, _matrix_inv_mod26
  - [x] `core/solvers/cp_hill.py` — attaque connue (linéaire mod 26) + attaque seule (bigrammes)
  - [x] `notebooks/H3-4-Hill.ipynb` — algèbre, CP-SAT connu (100%), CP-SAT seul

- [x] **H3-5 — Évaluation comparée**
  - [x] `core/evaluation/benchmark.py` — run_trials, print_table, compare_approaches
  - [x] `notebooks/H3-5-Evaluation.ipynb` — benchmark global 4 chiffrements + courbes comparatives

- [x] **Données linguistiques**
  - [x] `data/french_reference.txt` — 8 314 lettres de référence
  - [x] `data/french_bigrams_standard.json` — 676 bigrammes
  - [x] `data/french_trigrams_standard.json` — 17 576 trigrammes
