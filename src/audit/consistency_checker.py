"""
Layer 5: R1 → R2 consistency checker.

For each module that has both a Round 1 and Round 2 output, asks the LLM to
identify any specific statistics, numbers, dates, or factual claims that appear
in Round 2 but have no basis in Round 1.  These are cross-module amplification
candidates: the module may have treated another module's hallucination as fact.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from src.models.schemas import FinalAnalysis, ModuleOutput
from src.llm.client import ClaudeClient


def _summarise_output(mo: ModuleOutput) -> str:
    parts = []
    if isinstance(mo.analysis, dict):
        for k, v in mo.analysis.items():
            parts.append(f"{k}: {v}")
    else:
        parts.append(str(mo.analysis))
    parts.extend(mo.flags)
    return "\n".join(parts)


def _check_module(client: ClaudeClient, module: str,
                  r1: ModuleOutput, r2: ModuleOutput) -> List[str]:
    system = (
        "You are a consistency auditor for multi-round LLM analyses. "
        "Compare the Round 1 and Round 2 outputs from the same module. "
        "Identify any specific statistics, numbers, percentages, dates, named "
        "organisations, or concrete factual claims that appear in Round 2 but "
        "have NO basis in Round 1. Do not flag opinions, interpretations, or "
        "inferences — only newly introduced concrete facts. "
        "Return a JSON object: {\"inconsistencies\": [\"...\", ...]}. "
        "Return {\"inconsistencies\": []} if Round 2 is fully consistent."
    )
    user = (
        f"Module: {module}\n\n"
        f"=== Round 1 ===\n{_summarise_output(r1)}\n\n"
        f"=== Round 2 ===\n{_summarise_output(r2)}"
    )
    try:
        result = client.analyze(system, user)
        if isinstance(result, dict):
            return result.get("inconsistencies", [])
        return []
    except Exception as e:
        return [f"Error: {e}"]


def check_consistency(
    analysis: FinalAnalysis,
    client: Optional[ClaudeClient] = None,
    max_workers: int = 5,
) -> List[Dict]:
    """
    Returns list of {module, issues, ok} dicts for every module with R1+R2 outputs.
    """
    if client is None:
        client = ClaudeClient(model="claude-haiku-4-5-20251001")

    # Group by module name
    by_module: Dict[str, Dict[int, ModuleOutput]] = {}
    for mo in analysis.module_outputs:
        by_module.setdefault(mo.module_name, {})[mo.round] = mo

    # Only check modules that have both rounds
    pairs = {
        name: rounds
        for name, rounds in by_module.items()
        if 1 in rounds and 2 in rounds
    }

    if not pairs:
        return []

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {
            ex.submit(_check_module, client, name, rounds[1], rounds[2]): name
            for name, rounds in pairs.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            issues = future.result()
            results.append({"module": name, "issues": issues, "ok": not issues})

    results.sort(key=lambda r: r["module"])
    return results


def main(args: List[str] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Check for new facts introduced in R2 that have no basis in R1"
    )
    parser.add_argument("report", help="Path to report.json")
    parsed = parser.parse_args(args)

    with open(parsed.report) as f:
        analysis = FinalAnalysis(**json.load(f))

    print("Checking R1 → R2 consistency...")
    results = check_consistency(analysis)

    if not results:
        print("No module pairs with both rounds found.")
        return 0

    ok = [r for r in results if r["ok"]]
    failures = [r for r in results if not r["ok"]]

    print(f"Consistent: {len(ok)}/{len(results)} modules")

    if failures:
        print("\nINCONSISTENCIES FOUND:")
        for r in failures:
            print(f"\n  [{r['module']}]")
            for issue in r["issues"]:
                print(f"    ✗ {issue}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
