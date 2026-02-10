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
│ Market │      │  Tech  │      │  Cost  │
│ Module │      │ Module │      │ Module │
└────────┘      └────────┘      └────────┘
    │                │                │
    ▼                ▼                ▼
┌────────┐      ┌────────┐
│ Legal  │      │ Scale  │
│ Module │      │ Module │
└────────┘      └────────┘
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

Five specialized expert modules, each focused on one dimension:

### Market Fit Module
- Market size and opportunity
- Competitive landscape
- Customer demand validation
- Product-market fit assessment

### Technical Feasibility Module
- Technology stack requirements
- Implementation complexity
- Development timeline
- Technical risks and dependencies

### Cost Analysis Module
- Initial investment needed
- Operating costs
- Revenue projections
- Break-even analysis
- Funding requirements

### Legal/Compliance Module
- Regulatory requirements
- Legal risks
- Compliance needs
- Liability concerns

### Scalability Module
- Growth potential
- Infrastructure scaling
- Team scaling
- Operational complexity at scale

## Data Models

Pydantic schemas for structured outputs:

```python
class ModuleOutput(BaseModel):
    module_name: str
    round: int
    analysis: Dict
    flags: List[str]
    revised: bool

class FinalAnalysis(BaseModel):
    problem: str
    module_outputs: List[ModuleOutput]
    conflicts: List[str]
    synthesis: str
    recommendations: List[str]
    priority_flags: List[str]  # Red/yellow flags
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
│   │   ├── base_module.py      # Base class for all reasoning modules
│   │   ├── market_module.py    # Market fit analysis
│   │   ├── tech_module.py      # Technical feasibility
│   │   ├── cost_module.py      # Financial analysis
│   │   ├── legal_module.py     # Legal/compliance analysis
│   │   └── scalability_module.py # Growth/scaling potential
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py           # LLM API wrapper (Claude)
│   │   └── prompts.py          # Prompt templates per module
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py          # Pydantic models for outputs
│   │   └── types.py            # Type definitions
│   └── utils/
│       ├── __init__.py
│       ├── logger.py           # Logging
│       └── formatters.py       # Output formatting
├── tests/
│   ├── test_mediator.py
│   ├── test_modules.py
│   └── test_e2e.py
├── docs/
├── .env.example
├── requirements.txt
└── README.md
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

## Use Cases

- **Startup idea validation** — Evaluate a new app/business idea across market, tech, cost, legal, and scalability dimensions
- **Meeting agenda preparation** — Structure discussions and break down agenda items into different angles
- **Strategic planning** — Analyze complex business decisions from multiple perspectives
- **Investment decisions** — Assess opportunities with structured multi-dimensional analysis
- **Technical architecture decisions** — Evaluate trade-offs across feasibility, cost, and scalability

## Design Decisions

### Why multi-agent over a single LLM call?
A single LLM call cannot adequately focus on multiple complex dimensions simultaneously. By making each module a separate LLM call focused on one aspect, each call can go deeper into its domain without being spread thin. The mediator then synthesizes cross-cutting conflicts and trade-offs that individual calls would miss.

### Why general-purpose rather than domain-specific?
The system originated from a specific use case (meeting agenda reasoning) but was deliberately broadened. The user explicitly chose a general-purpose, reusable architecture over a domain-specific tool — meeting agendas were "for the start" but the design should accommodate any multi-faceted problem.

### Why these 5 modules?
The module selection was driven by the user's mental model for evaluating app/business ideas: market fit, tech feasibility, cost, and scalability. Legal/Compliance was added as a fifth module to cover a common blind spot in startup evaluation.

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

### Resolved questions
- **Sequential vs parallel execution within a round:** Modules run in parallel within each round using `ThreadPoolExecutor`. Since modules are independent within a round, this cuts wall-clock time from sequential API calls to parallel batches (R1 parallel + R2 parallel + synthesis).

## Design Principles

1. **Modularity** — Each module is independent and can be developed, tested, and modified separately
2. **Transparency** — All module outputs are visible; the system shows its reasoning
3. **Iterative Refinement** — The 3-round process allows modules to adjust based on cross-module insights
4. **Conflict Detection** — The mediator explicitly surfaces disagreements between modules
5. **Actionable Output** — Final analysis includes clear recommendations with priority flags (red/yellow/green)
