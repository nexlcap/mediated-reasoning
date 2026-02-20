"""
Lightweight run quality gate — no LLM calls, pure metrics.

Computes a score from structural signals already present in FinalAnalysis
(source survival, module failures, critical flag density) and returns a
RunQuality object attached to the analysis before it reaches the user.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.models.schemas import FinalAnalysis, RunQuality


def evaluate(analysis: "FinalAnalysis") -> "RunQuality":
    """Score a completed analysis run and return a RunQuality signal."""
    from src.models.schemas import RunQuality

    score = 1.0
    warnings: List[str] = []

    # --- Module failures -------------------------------------------------
    failed = analysis.modules_attempted - analysis.modules_completed
    if failed > 0:
        score -= 0.3 * failed
        warnings.append(
            f"{failed} module(s) failed — analysis is incomplete"
        )

    # --- Source grounding ------------------------------------------------
    sources_survived = len(analysis.sources)
    sources_claimed = analysis.sources_claimed

    if analysis.search_enabled:
        if sources_claimed > 0:
            survival = sources_survived / sources_claimed
            if survival < 0.5:
                score -= 0.3
                warnings.append(
                    f"Low source survival ({survival:.0%}) — most claimed sources had no real URL"
                )
            elif survival < 0.7:
                score -= 0.1
                warnings.append(
                    f"Moderate source survival ({survival:.0%}) — some sources may be hallucinated"
                )

        if sources_survived < 5:
            score -= 0.2
            warnings.append(
                f"Only {sources_survived} source(s) survived URL validation — "
                "analysis may be undergrounded"
            )

    # --- Critical flag density -------------------------------------------
    flags_red = sum(
        1 for f in analysis.priority_flags if f.lower().startswith("red:")
    )
    if flags_red >= 4:
        score -= 0.1
        warnings.append(
            f"{flags_red} critical flags identified — consider --deep-research "
            "for evidence-based resolution"
        )

    # --- Tier ------------------------------------------------------------
    # Round before tier comparison to avoid IEEE754 boundary errors
    # (e.g. 1.0 - 0.3 - 0.2 = 0.4999… rather than 0.5 in float64).
    score = round(max(0.0, min(1.0, score)), 2)
    if score >= 0.8:
        tier = "good"
    elif score >= 0.5:
        tier = "degraded"
    else:
        tier = "poor"

    return RunQuality(score=score, tier=tier, warnings=warnings)
