import asyncio
import time

from telethon.tl.types import KeyboardButtonSwitchInline

from .knowledge_retrieval import KnowledgeRetriever
from .learning import QLearning
from .memory import ExperienceMemory
from .perception import Perception
from .qwen_analyst import QwenAnalyst
from .reward import RewardEngine
from .stats import LearningStats
from .strategy import StrategyMemory
from .transitions import TransitionMemory


class Agent:
    def __init__(self, learning=None, memory=None, transitions=None, strategy=None, stats=None, analyst=None):
        self.perception = Perception()
        self.learning = learning or QLearning()
        self.memory = memory or ExperienceMemory()
        self.transitions = transitions or TransitionMemory()
        self.strategy = strategy or StrategyMemory()
        self.stats = stats or LearningStats()
        self.reward = RewardEngine()
        self.analyst = analyst or QwenAnalyst(KnowledgeRetriever())
        self.epsilon = 0.20
        self.account_state = {}

    async def step(self, client, message, account_id):
        buttons = await client.get_current_buttons(message)
        state = self.perception.parse(message.text or "", buttons)
        state_key = self.perception.state_key(state)
        actions = [action.key or action.text for action in state.available_actions]

        if not actions:
            print(f"[{account_id}] No actions detected | State: {state.location} | Buttons: {len(buttons)}")
            return None

        target = state.enemy_data.get("species") or state.enemy_data.get("name") or "unknown"
        context = self.account_state.setdefault(account_id, {
            "recent_states": [],
            "recent_actions": [],
            "last_change": time.time(),
            "epsilon": self.epsilon,
        })
        if context["recent_states"] and context["recent_states"][-1] != state_key:
            context["last_change"] = time.time()
        context["recent_states"].append(state_key)
        context["recent_states"] = context["recent_states"][-8:]

        if len(context["recent_states"]) >= 6 and len(set(context["recent_states"][-6:])) <= 2:
            context["epsilon"] = min(0.50, context["epsilon"] + 0.10)
        elif context["epsilon"] > self.epsilon:
            context["epsilon"] = max(self.epsilon, context["epsilon"] - 0.02)

        selected_key = self.learning.choose(
            state_key,
            actions,
            context["epsilon"],
            self.transitions,
            self.strategy,
            target,
        )
        selected = next(action for action in state.available_actions if (action.key or action.text) == selected_key)
        context["recent_actions"].append(selected_key)
        context["recent_actions"] = context["recent_actions"][-20:]

        print(f"[{account_id}] State: {state.location} | Actions: {', '.join(action.text for action in state.available_actions)}")
        print(f"[{account_id}] Selected: {selected.text}")

        clicked = await self._click(client, message, selected)
        if not clicked:
            print(f"[{account_id}] Action was not clicked: {selected.text}")
            return selected.text

        next_message = await self._wait_for_change(client, state_key)
        if next_message is None:
            return selected.text

        next_buttons = await client.get_current_buttons(next_message)
        next_state = self.perception.parse(next_message.text or "", next_buttons)
        next_key = self.perception.state_key(next_state)
        next_actions = [action.key or action.text for action in next_state.available_actions]
        reward = self.reward.calculate(state, next_state)

        self.memory.add(account_id, state_key, selected_key, next_key, reward)
        self.transitions.record(state_key, selected_key, next_key, reward)
        self.learning.update(state_key, selected_key, reward, next_key, next_actions)
        self.stats.record_step(account_id, reward)

        if self.analyst.should_analyze(account_id):
            asyncio.create_task(
                self.analyst.analyze_transition(
                    account_id,
                    state,
                    selected_key,
                    next_state,
                    reward,
                    list(context["recent_actions"]),
                )
            )

        if self._is_terminal(next_state):
            outcome = self._outcome(next_state)
            final_target = next_state.enemy_data.get("species") or next_state.enemy_data.get("name") or target
            self.strategy.record(final_target, selected_key, reward, outcome)
            self.memory.add_episode_outcome(account_id, next_state, reward)
            self.stats.record_episode(account_id, outcome)
            context["recent_states"] = []
            context["recent_actions"] = []
            context["epsilon"] = min(0.50, context["epsilon"] + 0.10) if outcome == "defeat" else max(self.epsilon, context["epsilon"] - 0.05)

        return selected.text

    async def _wait_for_change(self, client, state_key: str):
        for _ in range(10):
            await asyncio.sleep(0.5)
            message = await client.get_latest()
            if message is None:
                continue
            buttons = await client.get_current_buttons(message)
            state = self.perception.parse(message.text or "", buttons)
            if self.perception.state_key(state) != state_key:
                return message
        return await client.get_latest()

    async def _click(self, client, message, action) -> bool:
        if action.callback_data is not None:
            for row in message.buttons or []:
                for button in row:
                    data = getattr(button, "data", None)
                    if isinstance(data, bytes):
                        data = data.decode("utf-8", errors="replace")
                    if data == action.callback_data:
                        await button.click()
                        return True

        for row in message.buttons or []:
            for button in row:
                if isinstance(getattr(button, "button", None), KeyboardButtonSwitchInline):
                    continue
                if getattr(button, "text", "") == action.text:
                    await client.send(action.text)
                    return True

        try:
            await client.send(action.text)
            return True
        except Exception:
            return False

    def _is_terminal(self, state) -> bool:
        text = state.raw_text.lower()
        return (
            "погиб" in text
            or "проиграл" in text
            or "все враги повержены" in text
            or "побежден" in text
            or "победил" in text
        )

    def _outcome(self, state) -> str:
        text = state.raw_text.lower()
        if "погиб" in text or "проиграл" in text:
            return "defeat"
        if "все враги повержены" in text or "побежден" in text or "победил" in text:
            return "victory"
        return "unknown"

    def _flatten_buttons(self, message):
        result = []
        for row in message.buttons or []:
            result.extend(row)
        return result
