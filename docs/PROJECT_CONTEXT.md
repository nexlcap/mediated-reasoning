# Mediated Reasoning System - Project Context

## Project Overview

A general-purpose CLI tool that uses mediated reasoning to tackle complex, multi-faceted problems. The system breaks down problems into specialized perspectives and synthesizes insights through structured rounds of analysis.

**Core Problem:** Complex decisions require evaluating multiple dimensions simultaneously — market fit, technical feasibility, cost, legal implications, scalability, etc.

**Solution:** Deploy specialized reasoning modules that each focus on one aspect, then use a mediator to synthesize their perspectives into actionable insights.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     User Problem                         │
│          "I want to build a food delivery app"           │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │      MEDIATOR         │
         │  (Orchestrator)       │
         └───────────┬───────────┘
                     │
         ┌───────────┴───────────┐
         │   3-Round Process     │
         └───────────┬───────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
    ▼                ▼                ▼
┌────────┐      ┌────────┐      ┌────────┐
│ Market │      │  Cost  │      │  Risk  │
│ Module │      │ Module │      │ Module │
└────────┘      └────────┘      └────────┘
         │
         ▼
┌─────────────────────────────────┐
│    Final Synthesized Analysis   │
│  • Conflicts identified         │
│  • Flags (red/yellow/green)     │
│  • Recommendations              │
└─────────────────────────────────┘
```

## 3-Round Reasoning Process

### Round 1: Independent Analysis
Each module analyzes the problem independently without seeing other modules' work. This ensures unbiased initial perspectives.

### Round 2: Informed Revision
Modules see each other's Round 1 outputs and can revise their analysis. For example, the market analysis module might raise a concern that prompts the tech module to reconsider something.

### Round 3: Synthesis
The mediator collects all outputs, identifies conflicts between modules, flags critical issues, and generates final recommendations.

## Modules

Three default modules represent the ground-truth factors any business must address. Nine additional pool modules are available via `--auto-select`:

### Default Modules (3)

### Market Module
- Market size and opportunity
- Competitive landscape
- Customer demand validation
- Product-market fit assessment

### Cost Module
- Initial investment needed
- Operating costs
- Revenue projections
- Break-even analysis
- Funding requirements

### Risk Module
- Uncertainty assessment
- Downside scenarios
- Threat categorization
- Hedging strategies
- Contingency planning

### Auto-Select Pool Modules (9)

These are available when using `--auto-select`:

- **Tech** — Technology stack, implementation complexity, technical risks, dependencies
- **Legal** — Regulatory requirements, legal risks, compliance, liability, IP
- **Scalability** — Growth potential, infrastructure scaling, team scaling, bottlenecks
- **Political** — Government policy, political stability, institutional readiness, geopolitical factors
- **Social** — Societal impact, demographics, public acceptance, equity/inclusion, community impact
- **Environmental** — Ecological footprint, climate risk, resource consumption, sustainability
- **Ethics** — Fairness, bias, privacy, rights, dual-use, transparency, accountability
- **Operational** — Internal processes, team/HR, supply chain, org structure, change management
- **Strategy** — Business model, value proposition, competitive moats, positioning, partnerships

## Data Models

Pydantic schemas for structured outputs:

```python
class ModuleOutput(BaseModel):
    module_name: str
    round: int
    analysis: Dict
    flags: List[str]
    sources: List[str]
    revised: bool

class Conflict(BaseModel):
    modules: List[str]          # e.g. ["market", "cost"]
    topic: str                  # e.g. "burn rate"
    description: str            # e.g. "Market sees high demand but cost flags high burn rate [1][2]"
    severity: Literal["critical", "high", "medium", "low"]

class ConflictResolution(BaseModel):
    topic: str                      # conflict topic or red flag text
    modules: List[str]              # modules involved; empty list for standalone red flags
    severity: str                   # "high"/"critical" for conflicts, "red" for standalone flags
    verdict: str                    # evidence-based finding with inline [N] citations
    updated_recommendation: str     # concrete action step derived from the verdict
    sources: List[str]              # cleared after consolidation into FinalAnalysis.sources

class UrlCheckResult(BaseModel):
    url: str
    status: Optional[int]           # HTTP status code, or None if connection error
    error: Optional[str]            # Error message if connection failed
    ok: bool                        # True if status 2xx/3xx and no error
    bot_blocked: bool = False       # True when status 403/401/429 — page likely exists but blocks crawlers

class GroundingResult(BaseModel):
    verdict: str        # SUPPORTED / PARTIAL / UNSUPPORTED / FETCH_FAILED / UNKNOWN
    citation: str       # e.g. "[3]"
    sentence: str       # the claim that was checked against the source
    url: str            # source URL that was fetched for verification

class ConsistencyResult(BaseModel):
    module: str         # module name
    ok: bool            # True if no new uncited facts found in Round 2
    issues: List[str]   # descriptions of new concrete facts introduced without citation

class AuditSummary(BaseModel):
    layer1_passed: bool             # Prompt constraint linter: all checks passed
    layer1_violations: List[str]    # Constraint phrases missing from prompts
    layer2_passed: bool             # Citation integrity: no orphan refs, all sources have URLs
    layer2_violations: List[str]    # Specific integrity failures
    layer3_total: int               # Total URLs checked
    layer3_ok: int                  # URLs that returned 2xx/3xx
    layer3_failures: List[UrlCheckResult] # URLs that failed reachability checks
    layer4_ran: bool                # Whether grounding verifier (Layer 4) was run
    layer4_results: List[GroundingResult] # Per-citation grounding verdicts (sampled)
    layer5_ran: bool                # Whether R1→R2 consistency checker (Layer 5) was run
    layer5_results: List[ConsistencyResult] # Per-module consistency results

