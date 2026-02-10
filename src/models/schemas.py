from typing import Dict, List
from pydantic import BaseModel, Field


class ModuleOutput(BaseModel):
    module_name: str
    round: int
    analysis: Dict = Field(default_factory=dict)
    flags: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    revised: bool = False


class FinalAnalysis(BaseModel):
    problem: str
    module_outputs: List[ModuleOutput] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    synthesis: str = ""
    recommendations: List[str] = Field(default_factory=list)
    priority_flags: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    deactivated_disclaimer: str = ""
