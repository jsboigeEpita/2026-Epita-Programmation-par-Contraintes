from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from diet import build_weekly_menu
from preprocessing import build_dataset

ROOT = Path(__file__).parent
EXCEL_CANDIDATES = [
    ROOT / "Table Ciqual 2025_FR_2025_11_03.xlsx",
    ROOT / "Table_Ciqual_2020.xlsx",
]
CSV_CACHE = ROOT / "ciqual_clean.csv"

STATE: dict = {}


def load_dataset():
    if CSV_CACHE.exists():
        foods, nutrients, df = build_dataset(
            excel_path=str(EXCEL_CANDIDATES[0]),
            csv_cache=str(CSV_CACHE),
            force_rebuild=False,
        )
        return foods, nutrients, df

    excel = next((p for p in EXCEL_CANDIDATES if p.exists()), None)
    if excel is None:
        raise RuntimeError(
            "Aucune source de données trouvée. Place un des fichiers suivants à la racine du projet :\n"
            f"  - {EXCEL_CANDIDATES[0].name} (Ciqual 2025)\n"
            f"  - ou un cache déjà généré : {CSV_CACHE.name}"
        )
    return build_dataset(excel_path=str(excel), csv_cache=str(CSV_CACHE), force_rebuild=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    foods, nutrients, df = load_dataset()
    STATE["foods"] = foods
    STATE["nutrients"] = nutrients
    STATE["df"] = df
    yield
    STATE.clear()


app = FastAPI(title="Diet Planner", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class MenuRequest(BaseModel):
    days: int = Field(7, ge=1, le=14)
    meals_per_day: int = Field(2, ge=1, le=4)
    budget_eur: float | None = Field(None, ge=0)
    vegetarian: bool = False
    excluded_foods: list[str] = []
    seed: int | None = None


@app.get("/api/foods")
def list_foods():
    foods = STATE["foods"]
    return [
        {"nom": f[0], "categorie": f[-1], "prix_cts_100g": f[1]}
        for f in foods
    ]


@app.get("/api/nutrients")
def list_nutrients():
    return [
        {"nom": n[0], "min": n[1], "max": n[2]}
        for n in STATE["nutrients"]
    ]


@app.post("/api/menu")
def generate_menu(req: MenuRequest):
    try:
        weekly = build_weekly_menu(
            STATE["foods"],
            STATE["nutrients"],
            days=req.days,
            meals_per_day=req.meals_per_day,
            seed=req.seed,
            budget_eur=req.budget_eur,
            vegetarian=req.vegetarian,
            excluded_foods=req.excluded_foods or None,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur du solveur : {exc}") from exc

    total = 0.0
    days_payload = []
    for day_meals in weekly:
        meals = []
        for meal in day_meals:
            meals.append({
                "status": meal["status"],
                "cost": round(float(meal["cost"]), 2),
                "foods": [{"nom": n, "qty_g": int(q)} for (n, q) in meal["foods"]],
            })
            total += meal["cost"]
        days_payload.append(meals)

    return {
        "days": days_payload,
        "total_cost": round(total, 2),
        "params": req.model_dump(),
    }


STATIC_DIR = ROOT / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")