class FinalAnalysis(BaseModel):
    problem: str
    generated_at: str               # ISO 8601 UTC timestamp set by mediator.analyze()
    module_outputs: List[ModuleOutput]
    conflicts: List[Conflict]           # Structured conflict objects
    synthesis: str
    recommendations: List[str]
    priority_flags: List[str]           # Red/yellow/green flags
    sources: List[str]                  # Consolidated, URL-deduplicated citations; sources without URLs are dropped
    deactivated_disclaimer: str         # Disclaimer when modules are deactivated via --weight
    raci_matrix: Dict[str, Dict[str, Any]] # RACI matrix used for synthesis conflict resolution
    selection_metadata: Optional[SelectionMetadata] # Populated when --auto-select is used
    weights: Dict[str, float]           # Module weights as passed to the mediator (empty = all defaults)
    search_enabled: bool                # Whether web search was active for this run (DuckDuckGo or Tavily)
    conflict_resolutions: List[ConflictResolution] # Populated when --deep-research is used
    deep_research_enabled: bool         # Whether the deep research round ran
    search_context: Optional[SearchContext] # Raw search results from the pre-pass (queries + results)
    audit: Optional[AuditSummary]       # Layers 1–3 populated automatically; layers 4–5 written back by audit CLI
    quality: Optional[RunQuality]       # Structural quality score — populated by mediator after every run
    run_label: str = ""                 # Tag for metrics comparison; defaults to git short hash
    module_model: str = ""              # Model used for module calls when --module-model is set; empty = same as synthesis model
    token_usage: Optional[TokenUsage] = None  # Per-call-type token counts accumulated across the run
    timing: Optional[RoundTiming] = None      # Wall-clock time per round
    modules_attempted: int = 0          # Number of modules configured for this run
    modules_completed: int = 0          # Number of modules that produced Round 1 output
    sources_claimed: int = 0            # Total sources before URL dedup/filter in _consolidate_sources()

class SearchResult(BaseModel):
    title: str                  # Page title
    url: str                    # Canonical URL (used for deduplication)
    content: str                # Snippet/summary from the search backend

class SearchContext(BaseModel):
    queries: List[str]          # LLM-generated search queries
    results: List[SearchResult] # Deduplicated results (capped at 12)
    # format_for_prompt() serialises results as numbered [N] context block

class AdHocModule(BaseModel):
    name: str                   # e.g. "cultural"
    system_prompt: str          # LLM-generated system prompt

class TokenUsage(BaseModel):
    analyze_input: int = 0               # sum of input tokens across all client.analyze() calls (module + synthesis)
    analyze_output: int = 0              # sum of output tokens across all client.analyze() calls
    module_analyze_input: int = 0        # module-client analyze() input tokens (Haiku when --module-model is set)
    module_analyze_output: int = 0       # module-client analyze() output tokens
    synthesis_analyze_input: int = 0     # synthesis-client analyze() input tokens (synthesis, auto-select, gap-check)
    synthesis_analyze_output: int = 0    # synthesis-client analyze() output tokens
    chat_input: int = 0                  # client.chat() input tokens (--interactive follow-up mode)
    chat_output: int = 0
    ptc_orchestrator_input: int = 0      # orchestrating Claude in run_ptc_round() — 0 on pre-PTC builds
    ptc_orchestrator_output: int = 0
    total_input: int = 0
    total_output: int = 0

class RoundTiming(BaseModel):
    round1_s: float = 0.0       # wall-clock seconds for Round 1 (all modules)
    round2_s: float = 0.0       # wall-clock seconds for Round 2 (all modules)
    round3_s: float = 0.0       # wall-clock seconds for synthesis
    total_s: float = 0.0        # end-to-end wall-clock time

class RunQuality(BaseModel):
    score: float                # 0.0–1.0 composite quality score
    tier: str                   # "good" (≥0.8) | "degraded" (≥0.5) | "poor" (<0.5)
    warnings: List[str]         # human-readable reasons for any deductions

class SelectionMetadata(BaseModel):
    auto_selected: bool         # True when --auto-select was used
    selected_modules: List[str] # Module names chosen by the LLM pre-pass
    selection_reasoning: str    # Why these modules were selected
    gap_check_reasoning: str    # Gap check explanation
    ad_hoc_modules: List[AdHocModule] # Dynamically created modules to fill gaps
