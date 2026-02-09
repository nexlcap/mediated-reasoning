from .market_module import MarketModule
from .tech_module import TechModule
from .cost_module import CostModule
from .legal_module import LegalModule
from .scalability_module import ScalabilityModule

MODULE_REGISTRY = [
    MarketModule,
    TechModule,
    CostModule,
    LegalModule,
    ScalabilityModule,
]

__all__ = [
    "MarketModule",
    "TechModule",
    "CostModule",
    "LegalModule",
    "ScalabilityModule",
    "MODULE_REGISTRY",
]
