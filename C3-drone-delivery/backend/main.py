from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from models import SolveRequest, SolveResponse
from solver import solve
from generator import generate_instance

app = FastAPI(title="Drone Delivery CP-SAT")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.post("/solve", response_model=SolveResponse)
def solve_endpoint(req: SolveRequest):
    return solve(req)


@app.get("/generate", response_model=SolveRequest)
def generate_endpoint(
    n_clients: int = Query(10, ge=1, le=50),
    n_drones: int = Query(3, ge=1, le=10),
    n_zones: int = Query(2, ge=0, le=5),
    seed: int = Query(42),
    center_lat: float = Query(48.8566),
    center_lng: float = Query(2.3522),
    radius_km: float = Query(15.0, ge=1.0, le=100.0),
):
    return generate_instance(
        n_clients=n_clients,
        n_drones=n_drones,
        n_zones=n_zones,
        center_lat=center_lat,
        center_lng=center_lng,
        radius_km=radius_km,
        seed=seed,
    )


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
