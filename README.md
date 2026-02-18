# Mediated Reasoning

A CLI tool that uses multi-agent mediated reasoning to analyze complex problems from multiple perspectives. Three default modules (market, cost, risk) independently assess a problem, revise after seeing each other's work, and a mediator synthesizes the results into a final analysis with conflict detection and actionable recommendations. Additional specialist modules (tech, legal, scalability, and more) can be activated via `--auto-select`.

## How It Works

The system runs a 3-round process (7 API calls with default modules):

1. **Round 1 -- Independent Analysis:** Each module analyzes the problem independently, ensuring unbiased initial perspectives.
2. **Round 2 -- Informed Revision:** Modules see each other's Round 1 outputs and revise their analysis.
3. **Round 3 -- Synthesis:** The mediator identifies conflicts between modules, flags critical issues (red/yellow/green), and generates final recommendations with inline source citations.

Modules run in parallel within each round using `ThreadPoolExecutor`.

## Setup

```bash
# Clone and set up environment
conda create -n mediated-reasoning python=3.11
conda activate mediated-reasoning
pip install -r requirements.txt

# Configure API key
cp .env.example .env
# Edit .env and add your Anthropic API key
```

## Usage

```bash
# Basic analysis
python -m src.main "Should we build a food delivery app?"

# Detailed internal report
python -m src.main "your problem" --report

# Customer-facing report (no internal details)
python -m src.main "your problem" --customer-report

# Export all formats (md, json, html) to output/ directory
python -m src.main "your problem" --output

# Combine flags
python -m src.main "your problem" --report --output

# Interactive follow-up questions after analysis
python -m src.main "your problem" --interactive

# Adjust module weights (0 deactivates a module)
python -m src.main "your problem" --weight legal=2 --weight cost=0

# Adaptive module selection (LLM pre-pass picks relevant modules)
python -m src.main "your problem" --auto-select

# RACI matrix for conflict resolution
python -m src.main "your problem" --raci

# List available modules
python -m src.main --list-modules

# Verbose output (shows round-by-round details)
python -m src.main "your problem" --verbose
```

### Output Directory Structure

When using `--output`, reports are organized by problem and timestamp:

```
output/
  should-we-build-a-food-delivery-app/
    2026-02-11T14-30-00/
      report.md
      report.json
      report.html
```

## Testing

```bash
pytest
```

## License

[MIT](LICENSE)
