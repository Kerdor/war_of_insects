import json
import random
from pathlib import Path


class StrategyMemory:
    def __init__(self, path: str = "data/strategy.json"):
        self.path = Path(path)
        self.data = {}
        self._load()

    def record(self, target: str, action: str, reward: float, outcome: str) -> None:
        target = target or "unknown"
        action = action or "unknown"
        bucket = self.data.setdefault(target, {}).setdefault(action, {
            "count": 0,
            "reward": 0.0,
            "victories": 0,
            "defeats": 0,
        })
        bucket["count"] += 1
        bucket["reward"] += reward
        if outcome == "victory":
            bucket["victories"] += 1
        elif outcome == "defeat":
            bucket["defeats"] += 1
        self.save()

    def score(self, target: str, action: str) -> float:
        bucket = self.data.get(target or "unknown", {}).get(action or "unknown")
        if not bucket or bucket.get("count", 0) <= 0:
            return 0.0
        count = bucket["count"]
        average_reward = bucket.get("reward", 0.0) / count
        win_rate = bucket.get("victories", 0) / count
        loss_rate = bucket.get("defeats", 0) / count
        return average_reward + 10.0 * win_rate - 10.0 * loss_rate

    def choose(self, target: str, actions: list[str], epsilon: float) -> str | None:
        if not actions:
            return None
        if random.random() < epsilon:
            return random.choice(actions)
        scores = {action: self.score(target, action) for action in actions}
        best = max(scores.values())
        candidates = [action for action, score in scores.items() if score == best]
        return random.choice(candidates)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")

    def _load(self) -> None:
        if not self.path.exists():
            return
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
