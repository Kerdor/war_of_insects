import asyncio
import hashlib
import json
import os
import urllib.error
import urllib.request
from typing import Any

from .knowledge_retrieval import KnowledgeRetriever
from .knowledge_writer import KnowledgeWriter


class QwenAnalyst:
    """Observes completed transitions and extracts durable knowledge.

    This component never chooses or executes gameplay actions. Q-learning remains
    the only action-selection layer.
    """

    def __init__(self, retriever=None, writer=None):
        self.enabled = os.getenv("QWEN_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
        self.api_key = os.getenv("QWEN_API_KEY", "").strip()
        self.base_url = os.getenv(
            "QWEN_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ).rstrip("/")
        self.model = os.getenv("QWEN_MODEL", "qwen-plus").strip()
        self.interval = max(1, int(os.getenv("QWEN_ANALYSIS_INTERVAL", "10")))
        self.max_tokens = max(256, int(os.getenv("QWEN_MAX_TOKENS", "1200")))
        self.timeout = max(5, int(os.getenv("QWEN_TIMEOUT", "30")))
        self.retriever = retriever or KnowledgeRetriever()
        self.writer = writer or KnowledgeWriter()
        self.pending = {}
        self.locks = {}

    def should_analyze(self, account_id: str) -> bool:
        if not self.enabled or not self.api_key:
            return False
        count = self.pending.get(account_id, 0) + 1
        self.pending[account_id] = count
        if count < self.interval:
            return False
        self.pending[account_id] = 0
        return True

    async def analyze_transition(
        self,
        account_id: str,
        state_before,
        action: str,
        state_after,
        reward: float,
        recent_actions: list[str],
    ) -> None:
        if not self.enabled or not self.api_key:
            return
        lock = self.locks.setdefault(account_id, asyncio.Lock())
        if lock.locked():
            return
        async with lock:
            try:
                observation_id = self._observation_id(
                    account_id,
                    state_before,
                    action,
                    state_after,
                    reward,
                )
                result = await asyncio.to_thread(
                    self._analyze_sync,
                    account_id,
                    state_before,
                    action,
                    state_after,
                    reward,
                    recent_actions,
                )
                if result:
                    written = self.writer.write_candidates(result, account_id, observation_id)
                    if written:
                        print(f"[{account_id}] Qwen analyst: wrote/updated {len(written)} knowledge candidate(s)")
            except Exception as exc:
                print(f"[{account_id}] Qwen analyst error: {exc}")

    def _analyze_sync(self, account_id, state_before, action, state_after, reward, recent_actions):
        query_parts = [state_before.location, state_before.current_action, action]
        if state_before.enemy_data:
            query_parts.append(str(state_before.enemy_data.get("species", "")))
        query = " ".join(part for part in query_parts if part and part != "unknown")
        knowledge_context = self.retriever.build_qwen_prompt_context(
            query or "game mechanics",
            top_k=6,
            max_chars=8000,
        )

        payload = {
            "account_id": account_id,
            "transition": {
                "action": action,
                "reward": reward,
                "state_before": self._state_dict(state_before),
                "state_after": self._state_dict(state_after),
            },
            "recent_actions": recent_actions[-12:],
            "knowledge_context": knowledge_context,
        }
        prompt = self._build_prompt(payload)
        response = self._request(prompt)
        return self._parse_response(response)

    def _request(self, prompt: str) -> str:
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a game-mechanics analyst for a reinforcement-learning agent. "
                        "Do not choose actions, do not give commands to execute, and do not invent rules. "
                        "Extract only durable knowledge supported by the observed transition and supplied sources."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": self.max_tokens,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Qwen HTTP {exc.code}: {details[:500]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Qwen connection failed: {exc.reason}") from exc

        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Qwen returned an unexpected response") from exc

    def _build_prompt(self, payload: dict[str, Any]) -> str:
        return (
            "Analyze exactly one gameplay transition. Return JSON only, with this schema:\n"
            "{\"candidates\":[{\"type\":\"mechanic|action_consequence|prerequisite|exception|hypothesis\","
            "\"claim\":\"...\",\"mechanic_key\":\"stable_machine_readable_topic\","
            "\"relation\":\"new|supports|contradicts|unclear\",\"conflicts_with\":[\"claim text\"],"
            "\"domain\":\"...\",\"confidence\":0.0,\"status\":\"hypothesis|candidate\","
            "\"conditions\":\"...\",\"consequences\":\"...\",\"exceptions\":\"...\","
            "\"evidence\":[\"...\"],\"related\":[\"...\"]}]}\n\n"
            "Rules:\n"
            "- Produce at most 5 candidates.\n"
            "- Confidence must reflect evidence, not plausibility.\n"
            "- A single transition normally supports a hypothesis, not a confirmed rule.\n"
            "- Never mark a candidate as confirmed. The writer confirms only after repeated independent evidence.\n"
            "- Official source text is authoritative; learned text is only prior observation.\n"
            "- relation=supports means the observation agrees with an existing learned claim.\n"
            "- relation=contradicts means the observation materially conflicts with an existing learned claim under the same mechanic_key.\n"
            "- Different conditions are not automatically contradictions. Only mark contradicts when the claims cannot both be true under the same stated conditions.\n"
            "- conflicts_with should contain the exact claim text from retrieved learned context when a contradiction is identified; otherwise return [].\n"
            "- If retrieved knowledge contains a conflict, do not resolve it by guessing. Preserve uncertainty and use relation=unclear when evidence is insufficient.\n"
            "- Do not use conflicted knowledge as an authoritative rule.\n"
            "- Do not copy large source passages.\n"
            "- If there is not enough evidence for durable knowledge, return {\"candidates\":[]}.\n\n"
            f"OBSERVATION:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    @staticmethod
    def _parse_response(response: str) -> list[dict[str, Any]]:
        text = response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                return []
            try:
                data = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return []
        candidates = data.get("candidates", []) if isinstance(data, dict) else []
        return candidates if isinstance(candidates, list) else []

    @staticmethod
    def _observation_id(account_id, state_before, action, state_after, reward) -> str:
        payload = {
            "account_id": account_id,
            "state_before": state_before.raw_text,
            "action": action,
            "state_after": state_after.raw_text,
            "reward": reward,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha1(encoded).hexdigest()[:20]

    @staticmethod
    def _state_dict(state) -> dict[str, Any]:
        return {
            "raw_text": state.raw_text[-5000:],
            "location": state.location,
            "current_action": state.current_action,
            "available_actions": [action.text for action in state.available_actions],
            "self_data": state.self_data,
            "enemy_data": state.enemy_data,
            "inventory": state.inventory,
            "events": state.events[-10:],
        }
