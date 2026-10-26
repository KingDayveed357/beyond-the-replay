"""Investigation workflow: investigator -> sceptic -> verifier -> producer, over one shared board.

Mode "deterministic" uses the statistical investigator and the rule-based sceptic. When a model
deployment is configured, LLM agents replace those roles but keep the same tools, board,
verifier and grounding check; the UI always shows which mode produced a result. Both modes run as
one Microsoft Agent Framework workflow (investigation/orchestration.py).
"""
from __future__ import annotations

from phase0.observe import Case

# Fitted on Phase 0 development seeds 1-112 (results/phase0.json); never on held-out seeds.
DEFAULT_WEIGHTS = {"FATIGUE": 1.0, "OVERLOAD": 0.25, "STATIC": 0.5, "STYLE": 0.25, "FOUL": 0.25}


def investigate(case: Case, use_sceptic: bool = True, weights: dict | None = None, sceptic_mode: str = "refute") -> dict:
    """Statistics-only investigation, run as the same Microsoft Agent Framework workflow as the Claude agents."""
    from .orchestration import run
    return run(case, "deterministic", use_sceptic=use_sceptic, weights=weights or DEFAULT_WEIGHTS, sceptic_mode=sceptic_mode)
