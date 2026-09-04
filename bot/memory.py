import json
import time
import uuid
from pathlib import Path


class ExperienceMemory:
    def __init__(self, path: str = "data/experiences.jsonl", episodes_path: str = "data/episodes.jsonl"):
        self.path = Path(path)
        self.episodes_path = Path(episodes_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.episodes_path.parent.mkdir(parents=True, exist_ok=True)
        self.episodes = {}
        self.history = {}

    def add(self, account_id: str, state_before: str, action: str, state_after: str, reward: float) -> None:
        episode_id = self.episodes.setdefault(account_id, uuid.uuid4().hex)
        item = {
            "timestamp": time.time(),
            "account_id": account_id,
            "episode_id": episode_id,
            "state_before": state_before,
            "action": action,
            "state_after": state_after,
            "reward": reward,
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")
        self.history.setdefault(account_id, []).append(item)
        self.history[account_id] = self.history[account_id][-20:]

    def add_episode_outcome(self, account_id: str, state, reward: float) -> None:
        episode_id = self.episodes.setdefault(account_id, uuid.uuid4().hex)
        text = state.raw_text.lower()
        outcome = "unknown"
        reason = "unknown"

        if "погиб" in text or "проиграл" in text:
            outcome = "defeat"
            reason = "death_or_loss"
        elif "все враги повержены" in text or "побежден" in text or "победил" in text:
            outcome = "victory"
            reason = "enemy_defeated"

        recent = self.history.get(account_id, [])
        item = {
            "timestamp": time.time(),
            "account_id": account_id,
            "episode_id": episode_id,
            "outcome": outcome,
            "reason": reason,
            "target": state.enemy_data.get("species") or state.enemy_data.get("name") or "unknown",
            "reward": reward,
            "steps": [
                {
                    "state_before": entry["state_before"],
                    "action": entry["action"],
                    "state_after": entry["state_after"],
                    "reward": entry["reward"],
                }
                for entry in recent
                if entry.get("episode_id") == episode_id
            ],
            "state": state.raw_text,
        }
        with self.episodes_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")

        self.episodes[account_id] = uuid.uuid4().hex
        self.history[account_id] = []
