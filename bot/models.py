from dataclasses import dataclass, field
from typing import Any


@dataclass
class Action:
    text: str
    callback_data: str | None = None
    key: str = ""


@dataclass
class GameState:
    raw_text: str = ""
    location: str = "unknown"
    current_action: str = "unknown"
    available_actions: list[Action] = field(default_factory=list)
    self_data: dict[str, Any] = field(default_factory=dict)
    enemy_data: dict[str, Any] = field(default_factory=dict)
    inventory: dict[str, int] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)


@dataclass
class Experience:
    state_before: str
    action: str
    state_after: str
    reward: float
    timestamp: float
