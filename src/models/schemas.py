from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    title: str
    url: str
    content: str


class SearchContext(BaseModel):
    queries: List[str]
    results: List[SearchResult]

    def format_for_prompt(self) -> str:
        lines = ["Grounded Research Context (cite these real sources using [N] notation):"]
        for i, r in enumerate(self.results, 1):
            lines.append(f"[{i}] {r.title} — {r.url}\n    {r.content}")
        return "\n".join(lines)


class AdHocModule(BaseModel):
    name: str
    system_prompt: str


class SelectionMetadata(BaseModel):
    auto_selected: bool = False
    selected_modules: List[str] = Field(default_factory=list)
    selection_reasoning: str = ""
    gap_check_reasoning: str = ""
    ad_hoc_modules: List[AdHocModule] = Field(default_factory=list)


class ModuleOutput(BaseModel):
    module_name: str
    round: int
    analysis: Dict = Field(default_factory=dict)
    flags: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    revised: bool = False


class Conflict(BaseModel):
    modules: List[str]
    topic: str
    description: str
    severity: Literal["critical", "high", "medium", "low"]


class ConflictResolution(BaseModel):
    topic: str                      # conflict topic or red flag text
    modules: List[str]              # modules involved; empty for standalone red flags
    severity: str                   # "high"/"critical" for conflicts, "red" for flags
    verdict: str                    # evidence-based finding
    updated_recommendation: str     # concrete action given the verdict
    sources: List[str] = Field(default_factory=list)  # local sources, consolidated later


class UrlCheckResult(BaseModel):
    url: str
    status: Optional[int] = None
    error: Optional[str] = None
    ok: bool
    bot_blocked: bool = False   # True when status is 403/401/429 — URL likely exists but blocks crawlers


class GroundingResult(BaseModel):
    verdict: str        # SUPPORTED / PARTIAL / UNSUPPORTED / FETCH_FAILED / UNKNOWN
    citation: str       # e.g. "[3]"
    sentence: str       # the claim that was checked
    url: str            # source URL that was fetched


class ConsistencyResult(BaseModel):
    module: str
    ok: bool
    issues: List[str] = Field(default_factory=list)


class AuditSummary(BaseModel):
    layer1_passed: bool = True
    layer1_violations: List[str] = Field(default_factory=list)
    layer2_passed: bool = True
    layer2_violations: List[str] = Field(default_factory=list)
    layer3_total: int = 0
    layer3_ok: int = 0
    layer3_failures: List[UrlCheckResult] = Field(default_factory=list)
    layer4_ran: bool = False
    layer4_results: List[GroundingResult] = Field(default_factory=list)
    layer5_ran: bool = False
    layer5_results: List[ConsistencyResult] = Field(default_factory=list)


class TokenUsage(BaseModel):
    analyze_input: int = 0             # total analyze() tokens (module + synthesis)
    analyze_output: int = 0
    module_analyze_input: int = 0      # module calls only (Haiku when tiered)
    module_analyze_output: int = 0
    synthesis_analyze_input: int = 0   # synthesis + auto-select + gap-check (Sonnet)
    synthesis_analyze_output: int = 0
    chat_input: int = 0
    chat_output: int = 0
    ptc_orchestrator_input: int = 0
    ptc_orchestrator_output: int = 0
    total_input: int = 0
    total_output: int = 0


class RoundTiming(BaseModel):
    round1_s: float = 0.0
    round2_s: float = 0.0
    round3_s: float = 0.0
    total_s: float = 0.0


class FinalAnalysis(BaseModel):
    problem: str
    generated_at: str = ""
    module_outputs: List[ModuleOutput] = Field(default_factory=list)
    conflicts: List[Conflict] = Field(default_factory=list)
    synthesis: str = ""
    recommendations: List[str] = Field(default_factory=list)
    priority_flags: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    deactivated_disclaimer: str = ""
    raci_matrix: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    selection_metadata: Optional[SelectionMetadata] = None
    search_context: Optional[SearchContext] = None
    weights: Dict[str, float] = Field(default_factory=dict)
    search_enabled: bool = True
    conflict_resolutions: List[ConflictResolution] = Field(default_factory=list)
    deep_research_enabled: bool = False
    audit: Optional[AuditSummary] = None
    run_label: str = ""
    module_model: str = ""             # model used for module calls (empty = same as synthesis)
    token_usage: Optional[TokenUsage] = None
    timing: Optional[RoundTiming] = None
    modules_attempted: int = 0
    modules_completed: int = 0
    sources_claimed: int = 0
