from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


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


class FinalAnalysis(BaseModel):
    problem: str
    module_outputs: List[ModuleOutput] = Field(default_factory=list)
    conflicts: List[Conflict] = Field(default_factory=list)
    synthesis: str = ""
    recommendations: List[str] = Field(default_factory=list)
    priority_flags: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    deactivated_disclaimer: str = ""
    raci_matrix: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    selection_metadata: Optional[SelectionMetadata] = None
