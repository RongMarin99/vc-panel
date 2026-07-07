from storage.config import Config
from providers.php import PHPManager
from providers.node import NodeManager
from providers.python import PythonManager
from providers.java import JavaManager
from providers.dotnet import DotnetManager
from providers.go import GoManager
from providers.rust import RustManager
from core.base_manager import BaseManager


class Registry:
    def __init__(self, config: Config):
        self._managers: dict[str, BaseManager] = {
            "php":    PHPManager(config),
            "node":   NodeManager(config),
            "python": PythonManager(config),
            "java":   JavaManager(config),
            "dotnet": DotnetManager(config),
            "go":     GoManager(config),
            "rust":   RustManager(config),
        }

    def get(self, name: str) -> BaseManager | None:
        return self._managers.get(name)

    def all(self) -> dict[str, BaseManager]:
        return dict(self._managers)
