import json
from pathlib import Path


class PlatformContext:
    def __init__(self):
        self.data = {
            "input": {},
            "memory": {},
            "output": {},
            "metadata": {}
        }

    def get(self, section: str, key: str, default=None):
        return self.data.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value):
        if section not in self.data:
            self.data[section] = {}
        self.data[section][key] = value

    def to_dict(self):
        return self.data

    @classmethod
    def from_dict(cls, data: dict):
        context = cls()
        context.data = data
        return context

    def save_json(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load_json(cls, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
