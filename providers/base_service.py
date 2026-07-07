from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ServiceInfo:
    status: str           # "running" | "stopped" | "not_found"
    version: str | None
    port: int
    config_path: str | None
    service_key: str | None   # actual OS service name found


class BaseService(ABC):
    name: str
    display_name: str
    icon: str
    default_port: int

    @abstractmethod
    def info(self) -> ServiceInfo: ...

    @abstractmethod
    def start(self) -> bool: ...

    @abstractmethod
    def stop(self) -> bool: ...

    def restart(self) -> bool:
        import time
        self.stop()
        time.sleep(1.5)
        return self.start()

    @abstractmethod
    def get_port(self) -> int: ...

    @abstractmethod
    def set_port(self, port: int) -> bool: ...