```

## Code Structure

```
mediated-reasoning/
├── src/
│   ├── __init__.py
│   ├── main.py                # CLI entry point
│   ├── mediator.py             # Orchestrates the 3-round process
│   ├── observability.py        # Optional Langfuse/OTEL tracing (no-op without keys)
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── base_module.py      # Base class + create_dynamic_module() factory
│   │   ├── market_module.py    # Market analysis (default)
│   │   ├── cost_module.py      # Financial analysis (default)
│   │   ├── risk_module.py      # Risk analysis (default)
│   │   ├── tech_module.py      # Technical feasibility (pool)
│   │   ├── legal_module.py     # Legal/compliance (pool)
│   │   └── scalability_module.py # Growth/scaling (pool)
│   ├── search/
│   │   ├── __init__.py
│   │   └── searcher.py         # SearchPrePass — query gen + search fetch (DDG or Tavily)
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py           # LLM API wrapper (Claude)
│   │   └── prompts.py          # Prompt templates per module
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py          # Pydantic models for outputs
│   │   └── types.py            # Type definitions
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── __main__.py         # CLI: python -m src.audit <report.json> --layer N
│   │   ├── prompt_linter.py    # Layer 1 — static prompt constraint checker
│   │   ├── output_validator.py # Layer 2 — citation integrity validator
│   │   ├── url_checker.py      # Layer 3 — URL reachability (parallel HEAD/GET)
│   │   ├── grounding_verifier.py # Layer 4 — LLM fact-checks cited claims (Haiku)
│   │   ├── consistency_checker.py # Layer 5 — R1→R2 new-fact detection (Haiku)
│   │   └── quality_gate.py     # Run quality score — structural metrics, no LLM calls
│   ├── metrics/
│   │   ├── __init__.py
│   │   └── __main__.py         # Comparison CLI: `python -m src.metrics compare`
│   └── utils/
│       ├── __init__.py
│       ├── logger.py           # Logging
│       ├── formatters.py       # Output formatting
│       ├── exporters.py        # Markdown/JSON/HTML export
│       └── html_formatter.py   # Semantic HTML generator
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Shared fixtures and sample data
│   ├── test_mediator.py
│   ├── test_modules.py
│   ├── test_formatters.py
│   ├── test_schemas.py
│   ├── test_cli.py            # CLI argument tests
│   ├── test_module_selection.py # Prompt builders, dynamic module factory
│   ├── test_exporters.py      # Export format tests
│   ├── test_audit.py          # Audit layers 1 & 2 tests
│   ├── test_ptc.py            # run_ptc_round() unit tests
│   ├── test_metrics.py        # Metrics extraction and comparison tests
│   └── test_quality_gate.py   # Run quality gate scoring tests
├── docs/
├── .env.example
└── requirements.txt
```

## Tech Stack

- **Language:** Python 3.11+
- **Environment:** Conda
- **LLM:** Claude (Anthropic API)
- **Dependencies:** `anthropic>=0.72.0`
- **Libraries:**
  - `anthropic` — API client
  - `pydantic` — Data validation and schemas
  - `python-dotenv` — Environment variable management
  - `pytest` — Testing
  - `duckduckgo-search` — zero-config web search backend (no API key required); default search backend
  - `httpx` — HTTP client for URL reachability checks and source page fetching (audit layers 3 & 4)
- **Optional dependencies** (not installed by default):
  - `tavily-python` (`requirements-tavily.txt`) — higher-quality search via Tavily API; activated automatically when `TAVILY_API_KEY` is set
  - `langfuse>=3.0.0` (`requirements-langfuse.txt`) — hosted LLM observability dashboard (traces, cost, latency)
  - `opentelemetry-instrumentation-anthropic` (`requirements-langfuse.txt`) — auto-instruments `anthropic.messages.create()` calls as OTEL spans

## Use Cases

- **Startup idea validation** — Evaluate a new app/business idea across market, tech, cost, legal, and scalability dimensions
- **Meeting agenda preparation** — Structure discussions and break down agenda items into different angles
- **Strategic planning** — Analyze complex business decisions from multiple perspectives
- **Investment decisions** — Assess opportunities with structured multi-dimensional analysis
- **Technical architecture decisions** — Evaluate trade-offs across feasibility, cost, and scalability

## CLI Flags

| Flag | Description |
|------|-------------|
| `--verbose` | Show detailed round-by-round output |
| `--report` | Generate a comprehensive detailed (internal) report |
| `--customer-report` | Generate a customer-facing report (no internal details) |
| `--output` | Export reports to `output/` directory in all formats (.md, .json, .html) |
| `--weight MODULE=N` | Set module weight (e.g. `--weight legal=2`). Weight 0 deactivates a module |
| `--interactive` | Enter interactive follow-up mode after analysis |
| `--list-modules` | List available modules and exit |
| `--raci` | Use RACI matrix for conflict resolution in synthesis |
| `--auto-select` | Adaptive module selection — LLM pre-pass picks relevant modules from a pool of 12 |
| `--no-search` | Skip web search pre-pass; modules cite from training knowledge only |
| `--deep-research` | After synthesis, run targeted web search on high/critical conflicts and red flags to produce evidence-based verdicts and updated recommendations |
| `--model MODEL` | Claude model for synthesis, auto-select, gap-check, and PTC orchestration (default: `claude-sonnet-4-20250514`) |
| `--module-model MODEL` | Claude model for R1/R2 module analysis calls (default: same as `--model`). Use e.g. `claude-haiku-4-5-20251001` for tiered cost testing |
| `--run-label LABEL` | Tag this run for metrics comparison (e.g. `pre-ptc`, `ptc`). Defaults to the current git short hash |
| `--no-repeat-prompt` | Disable prompt repetition for synthesis and auto-select calls. Repetition is on by default (arxiv 2512.14982): doubles user-turn tokens so early tokens gain attention visibility over later schema/instructions. Module R1/R2 calls are never repeated. Benchmarked: +7.4% input tokens, +11% source survival rate, source survival 75%→81% |

### Interactive Follow-up Mode (`--interactive`)

After the initial 3-round analysis completes, `--interactive` drops the user into a REPL where they can ask follow-up questions. The mediator's `followup()` method sends the question along with the full analysis context to the LLM, so answers are grounded in the original multi-module reasoning. Type `exit`, `quit`, or send an empty line to leave.

### Structured Output Directory (`--output`)

The `--output` flag is a boolean (no filename argument). It calls `export_all()` which:
1. Slugifies the problem statement (lowercase, non-alnum → `-`, max 60 chars)
2. Creates a timestamped subdirectory: `output/<slug>/<YYYY-MM-DDTHH-MM-SS>/`
3. Writes `report.md`, `report.json`, and `report.html` into that directory

This ensures every run is preserved and easily comparable.

### Metrics Comparison CLI (`python -m src.metrics`)

`src/metrics/__main__.py` aggregates `report.json` files across runs to surface the concrete impact of code changes (e.g. pre-PTC vs PTC).

```bash
python -m src.metrics                          # list all runs with labels and timestamps
python -m src.metrics compare "webmcp"         # compare runs matching a problem slug substring
python -m src.metrics compare --label pre-ptc ptc  # filter by specific run labels
```

The CLI globs `output/**/report.json`, groups by `run_label`, and prints a mean±std table with a Δ% column for: token usage (by call type), round timing, module completion rate, source survival rate, flag/conflict counts, and L3 URL reachability rate. Timing improvements >20% are marked with `←`.

## Design Decisions

### Why multi-agent over a single LLM call?
A single LLM call cannot adequately focus on multiple complex dimensions simultaneously. By making each module a separate LLM call focused on one aspect, each call can go deeper into its domain without being spread thin. The mediator then synthesizes cross-cutting conflicts and trade-offs that individual calls would miss.

### Why general-purpose rather than domain-specific?
The system originated from a specific use case (meeting agenda reasoning) but was deliberately broadened. The user explicitly chose a general-purpose, reusable architecture over a domain-specific tool — meeting agendas were "for the start" but the design should accommodate any multi-faceted problem.

### Why these 3 default modules?
The defaults were narrowed to the ground-truth factors any business must address: market viability, financial viability, and risk. The original 5 defaults (market, tech, cost, legal, scalability) were reduced after adding adaptive module selection (`--auto-select`), which can pull in tech, legal, scalability, and other specialized modules as needed. This keeps the default run lean and universal.

### Why 3 rounds?
The 3-round structure maps to a natural deliberation pattern: (1) independent thinking, (2) revision after seeing others' perspectives, (3) final synthesis. This mirrors established methods like the Delphi technique. The number was proposed and accepted without debate.

### Why independent analysis first (Round 1)?
Running modules independently in Round 1 prevents anchoring bias — if modules see each other's work from the start, earlier outputs could bias later ones. Independent-first analysis ensures each perspective is genuinely unbiased before cross-pollination in Round 2.

### How does the mediator work?
The design chose a middle path between pure aggregation and real-time back-and-forth dialogue between modules. Instead, it uses structured rounds where cross-module influence happens through shared outputs. In Round 2, modules see each other's Round 1 results and can revise. In Round 3, the mediator aggregates and synthesizes. This avoids the complexity of real-time inter-module dialogue while still enabling iterative refinement.

### Context sharing model
All modules see the full original problem (the mediator does not pre-parse or filter for each module). Module outputs are staged: not shared in Round 1, fully shared in Round 2. This prevents the mediator from becoming a bottleneck or introducing bias through selective information sharing.

### Why CLI-first?
Chosen for faster iteration, full environment control, and better git integration compared to a browser-based approach. The goal was to ship an MVP as quickly as possible.

### Why Conda over venv?
Explicit user preference. No specific technical justification — purely a tooling choice.

### Why per-module domain-specific search in both rounds?
Without real sources, every module invents plausible-sounding citations from training data. These hallucinated sources are unacceptable for any analysis that will inform real decisions.

**The approach:** Each module runs its own web search in both Round 1 and Round 2, rather than sharing a single global pre-pass. `SearchPrePass.run_for_module()` is called per module per round:

- **Query generation:** The LLM generates 3–4 queries using the module's system prompt as a domain hint, so a legal module generates queries about regulatory frameworks while a market module generates queries about market size data. In Round 2, the module's own Round 1 key findings are also included so the search fetches supporting evidence and counter-arguments for what was already found.
- **Fetching:** Results are capped at 8 per module per round and deduplicated by URL. Tavily (`search_depth="advanced"`) returns richer content; DuckDuckGo returns shorter snippets but requires no account or API key.
- **Injection:** Results are formatted as a numbered `[N] Title — URL\n    content` block and injected into the module's prompt. Modules are explicitly instructed to cite from those entries and copy the full URL into the sources array.

**Source consolidation:** Each module produces local source indices [1]–[N]. After all rounds complete, `_consolidate_sources()` merges all module sources into a global deduplicated list (by URL first, then text), remaps all inline citations to global indices, and clears per-module source lists. Before synthesis (Round 3), this global list is pre-built and injected into the synthesis prompt with a `CRITICAL` instruction to cite only from it — preventing synthesis from inventing new sources beyond what modules actually found.

**Search backend priority:** DuckDuckGo is the zero-config default (no API key, no account, ships in `requirements.txt`). If `TAVILY_API_KEY` is set and `tavily-python` is installed (`pip install -r requirements-tavily.txt`), Tavily is used instead for higher-quality results. Resolved once at `SearchPrePass.__init__` time.

**Graceful degradation:** If neither backend is available, or any search call fails, that module's search is silently skipped and the module falls back to training-knowledge citations. `--no-search` disables all search explicitly.

**Benchmark — DuckDuckGo vs Tavily vs no-search** (fixed 3-module runs, single comparison, same problem):

| Metric | no-search | DuckDuckGo | Tavily |
|--------|-----------|------------|--------|
| sources_claimed | 36 | 36 | 44 |
| sources_survived | 27 | 27 | 37 |
| source_survival_pct | 75% | 75% | 84% |
| l3_ok_pct (live URLs) | 93% | 82% | 86% |
| flags_green | 1 | 2 | 3 |
| round1_s | 64s | 36s | 52s |
| total_s | 120s | 95s | 123s |

DDG produces the same source count and survival rate as no-search (training citations happen to match in volume), but adds real URLs and one more green flag. Tavily fetches more sources (+22% claimed, +37% survived), higher survival rate (+9pp), and one more green flag again — the `search_depth="advanced"` processing accounts for the quality gap and the extra latency. DDG's lower L3 URL rate (82% vs 86%) reflects some bot-blocked or paywalled pages in its results, handled by the existing `bot_blocked` distinction. Flags/conflicts structure is identical across all three backends.

### Why a post-synthesis deep research round (`--deep-research`)?
After synthesis, the framework has identified conflicts and red flags but no mechanism to actually *resolve* them with evidence. The deep research round (`--deep-research`) addresses this: for every `high`/`critical` severity conflict and every `red:` priority flag not already covered by a conflict, the mediator runs a targeted research task in parallel:

1. **Query generation** — Claude generates 3–4 queries specifically aimed at resolving that conflict (e.g. "WebMCP API DevTrial stability guarantees" for an API-stability conflict)
2. **Evidence fetch** — the configured search backend (DuckDuckGo or Tavily) returns fresh, current results
3. **Resolution LLM call** — receives the conflict description, both module positions, and fresh evidence; produces a `verdict` (which position evidence supports) and an `updated_recommendation` (more specific than the synthesis-level recommendations)

Resolution sources are consolidated into the global source list using the same URL-deduplication logic as module sources. The mediator handles this itself (not delegating back to modules) because conflicts are cross-domain by definition — no single domain module "owns" a cross-module disagreement. `--deep-research` is opt-in because each conflict triggers ~5 additional API calls (1 query gen + 3–4 search fetches + 1 resolution LLM call).

### Hallucination mitigations
Several layers prevent LLM-fabricated sources and unsupported claims from appearing in the output:

- **URL-only source filter** — `_consolidate_sources()` drops any source entry without an `https://` URL. Tavily always returns URLs; sources without them are training-knowledge fabrications. Inline citations pointing to dropped sources are also removed (`drop_on_miss=True` in `_remap_citations`).
- **Strict module prompt constraints** — `_module_json_instruction(has_search_context)` generates two distinct instructions: *with search context*: "sources MUST contain ONLY entries copied verbatim from the Grounded Research Context — do NOT add sources from training knowledge"; *without search context*: "sources array MUST BE EMPTY — do not fabricate source titles or URLs."
- **Pre-consolidated source list for synthesis** — Before calling the synthesis LLM, all module sources are merged into a global list `[1]–[N]`. Synthesis receives this list with a `CRITICAL` instruction to cite only within range and return an empty sources array, preventing it from inventing new sources beyond what modules actually found.
- **Follow-up constraint** — The `--interactive` follow-up system prompt explicitly says "answer strictly from the analysis provided — do not introduce new facts, statistics, or sources not present in the analysis."

