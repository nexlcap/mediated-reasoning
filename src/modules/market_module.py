from src.modules.base_module import BaseModule


class MarketModule(BaseModule):
    @property
    def name(self) -> str:
        return "market"
