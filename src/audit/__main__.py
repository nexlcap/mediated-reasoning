"""
On-demand audit runner.

Usage:
  python -m src.audit <report.json> --layer 2
  python -m src.audit <report.json> --layer 3
  python -m src.audit <report.json> --layer 4 [--sample-rate 0.2]
  python -m src.audit <report.json> --layer 5
  python -m src.audit <report.json> --all

Layer 1 (prompt linter) can also be run directly without a report file:
  python -m src.audit.prompt_linter
"""
import argparse
import json
import sys

from dotenv import load_dotenv
load_dotenv()

from src.models.schemas import FinalAnalysis


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.audit",
        description="Hallucination audit for mediated reasoning reports",
    )
    parser.add_argument("report", nargs="?", help="Path to report.json (required for layers 2–5)")
    parser.add_argument(
        "--layer", type=int, choices=[1, 2, 3, 4, 5],
        help="Single layer to run",
    )
    parser.add_argument("--all", action="store_true", help="Run all layers")
    parser.add_argument(
        "--sample-rate", type=float, default=0.2,
        help="Fraction of citations to sample for Layer 4 (default: 0.2)",
    )
    args = parser.parse_args()

    if not args.layer and not args.all:
        parser.print_help()
        return 0

    layers = list(range(1, 6)) if args.all else [args.layer]
    exit_code = 0

    # Load report if needed
    analysis = None
    if any(l in layers for l in (2, 3, 4, 5)):
        if not args.report:
            print("Error: report.json path required for layers 2–5", file=sys.stderr)
            return 1
        with open(args.report) as f:
            analysis = FinalAnalysis(**json.load(f))

    for layer in layers:
        print(f"\n{'='*50}")
        print(f"Layer {layer}", end=" — ")

        if layer == 1:
            print("Prompt Linter")
            from src.audit.prompt_linter import lint
            violations = lint()
            if violations:
                print("FAILURES:")
                for v in violations:
                    print(f"  ✗ {v}")
                exit_code = 1
            else:
                print("All checks passed.")

        elif layer == 2:
            print("Output Integrity")
            from src.audit.output_validator import validate
            violations = validate(analysis)
            if violations:
                print("FAILURES:")
                for v in violations:
                    print(f"  ✗ {v}")
                exit_code = 1
            else:
                print("All checks passed.")

        elif layer == 3:
            print("URL Reachability")
            from src.audit.url_checker import check_urls, _extract_urls
            urls = _extract_urls(analysis)
            print(f"Checking {len(urls)} URLs...")
            results = check_urls(analysis)
            ok = [r for r in results if r["ok"]]
            failures = [r for r in results if not r["ok"]]
            print(f"Reachable: {len(ok)}/{len(results)}")
            if failures:
                print("FAILURES:")
                for r in failures:
                    status = r["status"] or "ERR"
                    print(f"  [{status}] {r['url']}  {r['error'] or ''}")
                exit_code = 1

        elif layer == 4:
            print(f"Grounding Verifier (sample rate: {args.sample_rate:.0%})")
            from src.audit.grounding_verifier import verify_grounding
            results = verify_grounding(analysis, sample_rate=args.sample_rate)
            if not results:
                print("No cited sentences found.")
            else:
                markers = {"SUPPORTED": "✓", "PARTIAL": "~", "UNSUPPORTED": "✗",
                           "FETCH_FAILED": "?", "UNKNOWN": "?"}
                by_verdict: dict = {}
                for r in results:
                    by_verdict.setdefault(r["verdict"], []).append(r)
                for verdict in ("SUPPORTED", "PARTIAL", "UNSUPPORTED", "FETCH_FAILED", "UNKNOWN"):
                    items = by_verdict.get(verdict, [])
                    if not items:
                        continue
                    print(f"{markers.get(verdict, '?')} {verdict} ({len(items)})")
                    if verdict != "SUPPORTED":
                        exit_code = 1
                        for item in items:
                            print(f"  [{item['citation']}] {item['sentence'][:120]}...")
                            print(f"       {item['url']}")

        elif layer == 5:
            print("R1→R2 Consistency")
            from src.audit.consistency_checker import check_consistency
            results = check_consistency(analysis)
            if not results:
                print("No module pairs with both rounds found.")
            else:
                ok = [r for r in results if r["ok"]]
                failures = [r for r in results if not r["ok"]]
                print(f"Consistent: {len(ok)}/{len(results)} modules")
                if failures:
                    exit_code = 1
                    for r in failures:
                        print(f"\n  [{r['module']}]")
                        for issue in r["issues"]:
                            print(f"    ✗ {issue}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
