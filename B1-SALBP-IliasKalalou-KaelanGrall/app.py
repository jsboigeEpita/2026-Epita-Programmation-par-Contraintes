import os
import tempfile
from dataclasses import replace as dc_replace
from pathlib import Path

import pandas as pd
import streamlit as st

from benchmark import run_benchmark
from instances import Instance, Solution
from instances.library import classic_metadata, list_classics, load_classic
from instances.multimodel import MultiModelInstance, to_aggregated_instance, two_model_toy
from instances.otto import AlbParseError, parse_alb
from instances.toy import toy_instance
from instances.validators import InstanceValidationError, validate_instance, validate_precedences
from solvers import cpsat, plne, rpw
from solvers.multimodel import solve_mmalbp
from visualisation.gantt import draw_gantt
from visualisation.loads import draw_station_loads
from visualisation.precedence import draw_precedence_graph


MAX_UPLOAD_BYTES = 1_000_000
SOLVER_NAMES = [
    "CP-SAT — SALBP-1",
    "CP-SAT — SALBP-2",
    "PLNE (CBC) — SALBP-1",
    "RPW (heuristique) — SALBP-1",
]


st.set_page_config(page_title="SALBP Solver", page_icon="⚙", layout="wide")
st.title("SALBP — Équilibrage de chaîne d'assemblage")
st.caption("Groupe B1 : Ilias Kalalou & Kaelan Grall — EPITA SCIA 2026")


def display_solution(solution: Solution, instance: Instance, key_prefix: str = "") -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stations", solution.n_stations)
    c2.metric("Cycle time", solution.cycle_time)
    c3.metric("Optimal", "Oui" if solution.optimal else "Non")
    c4.metric("Temps", f"{solution.time_ms:.1f} ms")

    tabs = st.tabs(["Gantt", "Charges", "Affectation"])
    with tabs[0]:
        st.pyplot(draw_gantt(solution, instance))
    with tabs[1]:
        st.pyplot(draw_station_loads(solution, instance))
    with tabs[2]:
        rows = [
            {"Tâche": t, "Durée": instance.durations[t], "Station": solution.assignment[t]}
            for t in sorted(instance.tasks)
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True, key=f"{key_prefix}_tbl")


def run_solver_single(name: str, instance: Instance, n_stations: int, time_limit: float) -> Solution | None:
    if name == "CP-SAT — SALBP-1":
        return cpsat.solve_salbp1(instance, time_limit=time_limit)
    if name == "CP-SAT — SALBP-2":
        return cpsat.solve_salbp2(instance, n_stations=n_stations, time_limit=time_limit)
    if name == "PLNE (CBC) — SALBP-1":
        return plne.solve_salbp1(instance, time_limit=time_limit)
    if name == "RPW (heuristique) — SALBP-1":
        return rpw.solve_salbp1(instance)
    return None


def _safe_parse_uploaded(uploaded, cycle_override: int | None) -> Instance | None:
    if uploaded.size > MAX_UPLOAD_BYTES:
        st.error(f"Fichier trop volumineux ({uploaded.size} octets, max {MAX_UPLOAD_BYTES}).")
        return None
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".alb") as tmp:
            tmp.write(uploaded.read())
            tmp_path = Path(tmp.name)
        return parse_alb(tmp_path, cycle_time=cycle_override)
    except AlbParseError as e:
        st.error(f"Erreur de parsing : {e}")
        return None
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def load_instance_ui() -> tuple[Instance | None, dict | None]:
    source = st.radio(
        "Source de l'instance",
        ["Instance jouet", "Bibliothèque classique", "Fichier Otto (.alb)", "Édition manuelle"],
        horizontal=False,
    )

    if source == "Instance jouet":
        base = toy_instance()
        cycle = st.number_input("Cycle time", min_value=1, value=base.cycle_time, key="toy_cycle")
        inst = base if cycle == base.cycle_time else dc_replace(base, cycle_time=cycle)
        return inst, None

    if source == "Bibliothèque classique":
        name = st.selectbox("Instance", list_classics())
        meta = classic_metadata(name)
        st.write(f"{meta['n_tasks']} tâches, {meta['n_precedences']} précédences")
        cycle = st.number_input(
            "Cycle time",
            min_value=1,
            value=meta["default_cycle"],
            key="lib_cycle",
        )
        inst = load_classic(name, cycle_time=cycle)
        info = {
            "known_optimum": meta["known_optimum"],
            "default_cycle": meta["default_cycle"],
            "valid_for_cycle": cycle == meta["default_cycle"],
        }
        return inst, info

    if source == "Fichier Otto (.alb)":
        uploaded = st.file_uploader("Fichier .alb", type=["alb"])
        if uploaded is None:
            st.info(f"Téléversez un fichier .alb (max {MAX_UPLOAD_BYTES // 1000} Ko) pour continuer.")
            return None, None
        cycle_override_raw = st.number_input(
            "Cycle time (0 = celui du fichier)",
            min_value=0,
            value=0,
            key="otto_cycle",
        )
        cycle_override = cycle_override_raw if cycle_override_raw > 0 else None
        return _safe_parse_uploaded(uploaded, cycle_override), None

    return _instance_editor_ui(), None


