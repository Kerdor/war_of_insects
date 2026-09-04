import json
from pathlib import Path


class LearningStats:
    def __init__(self, path: str = "data/stats.json"):
        self.path = Path(path)
        self.data = {
            "steps": 0,
            "episodes": 0,
            "victories": 0,
            "defeats": 0,
            "total_reward": 0.0,
            "accounts": {},
        }
        self._load()

    def record_step(self, account_id: str, reward: float) -> None:
        self.data["steps"] += 1
        self.data["total_reward"] += reward
        account = self.data["accounts"].setdefault(account_id, {
            "steps": 0,
            "episodes": 0,
            "victories": 0,
            "defeats": 0,
            "reward": 0.0,
        })
        account["steps"] += 1
        account["reward"] += reward
        self.save()

    def record_episode(self, account_id: str, outcome: str) -> None:
        self.data["episodes"] += 1
        if outcome == "victory":
            self.data["victories"] += 1
        elif outcome == "defeat":
            self.data["defeats"] += 1

        account = self.data["accounts"].setdefault(account_id, {
            "steps": 0,
            "episodes": 0,
            "victories": 0,
            "defeats": 0,
            "reward": 0.0,
        })
        account["episodes"] += 1
        if outcome == "victory":
            account["victories"] += 1
        elif outcome == "defeat":
            account["defeats"] += 1
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.data.update(data)
