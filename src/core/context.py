from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlatformContext:
    """
    平台共用上下文。
    所有 Workflow、Skill 都透過這個物件交換資料。
    """

    input: dict = field(default_factory=dict)
    memory: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def get(self, section: str, key: str, default: Any = None) -> Any:
        if not hasattr(self, section):
            raise ValueError(f"未知 context 區塊：{section}")

        return getattr(self, section).get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        if not hasattr(self, section):
            raise ValueError(f"未知 context 區塊：{section}")

        getattr(self, section)[key] = value

    def to_dict(self) -> dict:
        return {
            "input": self.input,
            "memory": self.memory,
            "output": self.output,
            "metadata": self.metadata,
        }
