"""Dashboard Streamlit — Explicateur de solutions CP par LLM."""

import json
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from cp_explainer.llm.cache import CachedLLMClient
from cp_explainer.llm.llm_client import AnthropicClient, MistralClient
from cp_explainer.pipeline.runner import run_explainer
from cp_explainer.llm import prompts as cp_prompts

CACHE_DIR = ROOT / ".cache" / "llm"
PROBLEMS_DIR = SRC / "data"

st.set_page_config(page_title="CP Explainer", layout="wide")
st.title("🔍 Explicateur de solutions CP par LLM")

# Sidebar : choix du provider LLM
_has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
_has_mistral = bool(os.environ.get("MISTRAL_API_KEY"))
_available = [p for p, ok in [("mistral", _has_mistral), ("anthropic", _has_anthropic)] if ok]
if not _available:
    _available = ["anthropic", "mistral"]
with st.sidebar:
    st.header("Configuration LLM")
    _provider = st.selectbox("Provider", _available, index=0)
    _use_cache = st.checkbox("Utiliser le cache disque", value=True)


def _build_client():
    if _provider == "mistral":
        inner = MistralClient()
    else:
        inner = AnthropicClient()
    if _use_cache:
        return CachedLLMClient(inner, CACHE_DIR)
    return inner


tab1, tab2, tab3 = st.tabs([
    "🚀 Explorer une solution",
    "📊 Benchmark",
    "📜 Prompts",
])

# ---------------------------------------------------------------------------
# Tab 1 : Live exploration
# ---------------------------------------------------------------------------
with tab1:
    st.header("Explorer et expliquer une solution CP-SAT")

    problems = sorted(p.stem for p in PROBLEMS_DIR.glob("*.json")) if PROBLEMS_DIR.exists() else []
    if not problems:
        st.warning(f"Aucun problème trouvé dans {PROBLEMS_DIR}")
    else:
        selected = st.selectbox("Sélectionnez un problème :", problems)

        if st.button("Résoudre et expliquer"):
            prob_path = PROBLEMS_DIR / f"{selected}.json"
            prob_data = json.loads(prob_path.read_text())
            st.info(f"**{prob_data.get('description', selected)}**")

            client = _build_client()

            with st.spinner("Résolution CP-SAT + génération des explications…"):
                result = run_explainer(client, prob_path)

            if result.error:
                st.error(f"Erreur à l'étape **{result.error_stage}** : {result.error}")
            else:
                st.success(f"✅ Solution trouvée en {result.execution_time_s}s")

            # Solution
            if result.solution:
                sol = result.solution
                col1, col2, col3 = st.columns(3)
                col1.metric("Statut", sol.status)
                col2.metric(f"Objectif ({sol.objective_direction})", sol.objective_value)
                binding = [c.name for c in sol.constraint_analyses if c.is_binding]
                col3.metric("Contraintes actives", len(binding))

                with st.expander("📦 Variables de décision", expanded=True):
                    st.json(sol.variables)

                with st.expander("⚖️ Analyse des contraintes"):
                    df_c = pd.DataFrame([
                        {
                            "Contrainte": c.name,
                            "Description": c.description,
                            "Active ?": "🔴 OUI" if c.is_binding else "🟢 non",
                            "Marge (slack)": c.slack,
                            "Formule": c.formula,
                        }
                        for c in sol.constraint_analyses
                    ])
                    st.dataframe(df_c, use_container_width=True)

                if sol.sensitivity:
                    with st.expander("📈 Analyse de sensibilité"):
                        df_s = pd.DataFrame([
                            {
                                "Contrainte": s.constraint_name,
                                "Assouplissement": s.relaxation_amount,
                                "Objectif original": s.original_objective,
                                "Nouvel objectif": s.new_objective,
                                "Amélioration": s.improvement,
                                "Description": s.description,
                            }
                            for s in sol.sensitivity
                        ])
                        st.dataframe(df_s, use_container_width=True)

            # Explications LLM vs Template
            st.subheader("💬 Explications")
            exp_types = {
                "Pourquoi cette solution est-elle optimale ?": (
                    result.why_optimal, result.template_why_optimal
                ),
                "Pourquoi ne peut-on pas faire mieux ?": (
                    result.why_not, result.template_why_not
                ),
                "Comment améliorer la solution ?": (
                    result.how_to_improve, result.template_how_to_improve
                ),
            }

            for label, (llm_expl, tmpl_expl) in exp_types.items():
                with st.expander(label, expanded=True):
                    col_llm, col_tmpl = st.columns(2)
                    with col_llm:
                        st.caption(f"🤖 Explication LLM ({_provider.capitalize()})")
                        if llm_expl:
                            st.write(llm_expl.main_explanation)
                            if llm_expl.key_points:
                                st.markdown("**Points clés :**")
                                for pt in llm_expl.key_points:
                                    st.markdown(f"- {pt}")
                            conf_color = {"high": "🟢", "medium": "🟡", "low": "🔴"}
                            st.caption(
                                f"{conf_color.get(llm_expl.confidence, '')} "
                                f"Confiance : {llm_expl.confidence}"
                            )
                        else:
                            st.warning("Non disponible (erreur pipeline).")
                    with col_tmpl:
                        st.caption("📝 Explication template (sans LLM)")
                        if tmpl_expl:
                            st.text(tmpl_expl)
                        else:
                            st.warning("Non disponible.")

            if result.solution and result.solution.counterfactuals:
                with st.expander("🔄 Analyses contrefactuelles"):
                    df_cf = pd.DataFrame([
                        {
                            "Scénario": cf.description,
                            "Statut": cf.new_status,
                            "Nouvel objectif": cf.new_objective,
                            "Delta": f"{cf.delta:+.1f}" if cf.delta is not None else "N/A",
                            "Explication": cf.explanation,
                        }
                        for cf in result.solution.counterfactuals
                    ])
                    st.dataframe(df_cf, use_container_width=True)

