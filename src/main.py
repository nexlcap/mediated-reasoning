import argparse
import os
import subprocess
import sys

from dotenv import load_dotenv

from src.llm.client import ClaudeClient, DEFAULT_MODEL
from src.llm.prompts import ALL_MODULE_NAMES
from src.mediator import Mediator
from src.modules import MODULE_REGISTRY
from src.utils.exporters import export_all
from src.utils.formatters import format_customer_report, format_detailed_report, format_final_analysis, format_round_summary

DEFAULT_MODULE_NAMES = {cls(None).name for cls in MODULE_REGISTRY}


def _git_short_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


def main():
    load_dotenv()

    from src import observability
    observability.setup()

    parser = argparse.ArgumentParser(
        description="Mediated Reasoning System - Multi-perspective problem analysis"
    )
    parser.add_argument("problem", nargs="?", help="The problem or idea to analyze")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"LiteLLM model string for synthesis (default: {DEFAULT_MODEL}). Examples: claude-opus-4-6, gpt-4o, ollama/llama3.3")
    parser.add_argument("--module-model", default="", help="LiteLLM model string for module analysis calls (default: same as --model). Examples: claude-haiku-4-5-20251001, gpt-4o-mini, ollama/phi4")
    parser.add_argument("--context", default="", metavar="TEXT", help="User context and constraints (e.g. 'Bootstrapped SaaS, 2 co-founders, $8k MRR, B2B'). Injected into every LLM call so recommendations are calibrated to your situation.")
    parser.add_argument("--context-file", default="", metavar="PATH", help="Path to a file containing user context (alternative to --context for longer profiles)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed round-by-round output")
    parser.add_argument("--report", action="store_true", help="Generate a comprehensive detailed report")
    parser.add_argument("--customer-report", action="store_true", help="Generate a customer-facing report (no internal details)")
    parser.add_argument("--output", action="store_true", help="Export reports to output/ directory (.md, .json, .html)")
    parser.add_argument("--interactive", action="store_true", help="Enter interactive follow-up mode after analysis")
    parser.add_argument("--list-modules", action="store_true", help="List fixed fallback modules and exit")
    parser.add_argument("--no-search", action="store_true", help="Skip web search pre-pass (disables grounded source fetching via Tavily)")
    parser.add_argument("--deep-research", action="store_true", help="After synthesis, run targeted web search on high/critical conflicts and red flags to produce evidence-based verdicts and updated recommendations")
    parser.add_argument("--run-label", default="", help="Tag for metrics comparison (e.g. 'pre-ptc', 'ptc'). Defaults to git short hash.")
    # Hidden escape hatches (always-on by default)
    parser.add_argument("--no-auto-select", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-repeat-prompt", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.list_modules:
        for name in ALL_MODULE_NAMES:
            marker = "(default)" if name in DEFAULT_MODULE_NAMES else "(pool)"
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

    auto_select = not args.no_auto_select

    user_context = args.context.strip()
    if not user_context and args.context_file:
        try:
            with open(args.context_file) as f:
                user_context = f.read().strip()
        except OSError as e:
            print(f"Warning: could not read context file: {e}", file=sys.stderr)

    client = ClaudeClient(model=args.model)
    module_client = ClaudeClient(model=args.module_model, max_tokens=2048) if args.module_model else None
    mediator = Mediator(client, auto_select=auto_select, search=not args.no_search, deep_research=args.deep_research, module_client=module_client, repeat_prompt=not args.no_repeat_prompt, user_context=user_context or None)

    print(f"\nAnalyzing: {problem}\n")
    if user_context:
        print(f"Context: {user_context[:120]}{'…' if len(user_context) > 120 else ''}\n")
    print("Running adaptive module selection + 3-round mediated reasoning...")
    print("This may take a few minutes.\n")

    module_names = [] if auto_select else [m.name for m in mediator.modules]
    with observability.trace(
        "mediated-reasoning",
        input=problem,
        metadata={"run_label": args.run_label, "model": args.model, "modules": module_names},
    ):
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
