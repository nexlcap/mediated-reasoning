---
title: Fusen
emoji: 🔥
colorFrom: red
colorTo: yellow
sdk: gradio
sdk_version: "6.6.0"
python_version: "3.11"
app_file: app.py
pinned: false
---

# 🔥 Fusen

**Fuse every angle. Move alone.**

**Try it now:** [🔥 HuggingFace Space](https://huggingface.co/spaces/Yi47/mediated-reasoning) — no setup required, bring your own API key.

Fusen is the AI co-founder for solo entrepreneurs and builders. It assembles the right specialist advisors for your specific question, fuses their perspectives through three rounds of structured reasoning, and delivers a single, conflict-arbitrated recommendation — zero blind spots.

Whether you're validating a startup idea, distilling market signals into product opportunities, or navigating the next phase of company building, Fusen covers every role so you don't have to hire for them.

## How It Works

Three rounds of structured reasoning:

1. **Round 1 — Independent Analysis:** Fusen selects the specialist perspectives your problem needs, then each analyses it independently — no groupthink.
2. **Round 2 — Informed Revision:** Specialists see each other's outputs and revise their positions with full cross-domain context.
3. **Round 3 — Synthesis:** Conflicts are identified and arbitrated, critical issues are flagged (red/yellow/green), and a final recommendation is generated.

Agents run in parallel within each round via programmatic tool calling (PTC). LiteLLM is used as the LLM backend, supporting any provider out of the box — Anthropic (default), OpenAI, Google Gemini, Groq, or fully local models via Ollama (no API key required). A web search pre-pass grounds each agent's analysis in real, cited sources (DuckDuckGo by default — no API key required; Tavily opt-in for higher quality). A structural quality gate scores every run on source survival, agent completion, and critical flag density, and displays the result (`good` / `degraded` / `poor`) at the end of every output.

## Setup

```bash
conda create -n mediated-reasoning python=3.11
conda activate mediated-reasoning
pip install -r requirements.txt

cp .env.example .env
# Add ANTHROPIC_API_KEY to .env for the default Claude model
# For other providers, see .env.example — OpenAI, Google (GEMINI_API_KEY), Groq, or Ollama (local, no key)

# Optional: Tavily for higher-quality search results
# pip install -r requirements-tavily.txt
# Add TAVILY_API_KEY to .env
```

## Usage

```bash
# Basic analysis
python -m src.main "Should we build a food delivery app?"

# Export all formats (md, json, html) to output/ directory
python -m src.main "your problem" --output

# Detailed internal report (round-by-round breakdown)
python -m src.main "your problem" --report

# Skip web search pre-pass (use model training knowledge only)
python -m src.main "your problem" --no-search

# Deep research round: targeted evidence gathering for conflicts and red flags
python -m src.main "your problem" --deep-research

# Interactive follow-up questions after analysis
python -m src.main "your problem" --interactive

# Use a separate model for agent calls (cheaper/faster)
python -m src.main "your problem" --agent-model claude-haiku-4-5-20251001

# Use any LiteLLM-supported provider (OpenAI, Gemini, Groq, local Ollama, etc.)
python -m src.main "your problem" --model gpt-4o --agent-model gpt-4o-mini
python -m src.main "your problem" --model gemini/gemini-2.5-pro --agent-model gemini/gemini-2.5-flash  # Google Gemini
python -m src.main "your problem" --model ollama/llama3.3  # fully local, no API key

# Tag run for metrics comparison
python -m src.main "your problem" --output --run-label baseline

# List available agents
python -m src.main --list-agents

# Inject user context so recommendations are calibrated to your situation
python -m src.main "your problem" --context "Bootstrapped SaaS, 2 co-founders, $8k MRR, B2B"
python -m src.main "your problem" --context-file context.txt

# Persist project memory across sessions (brief.md + session logs)
python -m src.main "your problem" --project ./my-project

# Generate a client-facing report (no internal reasoning details)
python -m src.main "your problem" --customer-report

# Show detailed round-by-round output in the terminal
python -m src.main "your problem" --verbose
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

### Run Quality Gate

Every run computes a quality score (0–1) from structural metrics — no LLM calls:

| Signal | Condition | Penalty |
|--------|-----------|---------|
| Agent failures | per failed agent | −0.30 |
| Source survival | <50% of claimed sources had real URLs | −0.30 |
| Source survival | <70% | −0.10 |
| Grounding depth | <5 sources survived | −0.20 |
| Critical flags | ≥4 red flags | −0.10 |

Tiers: **good** (≥0.8) · **degraded** (≥0.5) · **poor** (<0.5). Displayed in color at the end of every output; degraded/poor runs also log a warning.

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

When keys are set, every run creates a trace in your Langfuse dashboard named `fusen` with nested spans for `auto-select`, `round-1`, `round-2`, `synthesis`, and `deep-research`. Agent generations are auto-captured by OpenTelemetry instrumentation. Without keys the system runs unchanged.

## Sample Reports

Published reports are available on **[GitHub Pages](https://nexlcap.github.io/mediated-reasoning/)**.

## Testing

```bash
pytest
```

## License

[MIT](LICENSE)
