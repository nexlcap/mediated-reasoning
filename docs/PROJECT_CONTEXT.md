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

class FinalAnalysis(BaseModel):
    problem: str
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
    search_enabled: bool                # Whether Tavily web search was active for this run
    conflict_resolutions: List[ConflictResolution] # Populated when --deep-research is used
    deep_research_enabled: bool         # Whether the deep research round ran
    search_context: Optional[SearchContext] # Raw search results from the pre-pass (queries + results)

class SearchResult(BaseModel):
    title: str                  # Page title
    url: str                    # Canonical URL (used for deduplication)
    content: str                # Snippet/summary from Tavily

class SearchContext(BaseModel):
    queries: List[str]          # LLM-generated search queries
    results: List[SearchResult] # Deduplicated results (capped at 12)
    # format_for_prompt() serialises results as numbered [N] context block

class AdHocModule(BaseModel):
    name: str                   # e.g. "cultural"
    system_prompt: str          # LLM-generated system prompt

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
│   │   └── searcher.py         # SearchPrePass — query gen + Tavily fetch
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
│   │   └── consistency_checker.py # Layer 5 — R1→R2 new-fact detection (Haiku)
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
│   └── test_audit.py          # Audit layers 1 & 2 tests
├── docs/
├── .env.example
└── requirements.txt
```

## Tech Stack

- **Language:** Python 3.11+
- **Environment:** Conda
- **LLM:** Claude (Anthropic API)
- **Libraries:**
  - `anthropic` — API client
  - `pydantic` — Data validation and schemas
  - `python-dotenv` — Environment variable management
  - `pytest` — Testing
  - `tavily-python` — Web search API client for grounded source pre-pass
  - `httpx` — HTTP client for URL reachability checks and source page fetching (audit layers 3 & 4)

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
| `--no-search` | Skip web search pre-pass; modules cite from training knowledge only (no Tavily call) |
| `--deep-research` | After synthesis, run targeted web search on high/critical conflicts and red flags to produce evidence-based verdicts and updated recommendations |
| `--model MODEL` | Claude model to use |

### Interactive Follow-up Mode (`--interactive`)

After the initial 3-round analysis completes, `--interactive` drops the user into a REPL where they can ask follow-up questions. The mediator's `followup()` method sends the question along with the full analysis context to the LLM, so answers are grounded in the original multi-module reasoning. Type `exit`, `quit`, or send an empty line to leave.

### Structured Output Directory (`--output`)

The `--output` flag is a boolean (no filename argument). It calls `export_all()` which:
1. Slugifies the problem statement (lowercase, non-alnum → `-`, max 60 chars)
2. Creates a timestamped subdirectory: `output/<slug>/<YYYY-MM-DDTHH-MM-SS>/`
3. Writes `report.md`, `report.json`, and `report.html` into that directory

This ensures every run is preserved and easily comparable.

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
- **Fetching:** Tavily returns clean summaries and canonical URLs (designed for LLM grounding, not raw HTML). Results are capped at 8 per module per round and deduplicated by URL.
- **Injection:** Results are formatted as a numbered `[N] Title — URL\n    content` block and injected into the module's prompt. Modules are explicitly instructed to cite from those entries and copy the full URL into the sources array.

**Source consolidation:** Each module produces local source indices [1]–[N]. After all rounds complete, `_consolidate_sources()` merges all module sources into a global deduplicated list (by URL first, then text), remaps all inline citations to global indices, and clears per-module source lists. Before synthesis (Round 3), this global list is pre-built and injected into the synthesis prompt with a `CRITICAL` instruction to cite only from it — preventing synthesis from inventing new sources beyond what modules actually found.

**Graceful degradation:** If `TAVILY_API_KEY` is missing, the package is not installed, or any Tavily call fails, that module's search is silently skipped and the module falls back to training-knowledge citations. `--no-search` disables all search explicitly.

### Why a post-synthesis deep research round (`--deep-research`)?
After synthesis, the framework has identified conflicts and red flags but no mechanism to actually *resolve* them with evidence. The deep research round (`--deep-research`) addresses this: for every `high`/`critical` severity conflict and every `red:` priority flag not already covered by a conflict, the mediator runs a targeted research task in parallel:

1. **Query generation** — Claude generates 3–4 queries specifically aimed at resolving that conflict (e.g. "WebMCP API DevTrial stability guarantees" for an API-stability conflict)
2. **Evidence fetch** — Tavily returns fresh, current results
3. **Resolution LLM call** — receives the conflict description, both module positions, and fresh evidence; produces a `verdict` (which position evidence supports) and an `updated_recommendation` (more specific than the synthesis-level recommendations)

Resolution sources are consolidated into the global source list using the same URL-deduplication logic as module sources. The mediator handles this itself (not delegating back to modules) because conflicts are cross-domain by definition — no single domain module "owns" a cross-module disagreement. `--deep-research` is opt-in because each conflict triggers ~5 additional API calls (1 query gen + 3–4 Tavily fetches + 1 resolution LLM call).

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
- **Cross-module amplification** — If a Round 1 module makes an uncited claim, Round 2 modules see it as "context" and may treat it as established fact, amplifying the error. The system has no mechanism to flag claims that originate from a module's own output rather than an external source.

### Why a dedicated `deactivated_disclaimer` field?
When modules are deactivated via `--weight module=0`, the synthesis must include a disclaimer noting their absence. Initially this was a free-text instruction in the prompt ("you MUST include a disclaimer..."), but the LLM consistently ignored it — especially when other modules partially covered the deactivated module's domain. Adding `deactivated_disclaimer` as a required field in the JSON schema forces the LLM to populate it, making the disclaimer reliable rather than discretionary.

### Why structured Conflict objects instead of free-text?
Conflicts were originally extracted as free-text strings in the synthesis prompt. This made them inconsistent — sometimes a paragraph, sometimes a bullet point, with no reliable way to identify which modules disagreed or how severe the conflict was. Switching to structured `Conflict` objects (`modules`, `topic`, `description`, `severity`) forces the LLM to produce machine-readable, consistent conflict data that can be filtered, sorted, and rendered uniformly across export formats.

### Resolved questions
- **Sequential vs parallel execution within a round:** Modules run in parallel within each round using `ThreadPoolExecutor`. Since modules are independent within a round, this cuts wall-clock time from sequential API calls to parallel batches (R1 parallel + R2 parallel + synthesis).

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
