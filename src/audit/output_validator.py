"""
Layer 2: Output integrity validator.

Validates a FinalAnalysis object (or report.json file) for citation integrity:
  - All sources have real URLs
  - No [N] markers reference an out-of-range source index
  - No citations present when search was disabled
  - Resolution sources also have URLs
"""
import json
import re
import sys
from typing import List

from src.models.schemas import FinalAnalysis


def validate(analysis: FinalAnalysis) -> List[str]:
    """Return a list of violation strings. Empty list = clean."""
    violations: List[str] = []

    # 1. Every source must contain an https:// URL
    for i, source in enumerate(analysis.sources, 1):
        if "https://" not in source:
            violations.append(f"Source [{i}] has no URL: {source!r}")

    # 2. Collect all [N] markers across all text
    all_text = _collect_all_text(analysis)
    cited_indices = {int(m) for m in re.findall(r'\[(\d+)\]', all_text)}
    valid_range = set(range(1, len(analysis.sources) + 1))

    orphans = cited_indices - valid_range
    if orphans:
        violations.append(
            f"Orphaned citations with no source entry: {sorted(orphans)}"
        )

    # 3. No citations when search was disabled
    if not analysis.search_enabled and cited_indices:
        violations.append(
            f"Citations {sorted(cited_indices)} present but search_enabled=False"
        )

    # 4. Deep research resolution sources must also have URLs
    for res in analysis.conflict_resolutions:
        for source in res.sources:
            if "https://" not in source:
                violations.append(
                    f"Resolution source for '{res.topic}' has no URL: {source!r}"
                )

    return violations


def _collect_all_text(analysis: FinalAnalysis) -> str:
    parts = [analysis.synthesis, analysis.deactivated_disclaimer]
    parts.extend(analysis.recommendations)
    parts.extend(analysis.priority_flags)
    for mo in analysis.module_outputs:
        if isinstance(mo.analysis, dict):
            parts.append(json.dumps(mo.analysis))
        else:
            parts.append(str(mo.analysis))
        parts.extend(mo.flags)
    for res in analysis.conflict_resolutions:
        parts.append(res.verdict)
        parts.append(res.updated_recommendation)
    return " ".join(parts)


def validate_file(path: str) -> List[str]:
    with open(path) as f:
        data = json.load(f)
    return validate(FinalAnalysis(**data))


def main(args: List[str] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Validate report.json citation integrity")
    parser.add_argument("report", help="Path to report.json")
    parsed = parser.parse_args(args)

    violations = validate_file(parsed.report)
    if violations:
        print("OUTPUT VALIDATOR — FAILURES:")
        for v in violations:
            print(f"  ✗ {v}")
        return 1
    print("Output validator: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
