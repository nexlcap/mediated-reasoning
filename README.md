# Mediated Reasoning

A CLI tool that uses multi-agent mediated reasoning to analyze complex problems from multiple perspectives. Specialist modules independently assess a problem, revise after seeing each other's work, and a mediator synthesizes the results into a final analysis with conflict detection, priority flags, and actionable recommendations with inline source citations.

## How It Works

Three rounds of structured reasoning:

1. **Round 1 — Independent Analysis:** Each module analyzes the problem independently, ensuring unbiased initial perspectives.
2. **Round 2 — Informed Revision:** Modules see each other's Round 1 outputs and revise their analysis.
3. **Round 3 — Synthesis:** The mediator identifies conflicts between modules, flags critical issues (red/yellow/green), and generates final recommendations.

Modules run in parallel within each round via programmatic tool calling (PTC). A web search pre-pass grounds each module's analysis in real, cited sources (DuckDuckGo by default — no API key required; Tavily opt-in for higher quality).

## Setup

```bash
conda create -n mediated-reasoning python=3.11
conda activate mediated-reasoning
pip install -r requirements.txt

cp .env.example .env
# Add ANTHROPIC_API_KEY to .env (web search works out of the box via DuckDuckGo)

# Optional: Tavily for higher-quality search results
# pip install -r requirements-tavily.txt
# Add TAVILY_API_KEY to .env
```

## Usage

```bash
# Basic analysis (3 default modules: market, cost, risk)
python -m src.main "Should we build a food delivery app?"

# Adaptive module selection — LLM picks relevant modules from a pool of 12
python -m src.main "your problem" --auto-select

# Export all formats (md, json, html) to output/ directory
python -m src.main "your problem" --output

# Customer-facing report (no internal details)
python -m src.main "your problem" --customer-report

# Detailed internal report (round-by-round breakdown)
python -m src.main "your problem" --report

# Skip web search (cite from training knowledge only)
python -m src.main "your problem" --no-search

# Deep research round: targeted evidence gathering for conflicts and red flags
python -m src.main "your problem" --deep-research

# Interactive follow-up questions after analysis
python -m src.main "your problem" --interactive

# Adjust module weights (0 deactivates a module)
python -m src.main "your problem" --weight legal=2 --weight cost=0

# Use a separate model for module calls (e.g. for cost testing)
python -m src.main "your problem" --module-model claude-haiku-4-5-20251001

# Tag run for metrics comparison
python -m src.main "your problem" --output --run-label baseline

# List available modules
python -m src.main --list-modules
```

### Output Directory Structure

```
output/
  should-we-build-a-food-delivery-app/
    2026-02-11T14-30-00/
      report.md
      report.json
      report.html
```

### Metrics Comparison

Compare token usage, timing, and quality metrics across labelled runs:

```bash
python -m src.metrics                              # list all runs
python -m src.metrics compare "food delivery"     # filter by problem
python -m src.metrics compare --label baseline v2 # compare two labels
```

### Source Integrity Audit

Five-layer audit for hallucination detection, run automatically (layers 1–3) with `--output`:

```bash
python -m src.audit report.json --all         # run all layers
python -m src.audit report.json --layer 3     # URL reachability only
python -m src.audit report.json --layer 4     # grounding verification (20% sample)
python -m src.audit report.json --layer 5     # R1→R2 consistency check
```

## Observability (Langfuse)

Optional LLM call tracing with cost, latency, and token breakdowns per round.

```bash
# Install optional deps
pip install -r requirements-langfuse.txt

# Add to .env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

When keys are set, every run creates a trace in your Langfuse dashboard named `mediated-reasoning` with nested spans for `auto-select`, `round-1`, `round-2`, `synthesis`, and `deep-research`. Module generations are auto-captured by OpenTelemetry instrumentation. Without keys the system runs unchanged.

## Sample Reports

Published reports are available on **[GitHub Pages](https://nexlcap.github.io/mediated-reasoning/)**.

## Testing

```bash
pytest
```

## License

[MIT](LICENSE)