**Remaining structural limitations (unfixable by prompting):**

- **Citation misattribution** — The LLM can cite a real, URL-backed source `[1]` in support of a claim that source `[1]` does not actually make. The URL is real; the attribution is wrong. Detecting this would require a separate LLM call per citation to verify relevance, which is impractical at scale.
- **Query generation bias** — Search queries are generated by the LLM itself. A module could generate queries that skew toward confirming its initial priors rather than seeking disconfirming evidence. The Tavily results are real; the selection of what to search for is not independently audited.
- **Conceptual errors** — A module can state something that is factually wrong about how a technology, regulation, or market works, regardless of whether it cites a source. This reflects training data limits and is not addressable through grounding constraints alone.
- **Round 2 new-fact constraint** — The R2 system prompt explicitly forbids introducing new statistics, percentages, version numbers, or named metrics that are not present in the module's own Round 1 output or the Grounded Research Context. Any new concrete figure must carry an inline `[N]` citation. Modules are also instructed not to soften or retract critical Round 1 findings to reach cross-module consensus. This directly addresses the cross-module amplification problem identified by the Layer 5 consistency audit.
- **Cross-module amplification (residual)** — If a Round 1 module makes an uncited claim, Round 2 modules see it as "context" and may treat it as established fact. The R2 constraint above reduces but does not eliminate this: a module can still reason from another module's uncited claim as long as it does not introduce new numbers. Full elimination would require per-claim provenance tracking across rounds.

