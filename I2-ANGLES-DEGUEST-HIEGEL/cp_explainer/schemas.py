"""Schemas Pydantic pour le pipeline d'explication de solutions CP-SAT."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ConstraintAnalysis(BaseModel):
    """Analyse d'une contrainte du modele sur la solution courante."""

    name: str = Field(description="Identifiant court de la contrainte.")
    description: str = Field(description="Description en langage naturel.")
    formula: str = Field(description="Expression evaluee (ex: 'sum(weights * take) <= 50').")
    lhs_value: Optional[float] = Field(
        description="Valeur du membre gauche sur la solution."
    )
    rhs_value: Optional[float] = Field(
        description="Borne droite de la contrainte (si applicable)."
    )
    slack: Optional[float] = Field(
        description="Marge disponible = rhs - lhs. 0 si contrainte active (binding)."
    )
    is_binding: bool = Field(
        description="True si la contrainte est active (slack == 0)."
    )


class SensitivityEntry(BaseModel):
    """Effet de relacher une contrainte binding d'un certain montant."""

    constraint_name: str
    relaxation_amount: float = Field(
        description="De combien la borne a ete assouplie."
    )
    original_objective: float
    new_objective: Optional[float] = Field(
        description="Valeur de l'objectif apres relachement. None si infaisable."
    )
    improvement: Optional[float] = Field(
        description="new_objective - original_objective (positif = amelioration)."
    )
    description: str = Field(
        description="Resume de l'effet en une phrase."
    )


class CounterfactualEntry(BaseModel):
    """Analyse contrefactuelle : que se passe-t-il si on force une decision differente ?"""

    description: str = Field(description="Ce qu'on a force (ex: 'item 3 inclus').")
    forced_change: str
    new_status: str = Field(description="OPTIMAL, FEASIBLE, INFEASIBLE...")
    new_objective: Optional[float]
    delta: Optional[float] = Field(
        description="Variation d'objectif par rapport a la solution originale."
    )
    explanation: str = Field(description="Pourquoi ce resultat ?")


class SolverOutput(BaseModel):
    """Sortie brute d'un solveur CP-SAT avant analyse."""

    problem_name: str
    problem_type: str
    parameters: dict[str, Any]
    status: str
    objective_value: Optional[float]
    objective_direction: Optional[Literal["minimize", "maximize"]]
    variables: dict[str, Any]
    constraint_analyses: list[ConstraintAnalysis]
    sensitivity: list[SensitivityEntry]
    counterfactuals: list[CounterfactualEntry]
    notes: list[str] = Field(default_factory=list)


class ExplanationOutput(BaseModel):
    """Explication LLM d'un aspect de la solution CP."""

    reasoning: str = Field(
        description=(
            "Reflexion pas a pas sur les faits cles avant de rediger l'explication. "
            "Identifier les contraintes actives, les marges, les echanges (trade-offs)."
        )
    )
    main_explanation: str = Field(
        description="Explication principale en langage naturel, claire et pedagogique."
    )
    key_points: list[str] = Field(
        description="2 a 4 points cles sous forme de liste de phrases courtes."
    )
    binding_constraints_cited: list[str] = Field(
        description="Noms des contraintes actives (binding) mentionnees dans l'explication."
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description=(
            "'high' si tous les faits sont clairs et l'explication est certaine. "
            "'medium' si quelques hypotheses ont ete faites. "
            "'low' si l'analyse est partielle ou incertaine."
        )
    )


class ExplainerResult(BaseModel):
    """Resultat complet du pipeline d'explication."""

    problem_name: str
    solution: SolverOutput
    why_optimal: Optional[ExplanationOutput] = None
    why_not: Optional[ExplanationOutput] = None
    how_to_improve: Optional[ExplanationOutput] = None
    template_why_optimal: Optional[str] = None
    template_why_not: Optional[str] = None
    template_how_to_improve: Optional[str] = None
    execution_time_s: Optional[float] = None
    error: Optional[str] = None
    error_stage: Optional[str] = None
