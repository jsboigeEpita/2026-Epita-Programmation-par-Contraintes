from pathlib import Path
import re
import pandas as pd


# Everyting is over 100g
COLUMNS_MAP = {
    "alim_code":         "code",
    "alim_nom_fr":       "nom",
    "alim_grp_nom_fr":   "groupe",
    "alim_ssgrp_nom_fr": "sous_groupe",
    "Energie,\nRèglement\nUE N°\n1169\n2011 (kcal\n100 g)": "kcal",
    "Protéines,\nN x\nfacteur de\nJones (g\n100 g)":        "prot_g",
    "Lipides\n(g\n100 g)":                                   "lip_g",
    "Glucides\n(g\n100 g)":                                  "gluc_g",
    "Fibres\nalimentaires\n(g\n100 g)":                      "fibres_g",
    "Sel\nchlorure\nde\nsodium\n(g\n100 g)":                 "sel_g",
    "Calcium\n(mg\n100 g)":                                  "calcium_mg",
    "Fer (mg\n100 g)":                                       "fer_mg",
}

NUTRIMENTS = ["kcal", "prot_g", "lip_g", "gluc_g", "fibres_g", "sel_g", "calcium_mg", "fer_mg"]

GROUPES_EXCLUS = {
    "aliments infantiles",
    "glaces et sorbets",
    "boissons",
    "aides culinaires et ingrédients divers",
}

SOUS_GROUPES_EXCLUS = {
    "huiles de poissons", "autres matières grasses", "margarines",
    "huiles et graisses végétales", "beurres",
    "confiseries non chocolatées", "chocolats et produits à base de chocolat",
    "sucres, miels et assimilés", "boissons alcoolisées", "boissons sans alcool",
    "crèmes et spécialités à base de crème", "fromages et alternatives végétales",
    "farines", "biscuits apéritifs", "fruits à coque et graines oléagineuses",
    "céréales de petit-déjeuner", "biscuits sucrés", "viennoiseries",
    "confitures et assimilés", "boisson alcoolisées", "pains et assimilés",
    "produits sucrés", "gâteaux et pâtisseries", "barres céréalières",
    "charcuteries et alternatives végétales", "fruits secs", "fruits séchés",
}

MOTS_CLES_EXCLUS = [
    "cru", "non cuit",
    "déshydraté", "lyophilisé", "s[eéè]ch",
    "abats", "tripes", "rognon", "foie gras",
    "bouillon", "fond de", "sirop", "confiserie",
    "farine", "amidon", "fécule", "graine",
    "biscotte", "pain grillé", "croûton", "feuille de brick",
    "chips", "biscuit apéritif", "poudre", "concentré",
    "salé", "grillé, salé", "produits céréaliers",
]

