"""Etages LLM du pipeline d'explication : why_optimal, why_not, how_to_improve."""

from __future__ import annotations

import json

from cp_explainer.llm_client import LLMClient
from cp_explainer.prompts import HOW_TO_IMPROVE_SYSTEM, WHY_NOT_SYSTEM, WHY_OPTIMAL_SYSTEM
from cp_explainer.schemas import ExplanationOutput, SolverOutput


def _solution_summary(sol: SolverOutput) -> str:
    """Formate la solution en texte dense pour le prompt."""
    lines = [
        f"Probleme : {sol.problem_name} ({sol.problem_type})",
        f"Statut : {sol.status}",
        f"Objectif ({sol.objective_direction}) : {sol.objective_value}",
        "",
        "=== Variables de decision ===",
        json.dumps(sol.variables, ensure_ascii=False, indent=2),
        "",
        "=== Analyse des contraintes ===",
    ]
    for c in sol.constraint_analyses:
        binding_label = "ACTIVE (binding)" if c.is_binding else f"marge={c.slack}"
        lines.append(
            f"  [{binding_label}] {c.name}: {c.description} — {c.formula}"
        )

    if sol.sensitivity:
        lines.append("")
        lines.append("=== Analyse de sensibilite ===")
        for s in sol.sensitivity:
            lines.append(f"  {s.description}")

    if sol.notes:
        lines.append("")
        lines.append("=== Notes du solveur ===")
        for note in sol.notes:
            lines.append(f"  - {note}")

    return "\n".join(lines)


def explain_why_optimal(client: LLMClient, solution: SolverOutput) -> ExplanationOutput:
    """Genere une explication LLM : pourquoi cette solution est optimale."""
    summary = _solution_summary(solution)
    user_prompt = (
        f"Voici la solution CP-SAT trouvee :\n\n{summary}\n\n"
        "Explique pourquoi cette solution est optimale. "
        "Cite les contraintes actives et les trade-offs."
    )
    return client.call_structured(WHY_OPTIMAL_SYSTEM, user_prompt, ExplanationOutput)


def explain_why_not(client: LLMClient, solution: SolverOutput) -> ExplanationOutput:
    """Genere une explication LLM : pourquoi ne peut-on pas faire mieux ?"""
    summary = _solution_summary(solution)
    cf_lines = []
    if solution.counterfactuals:
        cf_lines.append("=== Analyses contrefactuelles (re-resolution avec decisions forcees) ===")
        for cf in solution.counterfactuals[:4]:
            cf_lines.append(
                f"  Si {cf.forced_change} : statut={cf.new_status}, "
                f"objectif={cf.new_objective} (delta={cf.delta:+.1f})" if cf.delta is not None
                else f"  Si {cf.forced_change} : {cf.explanation}"
            )
    cf_text = "\n".join(cf_lines) if cf_lines else "(Aucune analyse contrefactuelle disponible.)"

    user_prompt = (
        f"Voici la solution CP-SAT optimale :\n\n{summary}\n\n"
        f"{cf_text}\n\n"
        "Explique pourquoi on ne peut pas faire mieux : "
        "quelles contraintes bloquent les alternatives ? "
        "Utilise les analyses contrefactuelles pour justifier."
    )
    return client.call_structured(WHY_NOT_SYSTEM, user_prompt, ExplanationOutput)


def explain_how_to_improve(client: LLMClient, solution: SolverOutput) -> ExplanationOutput:
    """Genere une explication LLM : comment ameliorer la solution en relachant des contraintes."""
    summary = _solution_summary(solution)
    binding_names = [c.name for c in solution.constraint_analyses if c.is_binding]
    binding_text = (
        f"Contraintes actives (binding) : {', '.join(binding_names)}"
        if binding_names else "Aucune contrainte strictement active."
    )

    sens_text = ""
    if solution.sensitivity:
        sens_lines = ["=== Impact de l'assouplissement des contraintes ==="]
        for s in solution.sensitivity:
            sens_lines.append(f"  - {s.description}")
        sens_text = "\n".join(sens_lines)
    else:
        sens_text = "(Aucune analyse de sensibilite disponible.)"

    user_prompt = (
        f"Voici la solution CP-SAT :\n\n{summary}\n\n"
        f"{binding_text}\n\n{sens_text}\n\n"
        "Quels assouplissements de contraintes permettraient d'ameliorer l'objectif ? "
        "Classe-les par impact decroissant et sois precis sur les montants."
    )
    return client.call_structured(HOW_TO_IMPROVE_SYSTEM, user_prompt, ExplanationOutput)


# ---------------------------------------------------------------------------
# Template-based explanations (sans LLM, pour comparaison)
# ---------------------------------------------------------------------------

def template_why_optimal(solution: SolverOutput) -> str:
    """Explication template (sans LLM) : pourquoi optimal ?"""
    binding = [c for c in solution.constraint_analyses if c.is_binding]
    non_binding = [c for c in solution.constraint_analyses if not c.is_binding]
    lines = [
        f"La solution optimale obtient un objectif de {solution.objective_value} "
        f"(direction : {solution.objective_direction}).",
        "",
    ]
    if binding:
        names = ", ".join(c.name for c in binding)
        lines.append(f"Contraintes actives (limitantes) : {names}.")
        for c in binding:
            lines.append(f"  • {c.description} : {c.formula}. Impossible de faire mieux sans relacher cette contrainte.")
    else:
        lines.append("Aucune contrainte n'est strictement active.")
    if non_binding:
        lines.append("")
        lines.append("Contraintes avec marge :")
        for c in non_binding:
            if c.slack is not None:
                lines.append(f"  • {c.description} : marge = {c.slack}.")
    if solution.notes:
        lines.append("")
        lines.extend(solution.notes)
    return "\n".join(lines)


def template_why_not(solution: SolverOutput) -> str:
    """Explication template (sans LLM) : pourquoi pas mieux ?"""
    lines = [
        f"La valeur optimale de {solution.objective_value} ne peut pas etre depassee car :",
        "",
    ]
    binding = [c for c in solution.constraint_analyses if c.is_binding]
    if binding:
        for c in binding:
            lines.append(f"  • La contrainte '{c.name}' est active : {c.formula}.")
            lines.append(f"    Toute amelioration necessite de relacher cette contrainte.")
    if solution.counterfactuals:
        lines.append("")
        lines.append("Analyses contrefactuelles :")
        for cf in solution.counterfactuals[:3]:
            lines.append(f"  • {cf.explanation}")
    return "\n".join(lines)


def template_how_to_improve(solution: SolverOutput) -> str:
    """Explication template (sans LLM) : comment ameliorer ?"""
    lines = ["Pour ameliorer la solution, on peut relacher les contraintes suivantes :", ""]
    if solution.sensitivity:
        for s in sorted(solution.sensitivity, key=lambda x: abs(x.improvement or 0), reverse=True):
            lines.append(f"  • {s.description}")
    else:
        binding = [c for c in solution.constraint_analyses if c.is_binding]
        if binding:
            for c in binding:
                lines.append(f"  • Relacher '{c.name}' : {c.description}")
        else:
            lines.append("  • Aucune recommandation disponible (pas d'analyse de sensibilite).")
    return "\n".join(lines)