def _instance_editor_ui() -> Instance | None:
    st.write("Définissez vos tâches puis vos précédences.")
    n_tasks = st.number_input("Nombre de tâches", min_value=2, max_value=50, value=5, key="ed_n")

    default_durations = pd.DataFrame(
        {"Tâche": list(range(n_tasks)), "Durée": [3] * n_tasks}
    )
    edited = st.data_editor(
        default_durations,
        use_container_width=True,
        hide_index=True,
        disabled=["Tâche"],
        key="ed_durations",
    )
    durations: dict[int, int] = {}
    for _, row in edited.iterrows():
        try:
            durations[int(row["Tâche"])] = max(1, int(row["Durée"]))
        except (TypeError, ValueError):
            durations[int(row["Tâche"])] = 1

    raw_prec = st.text_area(
        "Précédences (une par ligne, format `i,j` signifiant i avant j)",
        value="0,1\n1,2\n2,3\n3,4",
        key="ed_prec",
    )
    raw_pairs: list[tuple[int, int]] = []
    for line in raw_prec.strip().splitlines():
        line = line.strip()
        if not line or "," not in line:
            continue
        a_str, b_str = line.split(",", 1)
        try:
            raw_pairs.append((int(a_str), int(b_str)))
        except ValueError:
            st.warning(f"Précédence ignorée (non numérique) : {line!r}")
            continue

    try:
        precedences, warnings = validate_precedences(n_tasks, raw_pairs)
    except InstanceValidationError as e:
        st.error(str(e))
        return None
    for w in warnings:
        st.warning(w)

    cycle = st.number_input(
        "Cycle time",
        min_value=1,
        value=max(durations.values()) if durations else 1,
        key="ed_cycle",
    )

    instance = Instance(
        name="custom",
        tasks=list(range(n_tasks)),
        durations=durations,
        precedences=precedences,
        cycle_time=cycle,
    )
    try:
        validate_instance(instance)
    except InstanceValidationError as e:
        st.error(str(e))
        return None
    return instance


def _show_instance_summary(instance: Instance, info: dict | None) -> None:
    st.subheader(f"Instance : {instance.name}")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.write(f"**Tâches** : {len(instance.tasks)}")
        st.write(f"**Précédences** : {len(instance.precedences)}")
        st.write(f"**Durée totale** : {sum(instance.durations.values())}")
        st.write(f"**Cycle time** : {instance.cycle_time}")
        if info and info.get("known_optimum") is not None:
            if info.get("valid_for_cycle"):
                st.success(f"**Optimum connu : {info['known_optimum']} stations** (cycle de référence)")
            else:
                st.info(
                    f"Optimum connu : {info['known_optimum']} stations "
                    f"pour cycle={info['default_cycle']} (non comparable au cycle actuel)"
                )
    with c2:
        if len(instance.tasks) <= 30:
            st.pyplot(draw_precedence_graph(instance))
        else:
            st.info("Graphe de précédence masqué (plus de 30 tâches).")


def page_single_solver() -> None:
    with st.sidebar:
        st.header("Instance")
        instance, info = load_instance_ui()
        if instance is None:
            st.stop()
        st.header("Solveur")
        solver_name = st.selectbox("Algorithme", SOLVER_NAMES)
        n_stations = st.number_input("Nombre de stations (SALBP-2)", min_value=1, value=6)
        time_limit = st.slider("Temps limite (s)", 1, 60, 15)
        run = st.button("Résoudre", type="primary", use_container_width=True)

    _show_instance_summary(instance, info)

    if run:
        with st.spinner(f"Résolution avec {solver_name}..."):
            sol = run_solver_single(solver_name, instance, n_stations, time_limit)
        if sol is None:
            st.error("Aucune solution trouvée.")
        else:
            st.subheader("Résultat")
            display_solution(sol, instance, key_prefix="single")


