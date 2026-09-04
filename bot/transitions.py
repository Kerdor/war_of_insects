import json
from collections import defaultdict
from pathlib import Path


class TransitionMemory:
    def __init__(self, path: str = "data/transitions.json"):
        self.path = Path(path)
        self.transitions = defaultdict(lambda: defaultdict(dict))
        self._load()

    def record(self, state: str, action: str, next_state: str, reward: float) -> None:
        bucket = self.transitions[state][action]
        item = bucket.setdefault(next_state, {"count": 0, "reward": 0.0})
        item["count"] += 1
        item["reward"] += reward
        self.save()

    def predict(self, state: str, action: str):
        bucket = self.transitions.get(state, {}).get(action, {})
        if not bucket:
            return None
        candidates = []
        for next_state, data in bucket.items():
            count = data.get("count", 0)
            if count <= 0:
                continue
            average_reward = data.get("reward", 0.0) / count
            candidates.append((count, next_state, average_reward))
        if not candidates:
            return None
        return max(candidates, key=lambda item: item[0])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {state: dict(actions) for state, actions in self.transitions.items()}
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for state, actions in data.items():
            for action, next_states in actions.items():
                self.transitions[state][action] = next_states
