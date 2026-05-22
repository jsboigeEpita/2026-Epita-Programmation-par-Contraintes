# Project Tracker — J2 Combinatorial Auctions / WDP

Plan d'équipe et carte de lecture du dépôt. Pour les conventions et le
cycle d'une issue, voir [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).
Pour le suivi détaillé des issues, voir
[`.github/ISSUES.md`](.github/ISSUES.md).

---

## Équipe

| Membre | GitHub | Email (commits) | Rôle principal |
|---|---|---|---|
| Lucas Majerczyk | [Sosolalt](https://github.com/Sosolalt) | `lucas.majerczyk@epita.fr` | Tech lead — modèles CP-SAT + PLNE, VCG, intégration, ops dépôt |
| Nabil Chartouni | [NCH04](https://github.com/NCH04) | `nabil.chartouni@epita.fr` | Benchmarks — générateur synthétique, parser et datasets CATS |
| Wilfrid Wangon-Zekou | [56Nights](https://github.com/56Nights) | `124079558+56Nights@users.noreply.github.com` | Analyse / documentation — heuristique LOS, notebook, notes de recherche, README |

Lucas est tech lead et pousse directement sur `main` pour le cœur des
solveurs ; Nabil et Wilfrid passent par des PR relues par Lucas pour
les modules importants (générateur synthétique, intégration CATS,
refonte du notebook). La rotation des reviewers est visible dans
[`.github/ISSUES.md`](.github/ISSUES.md).

---

## Issues actives (toutes closes au moment de la soumission)

| # | Titre | Owner | Reviewer | Branche | Statut |
|---|---|---|---|---|---|
| 1 | Synthetic instance generator (random + regions) | @NCH04 | @Sosolalt | `feat/generator` | closed (PR #1) |
| 2 | Greedy LOS heuristic | @56Nights | @Sosolalt | main (direct) | closed |
| 3 | CATS parser + 18 official seeds | @NCH04 | @Sosolalt | `feat/cats` | closed (PR #2) |
| 4 | VCG with budget — DSIC analysis | @Sosolalt | @56Nights | main (direct) | closed |
| 5 | CATS benchmarks status note | @NCH04 | @56Nights | main (direct) | closed |
| 6 | Notebook full rebuild | @56Nights | @Sosolalt | `feat/notebook` | closed (PR #3) |

Plusieurs autres changements (data model, solveurs, VCG, fixes, perf,
docs) ont été apportés en direct sur `main` par Lucas. Ils ne portent
pas de numéro d'issue parce que leur scope tient dans un commit.

---

## Conventions

- Commits *Conventional Commits* (`feat`, `fix`, `docs`, `test`,
  `refactor`, `perf`, `chore`, `revert`). Sujet ≤ 60 caractères,
  impératif.
- Scopes dédiés pour la planification : `docs(plan): open issue #N`
  / `docs(plan): close issue #N`.
- Merges des feature branches en `--no-ff`. Le **reviewer** effectue
  le merge ; le merge commit porte `author = owner`, `committer =
  reviewer`, et un trailer `Reviewed-by:`.

Détail dans [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

---

## Méthode de travail

Coordination tactique en groupe privé (messagerie). Les décisions et
livrables formalisés vivent dans le dépôt :

- décisions de design archivées dans [`research/`](research/) (4 notes),
- planning et état des issues dans `PROJECT_TRACKER.md` et
  [`.github/ISSUES.md`](.github/ISSUES.md),
- conventions dans [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md),
- résultats reproductibles dans
  [`J2-CombinatorialAuctions.ipynb`](J2-CombinatorialAuctions.ipynb) +
  [`tests/`](tests/).
