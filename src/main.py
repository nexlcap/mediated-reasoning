import argparse
import os
import subprocess
import sys

from dotenv import load_dotenv

from src.llm.client import ClaudeClient, DEFAULT_MODEL
from src.llm.prompts import ALL_MODULE_NAMES, DEFAULT_RACI_MATRIX, MODULE_SYSTEM_PROMPTS
from src.mediator import Mediator
from src.modules import MODULE_REGISTRY
from src.utils.exporters import export_all
from src.utils.formatters import format_customer_report, format_detailed_report, format_final_analysis, format_round_summary

VALID_MODULE_NAMES = set(MODULE_SYSTEM_PROMPTS.keys())
DEFAULT_MODULE_NAMES = {cls(None).name for cls in MODULE_REGISTRY}


def _git_short_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


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
    parser.add_argument("--output", action="store_true", help="Export reports to output/ directory (.md, .json, .html)")
    parser.add_argument(
        "--weight", action="append", type=parse_weight, default=[], metavar="MODULE=N",
        help="Set module weight (e.g. --weight legal=2). Weight 0 deactivates a module."
    )
    parser.add_argument("--raci", action="store_true", help="Use RACI matrix for conflict resolution in synthesis")
    parser.add_argument("--interactive", action="store_true", help="Enter interactive follow-up mode after analysis")
    parser.add_argument("--list-modules", action="store_true", help="List available modules and exit")
    parser.add_argument("--auto-select", action="store_true", help="Use adaptive module selection (LLM pre-pass to pick relevant modules)")
    parser.add_argument("--no-search", action="store_true", help="Skip web search pre-pass (disables grounded source fetching via Tavily)")
    parser.add_argument("--deep-research", action="store_true", help="After synthesis, run targeted web search on high/critical conflicts and red flags to produce evidence-based verdicts and updated recommendations")
    parser.add_argument("--run-label", default="", help="Tag for metrics comparison (e.g. 'pre-ptc', 'ptc'). Defaults to git short hash.")
    args = parser.parse_args()

    if args.list_modules:
        for name in ALL_MODULE_NAMES:
            marker = "(default)" if name in DEFAULT_MODULE_NAMES else "(auto-select pool)"
            print(f"{name}  {marker}")
        sys.exit(0)

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
    raci = DEFAULT_RACI_MATRIX if args.raci else None

    client = ClaudeClient(model=args.model)
    mediator = Mediator(client, weights=weights, raci=raci, auto_select=args.auto_select, search=not args.no_search, deep_research=args.deep_research)

    print(f"\nAnalyzing: {problem}\n")
    if args.auto_select:
        print("Running adaptive module selection + 3-round mediated reasoning...")
    else:
        print("Running 3-round mediated reasoning (7 API calls)...")
    print("This may take a few minutes.\n")

    result = mediator.analyze(problem)
    result.run_label = args.run_label or _git_short_hash()

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
        from src.audit.runner import run_fast_audit
        print("Running source integrity audit (layers 1–3)...")
        result.audit = run_fast_audit(result)
        out_dir = export_all(result, report_style)
        print(f"\nReports exported to {out_dir}")

    if args.interactive:
        print("\nInteractive mode — ask follow-up questions (type 'exit' to quit)")
        while True:
            try:
                question = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not question or question.lower() in ("exit", "quit"):
                break
            response = mediator.followup(result, question)
            print(f"\n{response}\n")


if __name__ == "__main__":
    main()