# FIXME not sure how to handle that
# Niveau 1 — mots-clés dans le nom (ordre : du plus cher au moins cher à l'intérieur d'un type)
PRIX_MOTS_CLES = [
    # poissons & fruits de mer
    (r"huître|saint-jacques|homard|langouste",          28.0),
    (r"crevette|gambas",                                18.0),
    (r"saumon fumé|tarama",                             20.0),
    (r"saumon",                                         15.0),
    (r"dorade|bar|sole|turbot|loup de mer|daurade",     18.0),
    (r"truite",                                         12.0),
    (r"cabillaud|merlu|colin|lieu|haddock",             10.0),
    (r"thon",                                            8.0),
    (r"moule|palourde",                                  5.0),
    (r"sardine|maquereau|hareng|anchois|pilchard",       4.0),
    # viandes
    (r"agneau|gigot|côtelette d'agneau",                20.0),
    (r"veau",                                           18.0),
    (r"bœuf|boeuf|steak|entrecôte|rumsteak|bourguignon|côte de bœuf", 16.0),
    (r"canard|magret|confit",                           14.0),
    (r"lapin",                                          12.0),
    (r"porc|cochon|côte de porc|filet de porc",         10.0),
    (r"saucisse|merguez|chipolata",                      9.0),
    (r"poulet|dinde|volaille|pintade|caille",            7.0),
    # légumes (ordre : rares/hors-saison → courants)
    (r"asperge|artichaut|fenouil|endive",                7.0),
    (r"haricot vert|brocoli|épinard|blette|chou-fleur",  4.0),
    (r"courgette|aubergine|poivron|poireau",              3.0),
    (r"tomate|concombre|céleri|navet|betterave",          2.5),
    (r"carotte|chou|oignon|ail|échalote",                 1.5),
    (r"pomme de terre|patate douce",                      1.5),
    # fruits
    (r"fraise|framboise|myrtille|cerise|groseille",       7.0),
    (r"mangue|ananas|papaye|litchi|grenade|fruit de la passion", 5.0),
    (r"kiwi|raisin|figue|prune|pêche|nectarine|abricot",  4.0),
    (r"pomme|poire|banane|orange|mandarine|citron|pamplemousse", 2.0),
    # céréales
    (r"quinoa|épeautre|boulgour|sarrasin",                5.0),
    (r"pâtes|riz|semoule|maïs|polenta",                   2.0),
    # laitages
    (r"crème fraîche|crème épaisse",                      4.0),
    (r"yaourt|fromage blanc|skyr|faisselle",               3.0),
    (r"lait",                                              1.5),
]

# Niveau 2 — sous_groupe (fallback si aucun mot-clé ne matche)
PRIX_SOUS_GROUPE = {
    "viandes cuites":                                    12.0,
    "autres produits à base de viande":                  10.0,
    "poissons cuits":                                    10.0,
    "poissons crus":                                     10.0,
    "mollusques et crustacés cuits":                     12.0,
    "produits à base de poissons et produits de la mer": 10.0,
    "oeufs":                                              4.0,
    "légumes":                                            2.5,
    "salades composées et crudités":                      5.0,
    "pommes de terre et autres tubercules":               2.0,
    "légumineuses":                                       3.0,
    "pâtes, riz et céréales":                             2.0,
    "fruits":                                             3.0,
    "produits laitiers frais et alternatives végétales":  3.0,
    "laits":                                              1.5,
    "soupes":                                             4.0,
    "plats composés":                                     8.0,
    "pizzas, tartes et crêpes salées":                    7.0,
    "sandwichs":                                          8.0,
    "feuilletées et autres entrées":                      7.0,
    "pâtes à tarte":                                      4.0,
}

# Niveau 3 — groupe (dernier recours)
PRIX_EUR_KG = {
    "fruits, légumes, légumineuses et oléagineux": 3.0,
    "viandes, oeufs, poissons":                   12.0,
    "produits laitiers":                            5.0,
    "entrées et plats composés":                    8.0,
    "produits céréaliers":                          4.0,
}
PRIX_EUR_KG_DEFAUT = 5.0

MAX_G = {
    "fruits, légumes, légumineuses et oléagineux": 500,
    "viandes, oeufs, poissons":                    300,
    "produits laitiers":                           400,
    "entrées et plats composés":                   400,
    "produits céréaliers":                         300,
}
MAX_G_DEFAUT = 300

CATEGORIE_SOUS_GROUPE = {
    "légumes":                                           "légume",
    "salades composées et crudités":                     "légume",
    "pommes de terre et autres tubercules":              "féculent",
    "légumineuses":                                      "féculent",
    "pâtes, riz et céréales":                           "féculent",
    "viandes cuites":                                    "viande",
    "autres produits à base de viande":                  "viande",
    "poissons cuits":                                    "poisson",
    "poissons crus":                                     "poisson",
    "mollusques et crustacés cuits":                     "poisson",
    "produits à base de poissons et produits de la mer": "poisson",
    "oeufs":                                             "protéine",
    "fruits":                                            "dessert",
    "produits laitiers frais et alternatives végétales": "dessert",
    "laits":                                             "dessert",
}

