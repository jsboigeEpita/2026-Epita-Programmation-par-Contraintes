"""Point d'entrée rétrocompatible — délègue à cp_explainer.core.solvers."""

from cp_explainer.core.solvers import SOLVERS, solve

__all__ = ["SOLVERS", "solve"]
