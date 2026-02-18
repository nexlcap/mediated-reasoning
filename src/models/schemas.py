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


class AuditSummary(BaseModel):
    layer1_passed: bool = True
    layer1_violations: List[str] = Field(default_factory=list)
    layer2_passed: bool = True
    layer2_violations: List[str] = Field(default_factory=list)
    layer3_total: int = 0
    layer3_ok: int = 0
    layer3_failures: List[UrlCheckResult] = Field(default_factory=list)


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