### HTML report enhancements: timestamp, table of contents, always-visible config
Three additions improve the HTML report's professionalism and navigability:

- **Generation timestamp** — `FinalAnalysis.generated_at` stores an ISO 8601 UTC string set in `mediator.analyze()`. The HTML formatter renders it as a human-readable `"D Month YYYY"` line below the subtitle (e.g. *Generated: 18 February 2026 · 86 sources*). Placed directly under the subtitle so the reader immediately knows how fresh the analysis is.
- **Linked table of contents** — A `<nav class='toc'>` is inserted between the header block and the config box. It is built dynamically: only sections that actually render for the current `report_style` appear. Each entry is an anchor link (`href='#section-id'`) to an `id=` attribute on the corresponding `<section>` or `<h2>`. `scroll-behavior: smooth` in CSS gives fluid scrolling. This mirrors the consulting report convention: title → date → TOC → body.
- **Always-visible weights table and RACI matrix** — Module weights are shown as a formatted table even when all weights are 1.0×, so the reader can verify the analysis is unweighted. The RACI matrix is always rendered; if no custom RACI was provided, the default matrix from `DEFAULT_RACI_MATRIX` is used with a "(default)" label.

### Why a dedicated `deactivated_disclaimer` field?
When modules are deactivated via `--weight module=0`, the synthesis must include a disclaimer noting their absence. Initially this was a free-text instruction in the prompt ("you MUST include a disclaimer..."), but the LLM consistently ignored it — especially when other modules partially covered the deactivated module's domain. Adding `deactivated_disclaimer` as a required field in the JSON schema forces the LLM to populate it, making the disclaimer reliable rather than discretionary.

### Why structured Conflict objects instead of free-text?
Conflicts were originally extracted as free-text strings in the synthesis prompt. This made them inconsistent — sometimes a paragraph, sometimes a bullet point, with no reliable way to identify which modules disagreed or how severe the conflict was. Switching to structured `Conflict` objects (`modules`, `topic`, `description`, `severity`) forces the LLM to produce machine-readable, consistent conflict data that can be filtered, sorted, and rendered uniformly across export formats.

### Why distinguish bot-blocked URLs from real failures in Layer 3?

Layer 3 issues parallel HEAD requests against every source URL. HTTP 403 (Forbidden), 401 (Unauthorized), and 429 (Too Many Requests) responses are systematically returned by bot-detection systems on sites like Medium, Wikipedia, and market research paywalls — the page exists and the URL is valid, but the server refuses automated access. Treating these the same as 404 (Not Found) or connection errors would cause every audit to exit non-zero even when all sources are real, creating constant noise and making CI integration impractical.

