"""Pipeline d'explication sur un probleme unique."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from cp_explainer.cache import CachedLLMClient  # noqa: E402
from cp_explainer.llm_client import AnthropicClient, LLMClient, MistralClient  # noqa: E402
from cp_explainer.runner import run_explainer, run_template_only  # noqa: E402

CACHE_DIR = ROOT / ".cache" / "llm"


def _default_provider() -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("MISTRAL_API_KEY"):
        return "mistral"
    return "anthropic"


def build_client(provider: str, model: str | None, use_cache: bool) -> LLMClient:
    if provider == "anthropic":
        inner: LLMClient = AnthropicClient(model=model)
    elif provider == "mistral":
        inner = MistralClient(model=model)
    else:
        raise ValueError(f"Provider inconnu : {provider}")
    if use_cache:
        return CachedLLMClient(inner, CACHE_DIR)
    return inner


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("problem", type=Path,
                        help="Chemin vers le fichier JSON du probleme.")
    parser.add_argument("--provider", default=_default_provider(),
                        choices=["anthropic", "mistral"],
                        help="LLM a utiliser (auto-detecte depuis les variables d'env).")
    parser.add_argument("--model", default=None,
                        help="Override du modele LLM.")
    parser.add_argument("--no-cache", action="store_true",
                        help="Desactive le cache disque.")
    parser.add_argument("--template-only", action="store_true",
                        help="Explications template uniquement, sans appel LLM.")
    parser.add_argument("--save", type=Path, default=None,
                        help="Sauvegarder le resultat JSON a ce chemin.")
    args = parser.parse_args()

    if args.template_only:
        result = run_template_only(args.problem)
        print(f"=== Explicateur CP (mode template) — {args.problem} ===\n")
    else:
        client = build_client(args.provider, args.model, not args.no_cache)
        print(f"=== Explicateur CP — {args.problem} ===\n")
        result = run_explainer(client, args.problem)

    print(f"Probleme : {result.problem_name}")
    if result.solution:
        print(f"Statut solveur : {result.solution.status}")
        print(f"Objectif : {result.solution.objective_value} ({result.solution.objective_direction})")
        binding = [c.name for c in result.solution.constraint_analyses if c.is_binding]
        print(f"Contraintes actives : {binding or 'aucune'}")
    print()

    if result.why_optimal:
        print("--- POURQUOI CETTE SOLUTION EST OPTIMALE (LLM) ---")
        print(result.why_optimal.main_explanation)
        print()
        for pt in result.why_optimal.key_points:
            print(f"  • {pt}")
        print()
    elif result.template_why_optimal:
        print("--- POURQUOI CETTE SOLUTION EST OPTIMALE (template) ---")
        print(result.template_why_optimal)
        print()

    if result.why_not:
        print("--- POURQUOI NE PEUT-ON PAS FAIRE MIEUX (LLM) ---")
        print(result.why_not.main_explanation)
        print()
        for pt in result.why_not.key_points:
            print(f"  • {pt}")
        print()
    elif result.template_why_not:
        print("--- POURQUOI NE PEUT-ON PAS FAIRE MIEUX (template) ---")
        print(result.template_why_not)
        print()

    if result.how_to_improve:
        print("--- COMMENT AMELIORER LA SOLUTION (LLM) ---")
        print(result.how_to_improve.main_explanation)
        print()
        for pt in result.how_to_improve.key_points:
            print(f"  • {pt}")
        print()
    elif result.template_how_to_improve:
        print("--- COMMENT AMELIORER LA SOLUTION (template) ---")
        print(result.template_how_to_improve)
        print()

    if result.error:
        print(f"ERREUR a l'etape '{result.error_stage}' : {result.error}", file=sys.stderr)

    print(f"Temps d'execution : {result.execution_time_s}s")

    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        print(f"Resultat sauvegarde dans : {args.save}")

    return 0 if not result.error else 1


if __name__ == "__main__":
    sys.exit(main())
