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
    the only action-selection layer. Qwen may provide a bounded evidence-based
    learning signal about the observed transition.
    """

    def __init__(self, retriever=None, writer=None):
        self.enabled = os.getenv("QWEN_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
        self.base_url = os.getenv("QWEN_BASE_URL", "http://localhost:11434").rstrip("/")
        self.model = os.getenv("QWEN_MODEL", "qwen3:4b").strip()
        self.interval = max(1, int(os.getenv("QWEN_ANALYSIS_INTERVAL", "1")))
        self.max_tokens = max(256, int(os.getenv("QWEN_MAX_TOKENS", "1200")))
        self.timeout = max(5, int(os.getenv("QWEN_TIMEOUT", "120")))
        self.retriever = retriever or KnowledgeRetriever()
        self.writer = writer or KnowledgeWriter()
        self.pending = {}
        self.locks = {}

    def should_analyze(self, account_id: str) -> bool:
        if not self.enabled:
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
    ) -> dict[str, Any]:
        if not self.enabled:
            return {"learning_signal": 0.0}

        lock = self.locks.setdefault(account_id, asyncio.Lock())
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
                candidates = result.get("candidates", [])
                if candidates:
                    written = self.writer.write_candidates(candidates, account_id, observation_id)
                    if written:
                        print(f"[{account_id}] Qwen analyst: wrote/updated {len(written)} knowledge candidate(s)")
                learning_signal = self._bounded_signal(result.get("learning_signal", 0.0))
                print(f"[{account_id}] Qwen learning signal: {learning_signal:+.2f}")
                return {"learning_signal": learning_signal}
            except Exception as exc:
                print(f"[{account_id}] Qwen analyst error: {exc}")
                return {"learning_signal": 0.0}

    def _analyze_sync(self, account_id, state_before, action, state_after, reward, recent_actions):
        query_parts = [state_before.location, state_before.current_action, action]
        if state_before.enemy_data:
            query_parts.append(str(state_before.enemy_data.get("species", "")))
        query = " ".join(part for part in query_parts if part and part != "unknown")
        knowledge_context = self.retriever.build_qwen_prompt_context(
            query or "game mechanics",
            top_k=6,
            max_chars=8000,
            include_conflicted=True,
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
                        "Evaluate only the observed transition and extract durable knowledge supported by evidence."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.1,
                "num_predict": self.max_tokens,
            },
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
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
            return str(data["message"]["content"])
        except (KeyError, TypeError) as exc:
            raise RuntimeError("Qwen returned an unexpected response") from exc

    def _build_prompt(self, payload: dict[str, Any]) -> str:
        return (
            "Analyze exactly one gameplay transition. Return JSON only, with this schema:\n"
            "{\"learning_signal\":0.0,\"candidates\":[{\"type\":\"mechanic|action_consequence|prerequisite|exception|hypothesis\","
            "\"claim\":\"...\",\"mechanic_key\":\"stable_machine_readable_topic\","
            "\"relation\":\"new|supports|contradicts|unclear\",\"conflicts_with\":[\"claim text\"],"
            "\"domain\":\"...\",\"confidence\":0.0,\"status\":\"hypothesis|candidate\","
            "\"conditions\":\"...\",\"consequences\":\"...\",\"exceptions\":\"...\","
            "\"evidence\":[\"...\"],\"related\":[\"...\"]}]}\n\n"
            "Rules for learning_signal:\n"
            "- It evaluates the quality of the observed action outcome, not which action should be selected.\n"
            "- Use a small numeric signal from -5.0 to +5.0.\n"
            "- Positive only when the observed transition provides evidence of a useful outcome.\n"
            "- Negative only when the observed transition provides evidence of a harmful outcome.\n"
            "- Use 0.0 when the outcome is neutral, ambiguous, or insufficiently observable.\n"
            "- Do not infer a reward merely because an action is plausible.\n"
            "Rules for candidates:\n"
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
            "- If there is not enough evidence for durable knowledge, return an empty candidates list.\n\n"
            f"OBSERVATION:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    @staticmethod
    def _parse_response(response: str) -> dict[str, Any]:
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
                return {"learning_signal": 0.0, "candidates": []}
            try:
                data = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return {"learning_signal": 0.0, "candidates": []}
        if not isinstance(data, dict):
            return {"learning_signal": 0.0, "candidates": []}
        candidates = data.get("candidates", [])
        if not isinstance(candidates, list):
            candidates = []
        return {
            "learning_signal": data.get("learning_signal", 0.0),
            "candidates": candidates,
        }

    @staticmethod
    def _bounded_signal(value) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(-5.0, min(5.0, value))

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
