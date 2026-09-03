import json
import math
import random
from pathlib import Path


class QLearning:
    def __init__(self, path: str = "data/q_values.json", alpha: float = 0.2, gamma: float = 0.95):
        self.path = Path(path)
        self.alpha = alpha
        self.gamma = gamma
        self.values = {}
        self._load()

    def get(self, state: str, action: str) -> float:
        return float(self.values.get(state, {}).get(action, 0.0))

    def choose(self, state: str, actions: list[str], epsilon: float) -> str:
        if not actions:
            raise ValueError("No available actions")
        if random.random() < epsilon:
            return random.choice(actions)
        values = [self.get(state, action) for action in actions]
        best = max(values)
        candidates = [action for action, value in zip(actions, values) if value == best]
        return random.choice(candidates)

    def update(self, state: str, action: str, reward: float, next_state: str, next_actions: list[str]) -> None:
        current = self.get(state, action)
        future = max((self.get(next_state, item) for item in next_actions), default=0.0)
        target = reward + self.gamma * future
        self.values.setdefault(state, {})[action] = current + self.alpha * (target - current)
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.values, ensure_ascii=False), encoding="utf-8")

    def _load(self) -> None:
        if self.path.exists():
            self.values = json.loads(self.path.read_text(encoding="utf-8"))
