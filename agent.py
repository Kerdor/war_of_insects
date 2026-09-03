import asyncio

from learning import QLearning
from memory import ExperienceMemory
from perception import Perception
from reward import RewardEngine
from strategy import StrategyMemory
from transitions import TransitionMemory


class Agent:
    def __init__(self, learning=None, memory=None, transitions=None, strategy=None):
        self.perception = Perception()
        self.learning = learning or QLearning()
        self.memory = memory or ExperienceMemory()
        self.transitions = transitions or TransitionMemory()
        self.strategy = strategy or StrategyMemory()
        self.reward = RewardEngine()
        self.epsilon = 0.20

    async def step(self, client, message, account_id):
        buttons = self._flatten_buttons(message)
        state = self.perception.parse(message.text or "", buttons)
        state_key = self.perception.state_key(state)
        actions = [action.key or action.text for action in state.available_actions]

        if not actions:
            return None

        target = state.enemy_data.get("species") or state.enemy_data.get("name") or "unknown"
        selected_key = self.learning.choose(state_key, actions, self.epsilon, self.transitions)
        selected_key = self._apply_strategy_bonus(target, actions, selected_key)
        selected = next(action for action in state.available_actions if (action.key or action.text) == selected_key)

        await self._click(message, selected)
        next_message = await self._wait_for_change(client, state_key)
        if next_message is None:
            return selected.text

        next_state = self.perception.parse(next_message.text or "", self._flatten_buttons(next_message))
        next_key = self.perception.state_key(next_state)
        next_actions = [action.key or action.text for action in next_state.available_actions]
        reward = self.reward.calculate(state, next_state)

        self.memory.add(account_id, state_key, selected_key, next_key, reward)
        self.transitions.record(state_key, selected_key, next_key, reward)
        self.learning.update(state_key, selected_key, reward, next_key, next_actions)

        if self._is_terminal(next_state):
            outcome = self._outcome(next_state)
            final_target = next_state.enemy_data.get("species") or next_state.enemy_data.get("name") or target
            self.strategy.record(target, selected_key, reward, outcome)
            self.memory.add_episode_outcome(account_id, next_state, reward)

        return selected.text

    def _apply_strategy_bonus(self, target: str, actions: list[str], selected: str) -> str:
        if not actions:
            return selected
        scores = {action: self.strategy.score(target, action) for action in actions}
        best = max(scores.values(), default=0.0)
        if best <= 0.0:
            return selected
        selected_score = scores.get(selected, 0.0)
        if selected_score >= best:
            return selected
        return max(actions, key=lambda action: scores[action])

    async def _wait_for_change(self, client, state_key: str):
        for _ in range(10):
            await asyncio.sleep(0.5)
            message = await client.get_latest()
            if message is None:
                continue
            state = self.perception.parse(message.text or "", self._flatten_buttons(message))
            if self.perception.state_key(state) != state_key:
                return message
        return await client.get_latest()

    async def _click(self, message, action) -> None:
        if action.callback_data is not None:
            for row in message.buttons or []:
                for button in row:
                    data = getattr(button, "data", None)
                    if isinstance(data, bytes):
                        data = data.decode("utf-8", errors="replace")
                    if data == action.callback_data:
                        await button.click()
                        return
        for row in message.buttons or []:
            for button in row:
                if getattr(button, "text", "") == action.text:
                    await button.click()
                    return

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