**The distinction:**
- **Bot-blocked (403/401/429):** `bot_blocked: True` in `UrlCheckResult`. Shown in a separate `BOT-BLOCKED` section. Do not affect exit code. These are informational — the source is plausible but unverifiable by crawler.
- **Real failures (404, 410, timeout, connection error):** Shown in `FAILURES`. Exit code 1. These indicate a genuinely broken or non-existent URL that should be investigated.

This is set in `_check_url()` in `url_checker.py` and stored in the `UrlCheckResult.bot_blocked` field so downstream tooling (e.g. CI, metrics) can distinguish the two categories programmatically.

### Why Programmatic Tool Calling (PTC) for Round 1 and Round 2?

Previously, modules ran via `ThreadPoolExecutor` with a 5-second stagger between Round 2 submissions to stay under the 30k input tokens/minute rate limit. This added ~30 seconds of dead time per run and still caused 429 errors under load.

**PTC eliminates the stagger.** `ClaudeClient.run_ptc_round()` uses direct tool calling:

1. A single `messages.create()` call defines an `analyze_module` tool (with `module_name` as the only parameter) and instructs the orchestrating Claude to call it once for **every** module in a single response.
2. The API returns batched `tool_use` blocks — one per module — all in one response.
3. Our server dispatches them in parallel via `ThreadPoolExecutor`, captures `ModuleOutput` objects server-side, and returns a slim `"ok"` acknowledgement per tool call.
4. Module outputs never enter the orchestrating Claude's message context, so they contribute zero tokens to the rate-limit counter.
5. If the orchestrator misses any modules, the loop continues until it returns `end_turn`.

**Measured results** (n=10 runs each, `--auto-select`, Tavily search enabled, ~7–8 modules per run):

| Metric | pre-PTC (main) | PTC (feature/ptc) | Δ |
|--------|---------------|-------------------|---|
| round2_s | 98.9s ± 10.3s | 80.8s ± 15.4s | **−18%** |
| round1_s | 40.5s ± 8.0s | 48.2s ± 6.8s | +19% |
| total_s | 165.1s ± 15.5s | 151.7s ± 20.4s | **−8%** |
| ptc_orch_input_tok | 0 | 3,414 ± 457 | new |
| total_input_tok | 93,746 ± 10,222 | 85,247 ± 14,093 | −9% |
| source_survival_pct | 76% ± 3% | 81% ± 3% | +6% |
| L3 URL ok | 91% ± 2% | 91% ± 3% | = |

Round 2 savings are real but bounded by Tavily network I/O (~5–10s/module): with search active, network latency dominates over the eliminated 5s stagger. Without search the stagger was the bottleneck and Round 2 drops ~51%. Round 1 is slightly slower (+19%) due to the orchestrator round-trip overhead (~7s). Quality metrics (source survival, URL reachability, conflicts) are unchanged.

**Other effects:**
- Module outputs (R1, R2) stay off the orchestrating context → lower rate-limit exposure regardless of module count
- Synthesis (Round 3) is a single direct `client.analyze()` call, unchanged
- Deep research uses its own `ThreadPoolExecutor`, unchanged
- Individual module failures are caught per-tool and logged; the round continues with the successful subset

The orchestrator's `max_tokens=512` keeps its own cost negligible — it only needs to emit tool calls, not analysis.

### Why is Langfuse observability optional, and how does it degrade gracefully?

`src/observability.py` provides LLM call tracing (token counts, latency, cost) via Langfuse's hosted dashboard using their SDK v3 (OTEL-based). The integration is deliberately optional so that:

- **No forced dependency** — users who don't need tracing don't install `langfuse` or `opentelemetry-instrumentation-anthropic`. Core `requirements.txt` is unchanged.
- **Zero runtime impact without keys** — `observability.setup()` is called once in `main()` after `load_dotenv()`. If `LANGFUSE_PUBLIC_KEY` or `LANGFUSE_SECRET_KEY` are missing, or if the optional packages aren't installed, `_enabled` stays `False` and all functions (`trace()`, `span()`, `get_otel_context()`) become silent no-ops via early-return context managers. No exceptions, no log noise.
- **Auto-instrumentation** — `AnthropicInstrumentor().instrument()` patches `anthropic.Anthropic().messages.create()` at the OTEL level, so every API call is automatically captured as a Langfuse generation (model, prompt, response, token counts) without any changes to call sites.

**Trace hierarchy produced when keys are set:**

```
Trace: "mediated-reasoning" [input=problem, metadata={run_label, model, modules}]
├── Span: "auto-select"       (if --auto-select)
├── Span: "round-1"
│   ├── Generation: ptc-orchestrator call  (auto-captured)
│   └── Generation: module:market / tech / …  (auto-captured per thread)
├── Span: "round-2"
│   └── …
├── Span: "synthesis"
└── Span: "deep-research"     (if --deep-research)
```

**Thread context propagation:** `run_ptc_round()` dispatches module calls via `ThreadPoolExecutor`. OTEL context (the active span) does not propagate to worker threads automatically. Before submitting work, `observability.get_otel_context()` captures the current context; `_with_otel_ctx(ctx, fn, ...)` re-attaches it inside each worker using `otel_context.attach(token)` / `detach(token)`. This ensures module generations are correctly nested under their round span rather than appearing as disconnected root spans.

### Why repeat synthesis and auto-select prompts by default?

In causal language models, attention is unidirectional: each token can only attend to tokens that appear *before* it in the sequence. A synthesis prompt is structured as:

```
[module analyses …4–5K tokens…] [JSON schema + output instructions ~500 tokens]
```

The module analyses (the bulk of the input) are processed before the model sees the JSON schema. By the time the model reads the schema, it cannot revisit the analyses with full schema-awareness. The schema tokens, however, *can* attend to the analyses. This asymmetry means the output format often has more influence over the response than the substantive content.

