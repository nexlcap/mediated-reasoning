from .market_module import MarketModule
from .cost_module import CostModule
from .risk_module import RiskModule

MODULE_REGISTRY = [
    MarketModule,
    CostModule,
    RiskModule,
]

__all__ = [
    "MarketModule",
    "CostModule",
    "RiskModule",
    "MODULE_REGISTRY",
]