def page_compare() -> None:
    with st.sidebar:
        st.header("Instance")
        instance, info = load_instance_ui()
        if instance is None:
            st.stop()
        st.header("Paramètres")
        time_limit = st.slider("Temps limite par solveur (s)", 1, 60, 10)
        run = st.button("Comparer", type="primary", use_container_width=True)

    _show_instance_summary(instance, info)

    if run:
        results: dict[str, Solution | None] = {}
        with st.spinner("CP-SAT SALBP-1..."):
            results["CP-SAT"] = cpsat.solve_salbp1(instance, time_limit=time_limit)
        with st.spinner("PLNE..."):
            results["PLNE"] = plne.solve_salbp1(instance, time_limit=time_limit)
        with st.spinner("RPW..."):
            results["RPW"] = rpw.solve_salbp1(instance)

        rows = []
        for name, sol in results.items():
            if sol is None:
                rows.append({"Solveur": name, "Stations": "-", "Cycle": "-", "Optimal": "-", "Temps (ms)": "-"})
            else:
                rows.append(
                    {
                        "Solveur": name,
                        "Stations": sol.n_stations,
                        "Cycle": sol.cycle_time,
                        "Optimal": "Oui" if sol.optimal else "Non",
                        "Temps (ms)": f"{sol.time_ms:.1f}",
                    }
                )
        st.dataframe(rows, use_container_width=True, hide_index=True)

        cols = st.columns(len(results))
        for col, (name, sol) in zip(cols, results.items()):
            with col:
                st.markdown(f"### {name}")
                if sol is None:
                    st.warning("Aucune solution.")
                else:
                    st.pyplot(draw_gantt(sol, instance))


def page_benchmark() -> None:
    st.write("Lancement automatique des 3 solveurs sur les instances classiques de la bibliothèque.")
    with st.sidebar:
        st.header("Benchmark")
        selected = st.multiselect(
            "Instances à benchmarker",
            list_classics(),
            default=list_classics()[:4],
        )
        time_limit = st.slider("Temps limite par solveur (s)", 1, 60, 5)
        run = st.button("Lancer le benchmark", type="primary", use_container_width=True)

    if run and selected:
        instances_to_run = []
        for name in selected:
            meta = classic_metadata(name)
            instances_to_run.append((load_classic(name), meta["known_optimum"]))
        with st.spinner(f"Benchmark sur {len(instances_to_run)} instances..."):
            rows = run_benchmark(instances_to_run, time_limit_cpsat=time_limit, time_limit_plne=time_limit)
        st.subheader("Résultats")
        df = pd.DataFrame([r.to_dict() for r in rows])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "Télécharger les résultats (CSV)",
            df.to_csv(index=False).encode("utf-8"),
            file_name="benchmark_salbp.csv",
            mime="text/csv",
        )


def page_multimodel() -> None:
    st.write("Variante multi-modèles (MMALBP) : plusieurs produits partagent la même chaîne.")
    with st.sidebar:
        st.header("Instance multi-modèles")
        base: MultiModelInstance = two_model_toy()
        st.write(f"**Modèles** : {', '.join(base.models)}")
        st.write(f"**Tâches** : {len(base.tasks)}")
        cycle = st.number_input("Cycle time", min_value=1, value=base.cycle_time, key="mm_cycle")
        time_limit = st.slider("Temps limite (s)", 1, 60, 15)
        run = st.button("Résoudre MMALBP", type="primary", use_container_width=True)

    instance = dc_replace(base, cycle_time=cycle)
    st.subheader(f"Instance : {instance.name}")
    st.write(
        f"Cycle commun : **{cycle}** | Mix demande : "
        + ", ".join(f"{m}={instance.demand[m]:.0%}" for m in instance.models)
    )

    df_dur = pd.DataFrame(
        {m: [instance.durations[m][t] for t in instance.tasks] for m in instance.models},
        index=[f"T{t}" for t in instance.tasks],
    )
    st.dataframe(df_dur, use_container_width=True)

    if run:
        with st.spinner("Résolution MMALBP..."):
            sol = solve_mmalbp(instance, time_limit=time_limit)
        if sol is None:
            st.error("Pas de solution dans le temps imparti.")
            return
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Stations", sol.n_stations)
        c2.metric("Cycle imposé", sol.cycle_time)
        c3.metric("Optimal", "Oui" if sol.optimal else "Non")
        c4.metric("Temps", f"{sol.time_ms:.0f} ms")

        st.write("**Cycle atteint par modèle**")
        st.dataframe(
            [{"Modèle": m, "Cycle effectif": sol.cycle_per_model[m]} for m in instance.models],
            use_container_width=True,
            hide_index=True,
        )

        agg = to_aggregated_instance(instance, mode="max")
        solution_view = Solution(
            instance_name=sol.instance_name,
            solver="CP-SAT MMALBP",
            variant="MMALBP",
            assignment=sol.assignment,
            n_stations=sol.n_stations,
            cycle_time=max(sol.cycle_per_model.values()),
            optimal=sol.optimal,
            time_ms=sol.time_ms,
        )
        st.pyplot(draw_gantt(solution_view, agg))


PAGES = {
    "Solveur unique": page_single_solver,
    "Comparaison côte-à-côte": page_compare,
    "Benchmark classiques": page_benchmark,
    "Multi-modèles (MMALBP)": page_multimodel,
}

mode = st.sidebar.selectbox("Mode", list(PAGES.keys()))
st.sidebar.divider()
PAGES[mode]()
