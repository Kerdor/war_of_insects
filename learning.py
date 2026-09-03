import json
import random
from pathlib import Path


class QLearning:
    def __init__(self, path: str = "data/q_values.json", alpha: float = 0.2, gamma: float = 0.95):
        self.path = Path(path)
        self.alpha = alpha
        self.gamma = gamma
        self.values = {}
        self.visits = {}
        self._load()

    def get(self, state: str, action: str) -> float:
        return float(self.values.get(state, {}).get(action, 0.0))

    def choose(self, state: str, actions: list[str], epsilon: float, transitions=None) -> str:
        if not actions:
            raise ValueError("No available actions")

        if random.random() < epsilon:
            return random.choice(actions)

        scores = []
        for action in actions:
            value = self.get(state, action)
            visits = self.visits.get(state, {}).get(action, 0)
            exploration_bonus = 1.0 / (1.0 + visits) ** 0.5
            model_bonus = 0.0

            if transitions is not None:
                prediction = transitions.predict(state, action)
                if prediction is not None:
                    _, predicted_reward = prediction
                    model_bonus = 0.25 * predicted_reward

            scores.append(value + exploration_bonus + model_bonus)

        best = max(scores)
        candidates = [action for action, score in zip(actions, scores) if score == best]
        return random.choice(candidates)

    def update(self, state: str, action: str, reward: float, next_state: str, next_actions: list[str]) -> None:
        current = self.get(state, action)
        future = max((self.get(next_state, item) for item in next_actions), default=0.0)
        target = reward + self.gamma * future
        self.values.setdefault(state, {})[action] = current + self.alpha * (target - current)
        self.visits.setdefault(state, {})[action] = self.visits.setdefault(state, {}).get(action, 0) + 1
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "values": self.values,
            "visits": self.visits,
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if "values" in data:
            self.values = data.get("values", {})
            self.visits = data.get("visits", {})
        else:
            self.values = data
            self.visits = {}
