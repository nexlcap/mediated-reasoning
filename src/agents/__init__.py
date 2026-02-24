from .market_agent import MarketAgent
from .cost_agent import CostAgent
from .risk_agent import RiskAgent
from .legal_agent import LegalAgent
from .tech_agent import TechAgent
from .scalability_agent import ScalabilityAgent

AGENT_REGISTRY = [
    MarketAgent,
    CostAgent,
    RiskAgent,
    LegalAgent,
    TechAgent,
    ScalabilityAgent,
]

__all__ = [
    "MarketAgent",
    "CostAgent",
    "RiskAgent",
    "LegalAgent",
    "TechAgent",
    "ScalabilityAgent",
    "AGENT_REGISTRY",
]
