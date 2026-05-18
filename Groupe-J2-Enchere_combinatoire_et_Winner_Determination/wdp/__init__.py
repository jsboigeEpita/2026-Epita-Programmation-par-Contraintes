"""Package wdp : modélisation et résolution du Winner Determination Problem.

Modules :
    instance   - Représentation d'une instance (Item, Bid, Instance) + I/O JSON
    generator  - Génération d'instances synthétiques (random, regions)
    solver_cpsat - Solveur CP-SAT (livrables 1-2-3)
    solver_milp  - Solveur PLNE PuLP/CBC (livrable 4)
    solver_greedy - Heuristique gloutonne par densité (extension)
    cats_parser   - Parser pour le format CATS officiel (Leyton-Brown 2000)
    vcg          - Mécanisme VCG (livrable 5)
"""
