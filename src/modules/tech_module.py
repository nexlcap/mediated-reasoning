from src.modules.base_module import BaseModule


class TechModule(BaseModule):
    @property
    def name(self) -> str:
        return "tech"