# ---------------------------------------------------------------------------
# Tab 2 : Benchmark
# ---------------------------------------------------------------------------
with tab2:
    st.header("Résultats du benchmark")
    report_path = ROOT / "benchmark" / "benchmark_report.json"

    if not report_path.exists():
        st.warning(
            "Aucun rapport trouvé. Lancez d'abord :\n"
            "```bash\npython scripts/run_benchmark.py\n```"
        )
    else:
        data = json.loads(report_path.read_text())
        df = pd.DataFrame(data)

        ok_count = df["ok"].sum() if "ok" in df.columns else 0
        st.metric("Problèmes résolus avec succès", f"{ok_count}/{len(df)}")

        cols_to_show = [c for c in [
            "problem", "status", "objective", "ok", "error_stage",
            "execution_time_s", "binding_constraints",
            "why_optimal_coverage", "why_optimal_confidence",
        ] if c in df.columns]
        st.dataframe(df[cols_to_show], use_container_width=True)

        if "execution_time_s" in df.columns:
            st.subheader("Temps d'exécution par problème")
            st.bar_chart(df.set_index("problem")["execution_time_s"])

        if "why_optimal_coverage" in df.columns:
            st.subheader("Couverture des contraintes actives dans les explications LLM")
            chart_data = df.dropna(subset=["why_optimal_coverage"]).set_index("problem")["why_optimal_coverage"]
            st.bar_chart(chart_data)

# ---------------------------------------------------------------------------
# Tab 3 : Prompts
# ---------------------------------------------------------------------------
with tab3:
    st.header("Prompts envoyés au LLM")
    st.markdown(
        "Le pipeline génère **3 types d'explications**, chacun piloté par un *system prompt* dédié. "
        "Le *user prompt* contient la solution CP-SAT, l'analyse des contraintes et les données de sensibilité."
    )

    stages = [
        ("1️⃣ Pourquoi cette solution est-elle optimale ?", cp_prompts.WHY_OPTIMAL_SYSTEM),
        ("2️⃣ Pourquoi ne peut-on pas faire mieux ?", cp_prompts.WHY_NOT_SYSTEM),
        ("3️⃣ Comment améliorer la solution ?", cp_prompts.HOW_TO_IMPROVE_SYSTEM),
    ]
    for label, prompt in stages:
        with st.expander(label, expanded=False):
            st.code(prompt, language="markdown")

    st.divider()
    st.subheader("Structure du schéma de réponse (ExplanationOutput)")
    st.markdown("""
    Chaque explication LLM suit ce schéma Pydantic :
    - `reasoning` : réflexion pas à pas du LLM avant de rédiger
    - `main_explanation` : texte principal, 3–5 phrases
    - `key_points` : liste de 2–4 points clés
    - `binding_constraints_cited` : noms des contraintes actives mentionnées
    - `confidence` : `high` / `medium` / `low`
    """)