**Prompt repetition** (arxiv 2512.14982) fixes this by appending the entire user prompt a second time:

```
[module analyses][schema][module analyses][schema]
```

On the second pass, every analysis token attends to all prior tokens — including the schema from the first pass. The model effectively "re-reads" the context knowing exactly what structure it must produce. The paper reports improvements on 47/70 benchmarks with zero regressions; the technique adds only prefill tokens (no extra generation required).

Applied here to **synthesis** (~4–6K user tokens, largest single call) and **auto-select/gap-check** (~750–1200 tokens each). Module R1/R2 calls are excluded — doubling already-large R2 prompts (~6K × up to 8 modules) would create significant rate-limit exposure with lower expected gain since module calls have simpler, more regular schemas.

**Benchmark results** (fixed 3-module runs, single comparison):

| Metric | baseline | `--repeat-prompt` | Δ |
|--------|----------|-------------------|---|
| total_input_tok | 35,318 | 37,920 | +7.4% |
| total_output_tok | 6,633 | 7,182 | +8.3% |
| sources_survived | 27 | 30 | +11.1% |
| source_survival_pct | 75% | 81% | +8pp |
| flags_red/yellow | unchanged | unchanged | = |
| conflicts_total | unchanged | unchanged | = |

The +11% source survival improvement (the model cites more real, verifiable URLs rather than hallucinated ones) at +7.4% token cost is the primary quality signal. The feature is on by default; use `--no-repeat-prompt` to disable.

### Why a structural quality gate instead of an LLM self-assessment?

After a run completes, the user has no signal about whether that run is trustworthy — a run with 2 hallucinated sources and 4 red flags looks identical to one with 30 real sources and 1 yellow flag. The quality gate addresses this by computing a score from metrics that are already available, deterministic, and already proven to correlate with output quality across benchmarks.

**Why not ask the LLM to rate its own output?** LLM self-assessment is unreliable for the same reason confidence scores are: models are miscalibrated and can be confidently wrong. A structural signal derived from objective facts (did sources survive URL validation? did modules complete?) is more trustworthy than a model's introspective rating.

**Scoring logic** (`src/audit/quality_gate.py` — no LLM calls, pure metrics):

| Signal | Condition | Penalty |
|--------|-----------|---------|
| Module failures | per failed module | −0.30 each |
| Source survival | <50% of claimed sources had real URLs | −0.30 |
| Source survival | <70% | −0.10 |
| Grounding depth | <5 sources survived | −0.20 |
| Critical flag density | ≥4 red flags | −0.10 |

Tiers: **good** (≥0.8), **degraded** (≥0.5), **poor** (<0.5). Thresholds are derived from observed benchmark data where good runs consistently show 75–84% source survival and 27–37 survived sources.

**Integration point:** called at the end of `mediator.analyze()` after all consolidation is done — `result.quality = evaluate(result)` — so `RunQuality` is always populated before the result reaches the caller. Degraded/poor tiers emit a logger warning. The formatter prints the tier in color at the bottom of every output. The gate does not block or re-run — a degraded run is still informative, it just tells the user *why* to calibrate their confidence accordingly.

### Resolved questions
- **Sequential vs parallel execution within a round:** Modules run in parallel within each round. R1 and R2 use PTC (`run_ptc_round()`); deep research uses `ThreadPoolExecutor` directly. Both approaches dispatch all work simultaneously and collect results as they complete.

## Design Principles

1. **Modularity** — Each module is independent and can be developed, tested, and modified separately
2. **Transparency** — All module outputs are visible; the system shows its reasoning
3. **Iterative Refinement** — The 3-round process allows modules to adjust based on cross-module insights
4. **Conflict Detection** — The mediator explicitly surfaces disagreements between modules
5. **Actionable Output** — Final analysis includes clear recommendations with priority flags (red/yellow/green)
6. **Local-first testing** — Whenever possible, test with mocked API clients (`pytest`) before running live API calls. Unit tests should cover logic, formatting, schema validation, and prompt construction without spending API credits. Reserve live runs for end-to-end verification only.

## Planned: Intelligent Delegation Extensions

