from src.modules.base_module import BaseModule


class LegalModule(BaseModule):
    @property
    def name(self) -> str:
        return "legal"
