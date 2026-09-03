import json
import time
from pathlib import Path


class ExperienceMemory:
    def __init__(self, path: str = "data/experiences.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, account_id: str, state_before: str, action: str, state_after: str, reward: float) -> None:
        item = {
            "timestamp": time.time(),
            "account_id": account_id,
            "state_before": state_before,
            "action": action,
            "state_after": state_after,
            "reward": reward,
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")