The following features are inspired by *"Intelligent AI Delegation"* (Tomašev, Franklin, Osindero — Google DeepMind, 2025; https://arxiv.org/html/2602.11865v1). That paper proposes a comprehensive framework for multi-agent delegation covering dynamic assessment, adaptive execution, structural transparency, scalable coordination, and systemic resilience. Three of its core ideas map directly to improvements for mediated-reasoning:

### 14. Adaptive Module Selection (Implemented)

**Paper concept:** *Dynamic Assessment* — before delegating, the delegator evaluates which agents have relevant expertise for the task at hand, rather than broadcasting to everyone.

**Implementation:** The `--auto-select` flag runs a two-step LLM pre-pass: (1) selects 3–7 relevant modules from a pool of 12, (2) checks for coverage gaps and creates up to 3 ad-hoc modules with LLM-generated system prompts. Without the flag, the 3 default modules (market, cost, risk) run as before. Weight=0 vetoes auto-selected modules. Falls back to defaults if the pre-pass fails.

### 15. Runtime Re-delegation on Failure

**Paper concept:** *Adaptive Execution* — switch delegatees mid-task when performance degrades, rather than accepting a gap in coverage.

**Current behavior:** If a module's API call fails in Round 1, it is silently skipped (`mediator.py` logs the error and moves on). The remaining modules carry on with a blind spot.

**Proposed:** When a module fails, the mediator retries it — possibly with a different prompt variation, a fallback model, or by redistributing its concerns to a related module (e.g. asking scalability to also cover technical feasibility if tech fails). This ensures the final synthesis doesn't have unacknowledged gaps.

### 16. Per-Module Trust Scores

**Paper concept:** *Trust and Reputation* — the paper distinguishes trust (private, context-dependent delegator belief about an agent's reliability) from reputation (public, verifiable performance history). Both are used to dynamically adjust how much influence each agent has.

**Current behavior:** All modules start with equal credibility. `--weight` is a static, user-supplied knob with no memory across runs.

**Proposed:** Track each module's historical reliability — e.g. how often its flags were validated in synthesis, how often its analysis was contradicted, how specific vs. vague its outputs are — and use that to automatically adjust module influence over time. A module that consistently produces vague or contradicted analysis would get downweighted without the user needing to manually set `--weight`. Requires persistence (local DB or JSON file) to track run history across sessions.

## Token Optimization

Token costs break down as follows (mean, ~8 modules, Tavily enabled):

| Round | Estimated tokens | Driver |
|-------|-----------------|--------|
| R1 | ~23k | 8 × (system prompt + search context) |
| **R2** | **~46k** | 8 × (system prompt + search context + all other modules' full R1 outputs) |
| R3 synthesis | ~13k | system prompt + all 16 outputs + global sources |

**R2 is the dominant cost** because each module receives every other module's full `analysis` dict as cross-module context. With 8 modules, that is 7 full analysis objects per prompt × 8 prompts = 56 redundant analysis payloads per run.

### 19. Slim R2 Cross-Module Context (Implemented)

**Problem:** `_format_round1_outputs()` serialises the complete `analysis` dict (summary, key_findings, opportunities, risks, and all other fields) for every other module. A module revising its perspective only needs to know *what the other modules concluded* and *what they flagged* — not the full structured breakdown.

**Implementation:** Added `brief=True` parameter to `_format_round1_outputs`. When `brief=True`, only `summary` and `flags` are included per module. `build_round2_prompt` passes `brief=True` for other modules' outputs. The synthesis prompt still receives full outputs because it needs the complete picture to identify conflicts.

**Expected saving:** ~50–60% reduction in R2 cross-module payload → estimated −15k to −20k total input tokens per run (−18–25%).

### 20. Shared Search Query Cache (Implemented)

**Problem:** Each module independently generates queries and fetches results. Across 8 modules × 2 rounds = 16 `run_for_module` calls, many queries are near-identical (e.g. multiple modules asking about "WebMCP browser support"). Each duplicate query costs one search API call and returns the same results.

**Implementation:** `SearchPrePass` maintains a `_query_cache: Dict[str, List[SearchResult]]` keyed by exact query string. In `_fetch_results`, each query is checked against the cache before calling the search backend. Cache hits return stored results immediately; cache misses store results before returning. The cache lives for the lifetime of the `SearchPrePass` instance (one per `mediator.analyze()` call), so it is shared across all modules and both rounds.

**Expected saving:** Eliminates duplicate search calls regardless of backend. Also reduces Tavily quota consumption when Tavily is in use. Token savings are indirect (fewer `analyze` calls for query generation if query generation is also cached — but currently only the search fetch is cached, not the LLM query generation step).

### 21. Model Tiering — `--module-model` flag (Implemented)

Use a cheaper/faster model for R1/R2 module calls and `claude-sonnet-4-6` only for synthesis, auto-select, gap-check, and PTC orchestration. Enabled via `--module-model claude-haiku-4-5-20251001`.

Token tracking is split: `module_analyze_input/output` tracks module-client calls; `synthesis_analyze_input/output` tracks synthesis-client calls.

**Verbosity problem and two levers to fix it:**

Haiku without constraints generates ~3× more output tokens per module call than Sonnet. Root causes: (1) no per-array item limit in the JSON schema, (2) `max_tokens=4096` gives too much room. Two levers were added:

- **Lever A — `max_tokens` per client**: `ClaudeClient.__init__` accepts `max_tokens: int = 4096`. Module client is created with `max_tokens=2048` when `--module-model` is set. This caps per-call output and reduces Haiku rate-limit exposure.
- **Lever B — conciseness instruction**: `_module_json_instruction()` appends `"CONCISENESS: Maximum 5 items per array. One sentence per item. Omit minor points."` to every module prompt. Applies to all models; keeps Haiku focused.

**Benchmarks (WebMCP browser standard, with search):**

| Label | n | module_out_tok | total_s | modules_completed |
|-------|---|----------------|---------|-------------------|
| Sonnet (ptc) | 10 | ~15k | 151.7s ± 20s | 7.0 ± 1.2 |
| Haiku (unconstrained) | 5 | 44,771 ± 3,188 | 236.2s ± 44.8s | 7.8 ± 0.4 |
| Haiku (compact, max_tokens=2048 + conciseness) | 5 | ~22k | ~105s | 7.4 ± 1.1 |

Compact Haiku halves module output tokens vs unconstrained (~22k vs 44k) and cuts wall time from 236s to ~105s. Still ~30% slower than Sonnet due to Haiku's 10k output tokens/min org rate limit.

**Cost math (approximate Anthropic pricing):**

| | Module output tokens | Output price/MTok | Relative cost |
|---|---|---|---|
| Sonnet modules | ~15k | $15 | 1× |
| Haiku compact modules | ~22k | $4 | **0.59×** |

Haiku compact module calls are ~40% cheaper than Sonnet. But the rate-limit penalty makes total runs ~30% slower, so the trade-off only makes sense if cost matters more than latency.

**When Haiku makes sense:**
- Higher-tier rate limit (50k+ output tokens/min) — speed penalty disappears
- Fewer modules (3–4 via `--weight`) — output tokens per run stay under the 10k/min limit
- Batch/async workloads — latency doesn't matter, 40% cost saving is real

**Conclusion:** For interactive use with `--auto-select` (8 modules), Sonnet is faster and more reliable. The `--module-model` flag is worth keeping: compact Haiku is genuinely cheaper per run, and a higher rate limit would make it strictly better.
