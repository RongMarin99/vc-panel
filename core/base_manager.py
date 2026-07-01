from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Callable
from pathlib import Path


@dataclass
class VersionInfo:
    version: str
    installed: bool = False
    active: bool = False
    install_path: Optional[Path] = None
    release_date: Optional[str] = None


class BaseManager(ABC):
    name: str
    display_name: str

    def __init__(self, versions_root: Path):
        self.versions_root = versions_root / self.name
        self.versions_root.mkdir(parents=True, exist_ok=True)

    def install_path(self, version: str) -> Path:
        return self.versions_root / version

    def is_installed(self, version: str) -> bool:
        return self.install_path(version).exists()

    @abstractmethod
    def list_remote(self) -> list[VersionInfo]: ...

    @abstractmethod
    def list_installed(self) -> list[VersionInfo]: ...

    @abstractmethod
    def install(self, version: str, progress_callback: Optional[Callable] = None) -> bool: ...

    @abstractmethod
    def uninstall(self, version: str) -> bool: ...

    @abstractmethod
    def use(self, version: str) -> bool: ...

    @abstractmethod
    def current(self) -> Optional[str]: ...

    @abstractmethod
    def get_binary_path(self, version: str) -> Optional[Path]: ...