CATEGORIE_GROUPE = {
    "viandes, oeufs, poissons": "protéine",
    "produits laitiers":        "dessert",
    "produits céréaliers":      "féculent",
}

NUTRIENTS = [
    ("kcal",       1100, 1300),
    ("prot_g",       30,   80),
    ("lip_g",        30,   50),
    ("gluc_g",      125,  175),
    ("fibres_g",     13, None),
    ("sel_g_x10",     0,   25),
    ("calcium_mg",  475, 1250),
    ("fer_mg_x10",  55,  140),
]


def load_ciqual(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0)
    return df[list(COLUMNS_MAP.keys())].rename(columns=COLUMNS_MAP)


def clean_numeric(df: pd.DataFrame) -> pd.DataFrame:
    for col in NUTRIMENTS:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.replace(",", ".", regex=False)
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.fillna({col: 0 for col in NUTRIMENTS})


def filter_foods(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["groupe", "nom"])
    df = df[~df["groupe"].str.lower().isin(GROUPES_EXCLUS)]
    df = df[~df["sous_groupe"].str.lower().isin(SOUS_GROUPES_EXCLUS)]
    df = df[~df["nom"].str.lower().str.contains("|".join(MOTS_CLES_EXCLUS), regex=True, na=False)]
    df = df[~df["nom"].str.lower().str.startswith("lait de")]
    df = df[df["kcal"] > 0]
    return df.reset_index(drop=True)


def _prix_cts_100g(nom: str, sous_groupe: str, groupe: str) -> int:
    nom_lower = nom.lower()
    for pattern, eur_kg in PRIX_MOTS_CLES:
        if re.search(pattern, nom_lower):
            return int(round(eur_kg * 10))
    eur_kg = (PRIX_SOUS_GROUPE.get(sous_groupe)
              or PRIX_EUR_KG.get(groupe)
              or PRIX_EUR_KG_DEFAUT)
    return int(round(eur_kg * 10))


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    df["prix_cts_100g"] = df.apply(
        lambda r: _prix_cts_100g(r["nom"], r["sous_groupe"], r["groupe"]), axis=1
    )
    df["min_g"] = 50
    df["max_g"] = df["groupe"].map(lambda g: MAX_G.get(g, MAX_G_DEFAUT))
    df["categorie"] = df.apply(
        lambda r: CATEGORIE_SOUS_GROUPE.get(r["sous_groupe"])
               or CATEGORIE_GROUPE.get(r["groupe"])
               or "autre",
        axis=1,
    )
    return df


def to_foods_tuples(df: pd.DataFrame) -> list:
    return [
        (
            r.nom, int(r.prix_cts_100g),
            int(round(r.kcal)), int(round(r.prot_g)), int(round(r.lip_g)),
            int(round(r.gluc_g)), int(round(r.fibres_g)),
            int(round(r.sel_g * 10)), int(round(r.calcium_mg)), int(round(r.fer_mg * 10)),
            int(r.min_g), int(r.max_g), r.categorie,
        )
        for r in df.itertuples(index=False)
    ]


def build_dataset(excel_path: str = "Table_Ciqual_2020.xlsx",
                  csv_cache: str = "ciqual_clean.csv",
                  force_rebuild: bool = True) -> tuple:
    if Path(csv_cache).exists() and not force_rebuild:
        df = pd.read_csv(csv_cache)
    else:
        df = load_ciqual(excel_path)
        df = clean_numeric(df)
        df = filter_foods(df)
        df = enrich(df)
        df.to_csv(csv_cache, index=False)
    return to_foods_tuples(df), NUTRIENTS, df


if __name__ == "__main__":
    foods, _, df = build_dataset("Table Ciqual 2025_FR_2025_11_03.xlsx")
    print(f"{len(foods)} aliments")
    for f in foods[:3]:
        print(f)
