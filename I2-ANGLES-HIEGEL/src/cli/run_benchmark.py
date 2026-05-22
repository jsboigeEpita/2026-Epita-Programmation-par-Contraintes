"""Benchmark complet : lance le pipeline sur tous les problemes et produit un rapport JSON."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from cp_explainer.llm.cache import CachedLLMClient  # noqa: E402
from cp_explainer.llm.llm_client import AnthropicClient, LLMClient, MistralClient  # noqa: E402
from cp_explainer.pipeline.runner import run_explainer  # noqa: E402

PROBLEMS_DIR = SRC / "data"
CACHE_DIR = ROOT / ".cache" / "llm"
REPORT_PATH = ROOT / "benchmark" / "benchmark_report.json"


def _default_provider() -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("MISTRAL_API_KEY"):
        return "mistral"
    return "anthropic"


def _build_client(provider: str, no_cache: bool) -> LLMClient:
    inner: LLMClient = AnthropicClient() if provider == "anthropic" else MistralClient()
    return inner if no_cache else CachedLLMClient(inner, CACHE_DIR)


def _explanation_facts_cited(explanation, constraint_analyses) -> float:
    """Taux de contraintes actives mentionnees dans l'explication."""
    binding_names = {c.name for c in constraint_analyses if c.is_binding}
    if not binding_names or explanation is None:
        return 1.0
    cited = set(explanation.binding_constraints_cited)
    return len(cited & binding_names) / len(binding_names)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default=_default_provider(),
                        choices=["anthropic", "mistral"],
                        help="LLM a utiliser (auto-detecte depuis les variables d'env).")
    parser.add_argument("--model", default=None, help="Override du modele LLM.")
    parser.add_argument("--no-cache", action="store_true", help="Desactive le cache disque.")
    parser.add_argument("--report", type=Path, default=REPORT_PATH,
                        help="Chemin du rapport JSON de sortie.")
    args = parser.parse_args()

    client = _build_client(args.provider, args.no_cache)
    print(f"Provider : {args.provider}")
    problems = sorted(PROBLEMS_DIR.glob("*.json"))

    if not problems:
        print(f"Aucun probleme trouve dans {PROBLEMS_DIR}", file=sys.stderr)
        sys.exit(1)

    report = []
    for prob_path in problems:
        print(f"[{prob_path.stem}] ... ", end="", flush=True)
        t0 = time.perf_counter()
        result = run_explainer(client, prob_path)
        elapsed = time.perf_counter() - t0

        row: dict = {
            "problem": result.problem_name,
            "status": result.solution.status if result.solution else "ERROR",
            "objective": result.solution.objective_value if result.solution else None,
            "ok": result.error is None,
            "error_stage": result.error_stage,
            "execution_time_s": round(elapsed, 2),
            "binding_constraints": (
                [c.name for c in result.solution.constraint_analyses if c.is_binding]
                if result.solution else []
            ),
        }

        # Metriques de qualite des explications
        if result.solution and result.why_optimal:
            row["why_optimal_coverage"] = round(
                _explanation_facts_cited(result.why_optimal, result.solution.constraint_analyses), 2
            )
            row["why_optimal_key_points"] = len(result.why_optimal.key_points)
            row["why_optimal_confidence"] = result.why_optimal.confidence
        if result.solution and result.why_not:
            row["why_not_coverage"] = round(
                _explanation_facts_cited(result.why_not, result.solution.constraint_analyses), 2
            )
        if result.solution and result.how_to_improve:
            row["n_improvements"] = len(result.solution.sensitivity)

        report.append(row)
        status_icon = "✓" if row["ok"] else f"✗ ({result.error_stage})"
        print(status_icon)

    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRapport sauvegarde dans {args.report}")
    ok_count = sum(1 for r in report if r["ok"])
    print(f"Succes : {ok_count}/{len(report)}")


if __name__ == "__main__":
    main()
