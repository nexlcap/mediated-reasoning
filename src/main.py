import argparse
import os
import sys

from dotenv import load_dotenv

from src.llm.client import ClaudeClient, DEFAULT_MODEL
from src.mediator import Mediator
from src.utils.formatters import format_final_analysis, format_round_summary


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Mediated Reasoning System - Multi-perspective problem analysis"
    )
    parser.add_argument("problem", nargs="?", help="The problem or idea to analyze")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--verbose", action="store_true", help="Show detailed round-by-round output")
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

    client = ClaudeClient(model=args.model)
    mediator = Mediator(client)

    print(f"\nAnalyzing: {problem}\n")
    print("Running 3-round mediated reasoning (11 API calls)...")
    print("This may take a few minutes.\n")

    result = mediator.analyze(problem)

    if args.verbose:
        round1 = [o for o in result.module_outputs if o.round == 1]
        round2 = [o for o in result.module_outputs if o.round == 2]
        print(format_round_summary(round1, 1))
        print(format_round_summary(round2, 2))

    print(format_final_analysis(result))


if __name__ == "__main__":
    main()
