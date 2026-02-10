import argparse
import os
import sys

from dotenv import load_dotenv

from src.llm.client import ClaudeClient, DEFAULT_MODEL
from src.mediator import Mediator
from src.modules import MODULE_REGISTRY
from src.utils.exporters import export_to_file
from src.utils.formatters import format_customer_report, format_detailed_report, format_final_analysis, format_round_summary

VALID_MODULE_NAMES = {cls(None).name for cls in MODULE_REGISTRY}


def parse_weight(value: str) -> tuple[str, float]:
    """Parse a 'module=weight' string, validating module name and weight."""
    if "=" not in value:
        raise argparse.ArgumentTypeError(
            f"Invalid weight format: '{value}'. Expected format: module=weight (e.g. legal=2)"
        )
    name, weight_str = value.split("=", 1)
    if name not in VALID_MODULE_NAMES:
        raise argparse.ArgumentTypeError(
            f"Unknown module: '{name}'. Valid modules: {', '.join(sorted(VALID_MODULE_NAMES))}"
        )
    try:
        weight = float(weight_str)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid weight value: '{weight_str}'. Must be a number."
        )
    if weight < 0:
        raise argparse.ArgumentTypeError(
            f"Weight for '{name}' must be non-negative, got {weight}"
        )
    return name, weight


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Mediated Reasoning System - Multi-perspective problem analysis"
    )
    parser.add_argument("problem", nargs="?", help="The problem or idea to analyze")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--verbose", action="store_true", help="Show detailed round-by-round output")
    parser.add_argument("--report", action="store_true", help="Generate a comprehensive detailed report")
    parser.add_argument("--customer-report", action="store_true", help="Generate a customer-facing report (no internal details)")
    parser.add_argument("--output", help="Export report to file (.md, .json, .html)")
    parser.add_argument(
        "--weight", action="append", type=parse_weight, default=[], metavar="MODULE=N",
        help="Set module weight (e.g. --weight legal=2). Weight 0 deactivates a module."
    )
    args = parser.parse_args()

    problem = args.problem
    if not problem:
        print("Enter your problem or idea to analyze:")
        problem = input("> ").strip()
        if not problem:
            print("No problem provided. Exiting.")
            sys.exit(1)

    if args.verbose:
        os.environ["MEDIATED_REASONING_DEBUG"] = "1"

    weights = dict(args.weight) if args.weight else {}

    client = ClaudeClient(model=args.model)
    mediator = Mediator(client, weights=weights)

    print(f"\nAnalyzing: {problem}\n")
    print("Running 3-round mediated reasoning (11 API calls)...")
    print("This may take a few minutes.\n")

    result = mediator.analyze(problem)

    if args.verbose:
        round1 = [o for o in result.module_outputs if o.round == 1]
        round2 = [o for o in result.module_outputs if o.round == 2]
        print(format_round_summary(round1, 1))
        print(format_round_summary(round2, 2))

    if args.customer_report:
        report_style = "customer"
        print(format_customer_report(result))
    elif args.report:
        report_style = "detailed"
        print(format_detailed_report(result))
    else:
        report_style = "default"
        print(format_final_analysis(result))

    if args.output:
        export_to_file(result, args.output, report_style)
        print(f"\nReport exported to {args.output}")


if __name__ == "__main__":
    main()
