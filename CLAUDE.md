# Mediated Reasoning - Claude Code Context

## Project Summary

CLI tool using multi-agent mediated reasoning to analyze complex problems from multiple perspectives. An LLM pre-pass dynamically generates 3–7 bespoke specialist roles for each problem — this is the only agent-selection path. Uses a 3-round process: independent analysis, informed revision, synthesis.

## Architecture Conventions

- **Dynamic agents only.** All agents are created by `create_dynamic_agent` factory from LLM-generated names and system prompts. There is no fixed agent pool.
- **`AGENT_SYSTEM_PROMPTS`** in `src/llm/prompts.py` starts empty at import time and is populated at runtime by `create_dynamic_agent()`.
- **Model tiering** (`agent_client` vs `client`) is a first-class feature. Never hardcode `agent_client = None` in the web UI; always expose an agent model selector.

## Key Commands

- `conda activate mediated-reasoning`
- `python -m src.main "problem statement"` — run analysis
- `pytest` — run tests

## Improvement List

| # | Item | Status |
|---|------|--------|
| 1 | Parallel agent execution | Done |
| 2 | Export to markdown/JSON/HTML (`--output`, writes to `output/` dir) | Done |
| 3 | Suppress logging noise (stderr or `--verbose` only) | Done |
| 4 | Agent weighting (`--weight legal=2`) | Removed — agent set is dynamically selected per run; pre-assigning weights to unknown agents doesn't make sense |
| 5 | Structured conflict extraction (objects, not free-text) | Done |
| 6 | Follow-up / interactive mode (`--interactive`) | Done |
| 7 | CLI argument tests | Done |
| 8 | `--list-agents` flag | Removed — no fixed pool to list |
| 9 | `--report` flag for detailed output | Done |
| 10 | Sources/citations field | Done |
| 11 | Langfuse integration (tracing, cost tracking) | Done |
| 12 | `--customer-report` flag (client-facing, no internals) | Done |
| 13 | Optional RACI matrix (`--raci`) for synthesis conflict resolution | Removed — hardcoded, rarely applicable |
| 14 | Adaptive agent selection — LLM pre-pass invents bespoke roles; fixed pool removed | Done |
| 15 | Runtime re-delegation on failure — retry/redistribute failed agents | Open |
| 16 | Per-agent trust scores — dynamic reliability tracking across runs | Open |
| 17 | Web search pre-pass (Tavily) — grounded real citations, `--no-search` flag | Done |
| 18 | Programmatic Tool Calling (PTC) — parallel R1/R2 via direct tool calling, eliminates stagger | Done |
| 19 | Slim R2 cross-agent context — pass only summary+flags to other agents in Round 2 | Done |
| 20 | Shared Tavily query cache — deduplicate Tavily calls across agents within a run | Done |
| 21 | Model tiering (`--agent-model`) — separate model for agent vs synthesis calls | Done |
| 22 | Prompt repetition for synthesis + auto-select (on by default, `--no-repeat-prompt` to disable, arxiv 2512.14982) | Done |
| 23 | DuckDuckGo fallback search — zero-config default; Tavily opt-in via `TAVILY_API_KEY` | Done |
| 24 | Lightweight run quality gate — score + tier + warnings from structural metrics, no LLM calls | Done |
| 25 | LiteLLM backend — unified API for multi-provider + local model support (Anthropic, OpenAI, Google Gemini, xAI, Ollama, etc.) | Done |
| 26 | Gradio UI for HuggingFace Spaces — public web interface, separate HF Space repo, pip-installable main package | Done |
| 27 | User context / constraints profile — inject stage, resources, industry into every run so recommendations are actionable, not generic | Done |
| 28 | A vs B comparison mode — parallel panels for two options + synthesis that explicitly contrasts them | Open |
| 29 | Document / data input — feed a PDF, financial model, or research doc as grounding context alongside web search | Open |
| 30 | Scenario / sensitivity analysis — structured what-if variants (e.g. "stress-test at 50% slower growth") without re-running from scratch | Open |
| 31 | Recommendation follow-through — capture which recommendations were acted on, track outcomes, feed results back into future runs | Open |
| 32 | Project memory — cross-session persistence with brief.md + session logs (`--project PATH`) | Done |
