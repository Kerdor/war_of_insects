import asyncio
import json
import os
import time
import urllib.request
from typing import Any

from .knowledge_retrieval import KnowledgeRetriever
from .knowledge_writer import KnowledgeWriter


class QwenAnalyst:
    def __init__(self, retriever=None, writer=None):
        self.enabled = os.getenv("QWEN_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
        self.base_url = os.getenv("QWEN_BASE_URL", "http://localhost:11434").rstrip("/")
        self.model = os.getenv("QWEN_MODEL", "qwen3:4b").strip()
        self.interval = max(1, int(os.getenv("QWEN_ANALYSIS_INTERVAL", "1")))
        self.max_tokens = max(256, int(os.getenv("QWEN_MAX_TOKENS", "1200")))
        self.timeout = max(5, int(os.getenv("QWEN_TIMEOUT", "120")))
        self.retriever = retriever or KnowledgeRetriever()
        self.writer = writer or KnowledgeWriter()
        self._calls = {}
        self._locks = {}

    def should_analyze(self, account_id):
        if not self.enabled:
            return False
        self._calls[account_id] = self._calls.get(account_id, 0) + 1
        return self._calls[account_id] % self.interval == 0

    async def analyze_transition(self, account_id, state_before, action, state_after, reward, recent_actions):
        lock = self._locks.setdefault(account_id, asyncio.Lock())
        async with lock:
            return await asyncio.to_thread(
                self._analyze_sync,
                account_id,
                state_before,
                action,
                state_after,
                reward,
                recent_actions,
            )

    def _analyze_sync(self, account_id, state_before, action, state_after, reward, recent_actions):
        query_parts = [
            state_before.location or "",
            state_before.current_action or "",
            action,
            state_after.location or "",
            state_after.current_action or "",
            state_before.enemy_data.get("species", ""),
            state_after.enemy_data.get("species", ""),
        ]
        query = " ".join(part for part in query_parts if part)
        knowledge_context = self.retriever.build_context(query, include_conflicted=True)
        payload = {
            "account_id": account_id,
            "telegram_message_before": state_before.raw_text,
            "telegram_buttons_before": [item.text for item in state_before.available_actions],
            "telegram_message_after": state_after.raw_text,
            "telegram_buttons_after": [item.text for item in state_after.available_actions],
            "parsed_state_before": self._state_dict(state_before),
            "parsed_state_after": self._state_dict(state_after),
            "transition": {
                "action": action,
                "reward": reward,
                "recent_actions": recent_actions,
            },
            "knowledge_context": knowledge_context,
        }
        prompt = self._build_prompt(payload)
        try:
            raw = self._request(prompt)
            result = self._parse_result(raw)
            self._persist_candidates(account_id, state_before, action, state_after, reward, result)
            signal = result.get("learning_signal", 0.0)
            try:
                signal = max(-5.0, min(5.0, float(signal)))
            except (TypeError, ValueError):
                signal = 0.0
            return {"learning_signal": signal, "candidates": result.get("candidates", [])}
        except Exception as exc:
            print(f"[QWEN] Analysis failed for {account_id}: {exc}")
            return {"learning_signal": 0.0, "candidates": []}

    @staticmethod
    def _parse_result(raw: str) -> dict[str, Any]:
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start < 0 or end <= start:
                raise
            result = json.loads(raw[start:end + 1])

        if not isinstance(result, dict):
            raise ValueError("Qwen response is not a JSON object")
        return result

    def _request(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a game-mechanics analyst for a reinforcement-learning agent. "
                        "The Telegram messages are the primary observation source. "
                        "Read the complete actual game text and visible buttons before and after the action. "
                        "Do not choose actions, do not give commands to execute, and do not invent rules. "
                        "Evaluate only the observed transition and extract durable knowledge supported by evidence."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "think": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_predict": self.max_tokens,
            },
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["message"]["content"]

    def _build_prompt(self, payload: dict[str, Any]) -> str:
        return (
            "Analyze exactly one gameplay transition using the complete actual Telegram game messages as the primary evidence. Return JSON only, with this schema:\n"
            "{\"learning_signal\":0.0,\"candidates\":[{\"type\":\"mechanic|action_consequence|prerequisite|exception|hypothesis\","
            "\"claim\":\"...\",\"mechanic_key\":\"stable_machine_readable_topic\","
            "\"relation\":\"new|supports|contradicts|unclear\",\"conflicts_with\":[\"claim text\"],"
            "\"domain\":\"...\",\"confidence\":0.0,\"status\":\"hypothesis|candidate\","
            "\"conditions\":\"...\",\"consequences\":\"...\",\"exceptions\":\"...\","
            "\"evidence\":[\"...\"],\"related\":[\"...\"]}]}\n\n"
            "Analysis priority:\n"
            "1. Compare telegram_message_before with telegram_message_after exactly as written by the game.\n"
            "2. Use the complete Telegram text and visible buttons to determine what actually changed.\n"
            "3. Distinguish game facts explicitly stated in the messages from assumptions or hypotheses.\n"
            "4. Use parsed state fields as supporting structure, not as a replacement for the Telegram text.\n"
            "5. Treat the selected action and reward as context for the observed outcome.\n"
            "6. Use retrieved knowledge only as prior context; never override direct observed evidence with an unsupported rule.\n\n"
            "Rules for learning_signal:\n"
            "- It evaluates the quality of the observed action outcome, not which action should be selected.\n"
            "- Use a small numeric signal from -5.0 to +5.0.\n"
            "- Give 0.0 when the messages do not provide enough evidence to judge the outcome.\n"
            "- Do not invent a reward merely because an action changed the screen.\n\n"
            "Input:\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
        )

    @staticmethod
    def _state_dict(state) -> dict[str, Any]:
        return {
            "raw_text": state.raw_text,
            "location": state.location,
            "current_action": state.current_action,
            "available_actions": [action.text for action in state.available_actions],
            "self_data": state.self_data,
            "enemy_data": state.enemy_data,
            "inventory": state.inventory,
            "events": state.events,
        }

    def _persist_candidates(self, account_id, state_before, action, state_after, reward, result):
        candidates = result.get("candidates", [])
        if not isinstance(candidates, list):
            return
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            try:
                self.writer.add_candidate(
                    account_id,
                    state_before,
                    action,
                    state_after,
                    reward,
                    candidate,
                )
            except Exception as exc:
                print(f"[QWEN] Knowledge write failed for {account_id}: {exc}")
