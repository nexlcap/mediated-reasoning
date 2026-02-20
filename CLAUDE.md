# Mediated Reasoning - Claude Code Context

## Project Summary

CLI tool using multi-agent mediated reasoning to analyze complex problems from multiple perspectives (market, tech, cost, legal, scalability). Uses a 3-round process: independent analysis, informed revision, synthesis.

## Key Commands

- `conda activate mediated-reasoning`
- `python -m src.main "problem statement"` — run analysis
- `pytest` — run tests

## Improvement List

| # | Item | Status |
|---|------|--------|
| 1 | Parallel module execution | Done |
| 2 | Export to markdown/JSON/HTML (`--output report.md`) | Done |
| 3 | Suppress logging noise (stderr or `--verbose` only) | Done |
| 4 | Module weighting (`--weight legal=2`) | Done |
| 5 | Structured conflict extraction (objects, not free-text) | Done |
| 6 | Follow-up / interactive mode (`--interactive`) | Done |
| 7 | CLI argument tests | Done |
| 8 | `--list-modules` flag | Done |
| 9 | `--report` flag for detailed output | Done |
| 10 | Sources/citations field | Done |
| 11 | Langfuse integration (tracing, cost tracking) | Done |
| 12 | `--customer-report` flag (client-facing, no internals) | Done |
| 13 | Optional RACI matrix (`--raci`) for synthesis conflict resolution | Done |
| 14 | Adaptive module selection — pre-pass to activate only relevant modules | Done |
| 15 | Runtime re-delegation on failure — retry/redistribute failed modules | Open |
| 16 | Per-module trust scores — dynamic reliability tracking across runs | Open |
| 17 | Web search pre-pass (Tavily) — grounded real citations, `--no-search` flag | Done |
| 18 | Programmatic Tool Calling (PTC) — parallel R1/R2 via direct tool calling, eliminates stagger | Done |
| 19 | Slim R2 cross-module context — pass only summary+flags to other modules in Round 2 | Done |
| 20 | Shared Tavily query cache — deduplicate Tavily calls across modules within a run | Done |
| 21 | Model tiering (`--module-model`) — separate model for module vs synthesis calls | Done |
| 22 | Prompt repetition for synthesis + auto-select (on by default, `--no-repeat-prompt` to disable, arxiv 2512.14982) | Done |
| 23 | DuckDuckGo fallback search — zero-config default; Tavily opt-in via `TAVILY_API_KEY` | Done |
| 24 | Lightweight run quality gate — score + tier + warnings from structural metrics, no LLM calls | Done |
| 25 | LiteLLM backend — unified API for multi-provider + local model support (Ollama, OpenAI, Anthropic, etc.) | Done |
