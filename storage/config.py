import json
from pathlib import Path
from typing import Any


class Config:
    APP_NAME = "vc"

    def __init__(self):
        self.home = Path.home() / f".{self.APP_NAME}"
        self.versions_dir = self.home / "versions"
        self.tools_dir = self.home / "tools"
        self.shims_dir = self.home / "shims"
        self.config_file = self.home / "config.json"
        self.db_path = self.home / "vc.db"

        for d in [self.versions_dir, self.tools_dir, self.shims_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self._data = self._load()

    def _load(self) -> dict:
        if self.config_file.exists():
            try:
                return json.loads(self.config_file.read_text())
            except Exception:
                pass
        return {"active_versions": {}, "projects": {}}

    def save(self):
        self.config_file.write_text(json.dumps(self._data, indent=2))

    def get_active(self, tool: str) -> str | None:
        return self._data["active_versions"].get(tool)

    def set_active(self, tool: str, version: str | None):
        if version is None:
            self._data["active_versions"].pop(tool, None)
        else:
            self._data["active_versions"][tool] = version
        self.save()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value
        self.save()
