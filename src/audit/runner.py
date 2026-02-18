"""
Fast audit runner — layers 1–3, no LLM calls.

Runs automatically after every analysis and attaches results to FinalAnalysis.
Layers 4–5 (LLM-based) remain on-demand via `python -m src.audit`.
"""
from src.models.schemas import AuditSummary, FinalAnalysis, UrlCheckResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run_fast_audit(analysis: FinalAnalysis) -> AuditSummary:
    """Run layers 1–3 and return an AuditSummary."""
    from src.audit.prompt_linter import lint
    from src.audit.output_validator import validate
    from src.audit.url_checker import check_urls, _extract_urls

    # Layer 1: static prompt constraint check
    logger.info("Audit layer 1: prompt linter")
    l1_violations = lint()

    # Layer 2: citation integrity
    logger.info("Audit layer 2: output integrity")
    l2_violations = validate(analysis)

    # Layer 3: URL reachability
    urls = _extract_urls(analysis)
    l3_results = []
    if urls:
        logger.info("Audit layer 3: checking %d URLs", len(urls))
        l3_results = check_urls(analysis)

    l3_ok = [r for r in l3_results if r["ok"]]
    l3_failures = [r for r in l3_results if not r["ok"]]

    return AuditSummary(
        layer1_passed=not l1_violations,
        layer1_violations=l1_violations,
        layer2_passed=not l2_violations,
        layer2_violations=l2_violations,
        layer3_total=len(l3_results),
        layer3_ok=len(l3_ok),
        layer3_failures=[
            UrlCheckResult(url=r["url"], status=r["status"], error=r["error"], ok=r["ok"])
            for r in l3_failures
        ],
    )
