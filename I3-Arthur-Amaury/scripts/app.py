import streamlit as st
import json
import pandas as pd
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cp_llm.llm_client import MistralClient
from cp_llm.runner import run_pipeline
from scripts.run_benchmark import load_reference

# Patch CpSolver globally for this process (essential for macOS stability)
try:
    from ortools.sat.python import cp_model
    _original_solve = cp_model.CpSolver.Solve
    def _patched_solve(self, model, solution_callback=None):
        self.parameters.num_search_workers = 1
        return _original_solve(self, model, solution_callback)
    cp_model.CpSolver.Solve = _patched_solve
except ImportError:
    pass

st.set_page_config(page_title="CP-LLM Demo", layout="wide")

st.title("🧩 Modélisation CP Assistée par LLM")

tab1, tab2 = st.tabs(["🚀 Live Run & Repair", "📊 Benchmark Dashboard"])

with tab1:
    st.header("Live Pipeline Execution")
    problems_dir = ROOT / "benchmark" / "problems"
    problems = (
        [p.stem for p in problems_dir.glob("*.txt")] if problems_dir.exists() else []
    )

    if not problems:
        st.warning("Aucun problème trouvé dans benchmark/problems/")
    else:
        selected_problem = st.selectbox("Sélectionnez un problème :", sorted(problems))

        if st.button("Lancer le pipeline"):
            try:
                from dotenv import load_dotenv

                load_dotenv(ROOT / ".env")
            except ImportError:
                pass

            client = MistralClient()
            problem_path = problems_dir / f"{selected_problem}.txt"
            st.info(f"Enoncé : {problem_path.read_text()}")

            with st.spinner("Exécution du pipeline (LLM + Vérification)..."):
                result = run_pipeline(client, problem_path)
            
            # Load reference for comparison
            with st.spinner("Exécution de la référence..."):
                reference, ref_exec_time = load_reference(selected_problem)

            if result.error_stage:
                st.error(f"Échec à l'étape : {result.error_stage}")
                st.code(result.error_message, language="text")
            else:
                st.success("Génération et vérification réussies !")

            # --- Reasoning Display ---
            st.subheader("🧠 Étapes de réflexion de l'LLM")
            
            with st.expander("1. Analyse du problème", expanded=False):
                st.write("**Raisonnement :**")
                st.write(result.analysis.reasoning)
                st.write("**Résumé :**", result.analysis.summary)
                st.write("**Paramètres extraits :**", result.analysis.parameters)

            with st.expander("2. Identification des variables", expanded=False):
                st.write("**Raisonnement :**")
                st.write(result.variables.reasoning)
                col_v1, col_v2 = st.columns(2)
                for i, v in enumerate(result.variables.variables):
                    with (col_v1 if i % 2 == 0 else col_v2):
                        st.markdown(f"- `{v.name}` ({v.var_type}): {v.description}")

            with st.expander("3. Extraction des contraintes", expanded=False):
                st.write("**Raisonnement :**")
                st.write(result.constraints.reasoning)
                for c in result.constraints.constraints:
                    st.markdown(f"- **{c.name}** : `{c.formula}` ({'Implicite' if c.is_implicit else 'Explicite'})")

            # --- Code & Execution Time ---
            st.subheader("💻 Code & Performance")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.write("**Code Généré :**")
                st.code(result.generated_code, language="python")
            
            with col2:
                st.write("**Temps d'exécution :**")
                
                exec_time = result.execution_time_s
                
                st.metric("LLM Generated", f"{exec_time:.4f} s" if exec_time is not None else "N/A")
                st.metric("Reference Code", f"{ref_exec_time:.4f} s" if ref_exec_time is not None else "N/A")
                
                if exec_time is not None and ref_exec_time is not None:
                    diff = exec_time - ref_exec_time
                    delta_color = "inverse" if diff > 0 else "normal"
                    st.metric("Différence", f"{diff:+.4f} s", delta=f"{diff:+.4f} s", delta_color=delta_color)
                
                if result.verification.get("result"):
                    st.write("**Résultat du solveur :**")
                    st.json(result.verification["result"])

with tab2:
    st.header("Benchmark Comparison")
    report_path = ROOT / "benchmark_report.json"
    if report_path.exists():
        data = json.loads(report_path.read_text())
        df = pd.DataFrame(data)

        cols_to_show = ["problem", "ok", "error_stage", "execution_time_s", "reference_execution_time_s", "execution_time_diff_s"]
        cols_to_show = [c for c in cols_to_show if c in df.columns]

        st.dataframe(df[cols_to_show])

        if "execution_time_s" in df.columns:
            st.subheader("Temps d'exécution (Generated vs Reference)")
            chart_data = df[df["ok"]].set_index("problem")[["execution_time_s", "reference_execution_time_s"]]
            st.bar_chart(chart_data)
        else:
            st.info(
                "Lancez `python scripts/run_benchmark.py` pour générer les temps d'exécution."
            )
    else:
        st.warning("Veuillez lancer `run_benchmark.py` pour générer le rapport JSON.")
